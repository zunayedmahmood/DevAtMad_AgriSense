from __future__ import annotations

import calendar
from typing import Any

from app.schemas import CropRecommendation, FarmProfile
from app.services.finance import FinancialCalculator
from app.services.kb import KnowledgeRepository
from app.services.rag import HybridRAGStore


WATER_NEED_RANK = {"very_low": 0, "low": 1, "medium": 2, "high": 3, "very_high": 4}
WATER_ACCESS_RANK = {"none": 0, "limited": 1, "rented": 2, "reliable": 4}


class CropRecommender:
    def __init__(
        self,
        kb: KnowledgeRepository,
        rag: HybridRAGStore,
        finance: FinancialCalculator,
    ):
        self.kb = kb
        self.rag = rag
        self.finance = finance

    def rank(self, profile: FarmProfile, weather: dict[str, Any], top_k: int = 3) -> list[CropRecommendation]:
        if not all(
            [
                profile.location_text,
                profile.farm_size_acre,
                profile.soil_type,
                profile.water_availability,
                profile.budget_bdt,
                profile.target_season,
            ]
        ):
            raise ValueError("Complete Tier-0 profile is required before ranking crops")
        results: list[CropRecommendation] = []
        for crop_id in self.kb.supported_crop_ids:
            results.append(self._score_crop(crop_id, profile, weather))
        results.sort(
            key=lambda item: (item.suitability_score, item.estimated_net_profit_bdt), reverse=True
        )
        ranked = []
        for index, result in enumerate(results[: max(3, top_k)], 1):
            ranked.append(result.model_copy(update={"rank": index}))
        return ranked

    def _score_crop(self, crop_id: str, profile: FarmProfile, weather: dict[str, Any]) -> CropRecommendation:
        bundle = self.kb.get_crop_bundle(crop_id)
        master = bundle["master"]
        score = 10.0
        reasons: list[str] = []
        warnings: list[str] = []

        season_score, season_reason = self._season_score(master.get("season", ""), profile.target_season or "")
        score += season_score
        season_compatible = season_score >= 0
        hard_eligibility_reasons: list[str] = []
        if not season_compatible:
            hard_eligibility_reasons.append("Planting window is incompatible with the target season.")
            warnings.append("This crop failed a hard eligibility gate.")
            warnings.append(season_reason)
        else:
            reasons.append(season_reason)

        suitable_soils = {soil.lower().replace("-", "_").replace(" ", "_") for soil in master.get("suitable_soils", [])}
        if profile.soil_type in suitable_soils:
            score += 18
            reasons.append(f"Soil match: {profile.soil_type} is listed in the supplied mock crop profile.")
        else:
            score -= 18
            warnings.append(f"Soil mismatch: {profile.soil_type} is not listed among the mock suitable soils.")

        need = master.get("irrigation_need", "medium")
        access = profile.water_availability or "none"
        need_rank = WATER_NEED_RANK.get(need, 2)
        access_rank = WATER_ACCESS_RANK.get(access, 0)
        if access_rank >= need_rank:
            score += 15
            reasons.append(f"Water fit: {access} access can cover the crop's {need} mock irrigation need.")
        elif access_rank + 1 == need_rank:
            score += 3
            warnings.append(f"Water is borderline: {access} access versus {need} crop need.")
        else:
            score -= 18
            warnings.append(f"Water mismatch: {access} access is below the crop's {need} mock need.")

        month_score, month_message = self._month_score(bundle["calendar"], profile.target_month)
        score += month_score
        (reasons if month_score >= 0 else warnings).append(month_message)

        weather_summary = weather["summary"]
        yield_factor = 1.0
        sensitivity = master.get("waterlogging_sensitivity", "medium")
        if weather_summary.get("heavy_rain_next_72h") and sensitivity in {"medium", "high"}:
            score -= 12
            yield_factor -= 0.08
            warnings.append(
                f"Live forecast shows {weather_summary['rainfall_next_72h_mm']} mm in 72 hours and the crop has {sensitivity} waterlogging sensitivity."
            )
        elif weather_summary.get("dry_next_5d") and need_rank >= 3 and access_rank < 3:
            score -= 10
            yield_factor -= 0.07
            warnings.append(
                "The live 5-day forecast is dry while this crop has high water need and irrigation is not reliable."
            )
        else:
            score += 3
            reasons.append("No immediate high-impact rain/water mismatch was detected in the live forecast window.")

        agronomy_rows = self.kb.district_agronomy(crop_id, profile.district)
        climate_row = self._select_agronomy_row(agronomy_rows, profile.target_season)
        if climate_row:
            climate = (climate_row.get("climate") or {}).get("temperature_celsius", {})
            avg = weather_summary.get("temperature_avg_c")
            if avg is not None and climate.get("minimum") is not None and climate.get("maximum") is not None:
                if float(climate["minimum"]) <= avg <= float(climate["maximum"]):
                    score += 5
                    reasons.append(
                        f"Live mean temperature {avg} C falls inside the supplied district profile range {climate['minimum']}-{climate['maximum']} C."
                    )
                else:
                    score -= 7
                    yield_factor -= 0.05
                    warnings.append(
                        f"Live mean temperature {avg} C is outside the supplied district profile range {climate['minimum']}-{climate['maximum']} C."
                    )

        suitability = self.kb.suitability(crop_id, profile.district, profile.upazila)
        if suitability and suitability.get("weighted_suitability_score_0_100") is not None:
            raw_score = float(suitability["weighted_suitability_score_0_100"])
            contribution = (raw_score - 50) * 0.12
            score += contribution
            reasons.append(
                f"Provided source-derived location suitability score is {raw_score:.1f}/100, contributing {contribution:+.1f} points."
            )

        projection = self.finance.calculate(
            crop_id,
            profile,
            yield_factor=max(0.65, yield_factor),
            extra_assumptions=["Recommendation-stage yield adjustment is rule-based from the 7-day forecast."],
        )
        if profile.budget_bdt >= projection.total_cost_bdt * 1.1:
            score += 12
            budget_fit = "comfortable"
            reasons.append("Budget covers the mock total cost with at least a 10% buffer.")
        elif profile.budget_bdt >= projection.total_cost_bdt:
            score += 5
            budget_fit = "tight"
            warnings.append("Budget covers the mock total cost but leaves less than a 10% buffer.")
        else:
            score -= 12
            budget_fit = "insufficient"
            warnings.append(
                f"Budget is short by BDT {projection.total_cost_bdt - profile.budget_bdt:,.2f} against the mock projection."
            )

        if projection.net_profit_bdt > 0:
            score += min(6, projection.roi_percent / 15)
            reasons.append(
                f"Mock expected projection is profitable: BDT {projection.net_profit_bdt:,.2f} net, ROI {projection.roi_percent:.1f}%."
            )
        else:
            score -= 10
            warnings.append("Mock expected projection is not profitable under the current assumptions.")

        eligible = season_compatible
        query = (
            f"{master['crop_name']} crop suitability agronomy calendar fertilizer irrigation in "
            f"{profile.upazila or ''} {profile.district or profile.location_text} {profile.target_season}"
        )
        evidence = self.rag.search(
            query,
            top_k=4,
            crop_id=crop_id,
            district=profile.district,
            upazila=profile.upazila,
            include_mock=True,
        )
        if len(evidence) < 2:
            evidence.extend(
                self.rag.search(query, top_k=4 - len(evidence), crop_id=crop_id, include_mock=True)
            )

        final_score = round(max(0.0, min(100.0, score)), 1)
        if final_score >= 75:
            label = "strong"
        elif final_score >= 55:
            label = "moderate"
        else:
            label = "weak"
        if final_score >= 75 and len(warnings) <= 1:
            risk = "low"
        elif final_score < 50 or len(warnings) >= 4:
            risk = "high"
        else:
            risk = "medium"
        return CropRecommendation(
            rank=0,
            crop_id=crop_id,
            crop_name=master["crop_name"],
            suitability_score=final_score,
            suitability_label=label,
            water_need=need,
            risk_level=risk,
            estimated_total_cost_bdt=projection.total_cost_bdt,
            estimated_revenue_bdt=projection.expected_revenue_bdt,
            estimated_net_profit_bdt=projection.net_profit_bdt,
            roi_percent=projection.roi_percent,
            budget_fit=budget_fit,
            reasons=reasons,
            warnings=warnings,
            evidence=evidence[:4],
            eligible=eligible,
            season_compatible=season_compatible,
            hard_eligibility_reasons=hard_eligibility_reasons,
        )

    @staticmethod
    def _season_score(crop_season: str, target: str) -> tuple[float, str]:
        crop = crop_season.lower().replace("-", "_")
        target = target.lower().replace("-", "_")
        if "year_round" in crop:
            return 20, "Season fit: the mock profile marks this crop as year-round."
        if target in crop or crop in target:
            return 25, f"Season fit: target {target} matches crop profile {crop}."
        if target.startswith("rabi") and "rabi" in crop:
            return 25, f"Season fit: target {target} matches a rabi crop."
        if target.startswith("kharif") and "kharif" in crop:
            return 22, f"Season fit: target {target} matches a kharif crop."
        return -20, f"Season mismatch: target {target} does not match mock crop season {crop}."

    @staticmethod
    def _month_score(calendar_row: dict[str, Any], target_month: int | None) -> tuple[float, str]:
        if target_month is None:
            return 0, "No target month was supplied, so month-window scoring was not applied."
        month_names = (
            calendar_row.get("sowing_window_months_mock", [])
            + calendar_row.get("transplant_window_months_mock", [])
        )
        month_numbers = {
            list(calendar.month_abbr).index(name[:3].title())
            for name in month_names
            if name[:3].title() in list(calendar.month_abbr)
        }
        if not month_numbers:
            return 0, "No mock sowing month window was available for this crop."
        if target_month in month_numbers:
            return 10, f"Target month {calendar.month_name[target_month]} is inside the supplied mock sowing/transplant window."
        return -15, f"Target month {calendar.month_name[target_month]} is outside the supplied mock sowing/transplant window."

    @staticmethod
    def _select_agronomy_row(rows: list[dict[str, Any]], target_season: str | None) -> dict[str, Any] | None:
        if not rows:
            return None
        if target_season:
            target = target_season.lower().replace("_", " ")
            for row in rows:
                season = str(row.get("season") or "").lower()
                if target.split()[0] in season:
                    return row
        return rows[0]
