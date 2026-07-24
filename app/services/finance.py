from __future__ import annotations

from typing import Any

from app.schemas import FarmProfile, FinancialProjection
from app.services.kb import KnowledgeRepository
from app.utils import money


class FinancialCalculator:
    def __init__(self, kb: KnowledgeRepository):
        self.kb = kb

    def calculate(
        self,
        crop_id: str,
        profile: FarmProfile,
        *,
        yield_factor: float = 1.0,
        price_factor: float = 1.0,
        extra_assumptions: list[str] | None = None,
    ) -> FinancialProjection:
        if profile.farm_size_acre is None or profile.budget_bdt is None:
            raise ValueError("farm_size_acre and budget_bdt are required")
        bundle = self.kb.get_crop_bundle(crop_id)
        economics = bundle["economics"]
        area = profile.farm_size_acre
        per_acre_components = economics["cost_components_bdt_per_acre_mock"]
        components = {name: money(value * area) for name, value in per_acre_components.items()}
        total_cost = money(sum(components.values()))
        expected_yield_per_acre = round(
            float(economics["expected_yield_kg_per_acre_mock"]) * yield_factor, 2
        )
        expected_price = money(float(economics["expected_price_bdt_per_kg_mock"]) * price_factor)
        total_yield = round(expected_yield_per_acre * area, 2)
        revenue = money(total_yield * expected_price)
        profit = money(revenue - total_cost)
        roi = round((profit / total_cost * 100) if total_cost else 0.0, 2)
        break_even_price = money(total_cost / total_yield) if total_yield else 0.0
        break_even_yield = round(total_cost / expected_price, 2) if expected_price else 0.0

        scenarios: dict[str, dict[str, float]] = {}
        for name, values in economics.get("scenario_projection_mock", {}).items():
            scenario_yield_per_acre = float(values["yield_kg_per_acre"])
            scenario_price = float(values["price_bdt_per_kg"])
            scenario_yield_total = scenario_yield_per_acre * area
            scenario_revenue = money(scenario_yield_total * scenario_price)
            scenarios[name] = {
                "yield_kg_per_acre": round(scenario_yield_per_acre, 2),
                "price_bdt_per_kg": money(scenario_price),
                "total_yield_kg": round(scenario_yield_total, 2),
                "revenue_bdt": scenario_revenue,
                "profit_bdt": money(scenario_revenue - total_cost),
            }

        assumptions = [
            "All yield, price, and cost baselines are synthetic mock values from the supplied demo KB.",
            f"Farm area is {area:g} acre(s); every per-acre cost was multiplied by this area.",
            f"Expected yield factor applied: {yield_factor:.3f}.",
            f"Expected price factor applied: {price_factor:.3f}.",
        ]
        assumptions.extend(extra_assumptions or [])
        math_trace = [
            f"total_cost = sum(scaled components) = BDT {total_cost:,.2f}",
            f"total_expected_yield = {expected_yield_per_acre:,.2f} kg/acre × {area:g} acres = {total_yield:,.2f} kg",
            f"expected_revenue = {total_yield:,.2f} kg × BDT {expected_price:,.2f}/kg = BDT {revenue:,.2f}",
            f"net_profit = BDT {revenue:,.2f} - BDT {total_cost:,.2f} = BDT {profit:,.2f}",
            f"ROI = net_profit / total_cost × 100 = {roi:.2f}%",
            f"break_even_price = total_cost / expected_yield = BDT {break_even_price:,.2f}/kg",
        ]
        return FinancialProjection(
            crop_id=crop_id,
            crop_name=bundle["master"]["crop_name"],
            area_acre=area,
            cost_components_bdt=components,
            total_cost_bdt=total_cost,
            budget_bdt=money(profile.budget_bdt),
            budget_surplus_or_gap_bdt=money(profile.budget_bdt - total_cost),
            expected_yield_kg_per_acre=expected_yield_per_acre,
            total_expected_yield_kg=total_yield,
            expected_price_bdt_per_kg=expected_price,
            expected_revenue_bdt=revenue,
            net_profit_bdt=profit,
            roi_percent=roi,
            break_even_price_bdt_per_kg=break_even_price,
            break_even_yield_kg=break_even_yield,
            scenario_projection=scenarios,
            assumptions=assumptions,
            math_trace=math_trace,
        )
