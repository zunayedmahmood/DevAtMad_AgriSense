from __future__ import annotations

import json
from typing import Any

from app.dependencies import Services
from app.schemas import AgentTurnRequest, AgentTurnResponse, FarmProfile, ToolTraceItem
from app.services.intake import IntakeParser
from app.services.safety import detect_safety_flags
from app.services.trace import TraceRecorder


class TierZeroAgent:
    def __init__(self, services: Services):
        self.services = services
        self.intake = IntakeParser(services.kb, services.location_normalizer)

    async def turn(self, request: AgentTurnRequest) -> AgentTurnResponse:
        db = self.services.database
        session_id = db.ensure_session(request.session_id)
        session = db.get_session(session_id) or {"profile": {}}
        profile = FarmProfile.model_validate(session.get("profile") or {})
        db.add_message(session_id, "user", request.message)
        trace = TraceRecorder(db, session_id)
        safety_flags = detect_safety_flags(request.message)

        parsed = await trace.call(
            "parse_farmer_message",
            {"message": request.message, "current_profile": profile.model_dump(mode="json")},
            lambda: self.intake.parse(request.message, profile),
            source_kind="deterministic_local_parser",
        )
        profile = self.intake.merge(profile, parsed, request.profile_patch)
        db.save_profile(session_id, profile)
        normalized = self.services.location_normalizer.extract(profile.location_text or "")
        weather = None
        if profile.location_text and (profile.latitude is None or profile.longitude is None):
            geocode = await trace.call(
                "geocode_location",
                {
                    "location_text": profile.location_text,
                    "district": profile.district,
                    "upazila": profile.upazila,
                    "clean_query_preview": self.services.geocoder._build_query(
                        profile.location_text or "", profile.district, profile.upazila
                    ),
                },
                lambda: self.services.geocoder.geocode(
                    profile.location_text or "",
                    district=profile.district,
                    upazila=profile.upazila,
                    exact_catalog_match=normalized.exact_catalog_match,
                ),
                source_kind="external_api_or_tagged_fallback",
            )
            profile = profile.model_copy(
                update={
                    "latitude": geocode["latitude"],
                    "longitude": geocode["longitude"],
                    "district": profile.district or geocode.get("district"),
                    "upazila": profile.upazila or geocode.get("upazila"),
                    "geocode_source": geocode["source"],
                    "geocode_confidence": geocode.get("confidence"),
                }
            )
            db.save_profile(session_id, profile)
            if geocode.get("needs_confirmation"):
                question = f"Geoapify matched your location to “{geocode['formatted']}”. Is that the correct farm area?"
                message = question
                db.add_message(session_id, "assistant", message)
                return self._response(
                    session_id=session_id,
                    trace_id=trace.trace_id,
                    status="needs_location_confirmation",
                    message=message,
                    missing_fields=[],
                    follow_up_questions=[question],
                    profile=profile,
                    safety_flags=safety_flags,
                    decision_summary=[
                        "The external geocoding confidence was below the configured threshold, so the location was not silently accepted."
                    ],
                )

        if profile.latitude is not None and profile.longitude is not None:
            weather = await trace.call(
                "get_live_weather_forecast",
                {
                    "latitude": profile.latitude,
                    "longitude": profile.longitude,
                    "forecast_days": self.services.settings.default_forecast_days,
                    "force_refresh": request.force_refresh_weather,
                },
                lambda: self.services.weather.forecast(
                    profile.latitude or 0.0,
                    profile.longitude or 0.0,
                    days=self.services.settings.default_forecast_days,
                    force_refresh=request.force_refresh_weather,
                ),
                source_kind="external_api_or_tagged_fallback",
            )

        missing = self.intake.missing_fields(profile)
        questions = self.intake.followups(
            missing, parsed.clarifications, self.services.settings.max_followup_fields
        )
        if missing or parsed.clarifications:
            message = self._collecting_message(profile, weather, questions, safety_flags)
            db.add_message(session_id, "assistant", message)
            decision_summary = [
                f"Reasoning Process: Extracted current profile: {json.dumps({k: v for k, v in profile.model_dump().items() if v is not None})}.",
                *parsed.extraction_notes,
            ]
            if weather and weather.get("summary"):
                decision_summary.append(
                    f"Proactively retrieved live weather for {profile.location_text}: "
                    f"{weather['summary']['temperature_avg_c']}°C mean temp, {weather['summary']['rainfall_forecast_total_mm']} mm rainfall forecast."
                )
            decision_summary.append(f"Field collection required: {', '.join(missing or ['clarifications'])}.")
            return self._response(
                session_id=session_id,
                trace_id=trace.trace_id,
                status="collecting_profile",
                message=message,
                missing_fields=missing,
                follow_up_questions=questions,
                profile=profile,
                safety_flags=safety_flags,
                decision_summary=decision_summary,
            )

        context_query = (
            f"crop suitability season calendar fertilizer water yield in {profile.upazila or ''} "
            f"{profile.district or profile.location_text} for {profile.target_season} soil {profile.soil_type}"
        )
        retrieved_context = await trace.call(
            "retrieve_agronomic_context",
            {
                "query": context_query,
                "district": profile.district,
                "upazila": profile.upazila,
                "top_k": 10,
            },
            lambda: [
                item.model_dump(mode="json")
                for item in self.services.rag.search(
                    context_query,
                    top_k=10,
                    district=profile.district,
                    upazila=profile.upazila,
                    include_mock=True,
                )
            ],
            source_kind="persistent_hybrid_rag",
        )

        recommendations = await trace.call(
            "rank_crop_candidates",
            {
                "profile": profile.model_dump(mode="json"),
                "weather_summary": weather["summary"],
                "retrieved_context_document_ids": [row["document_id"] for row in retrieved_context],
                "minimum_candidates": 3,
            },
            lambda: self.services.recommender.rank(profile, weather, top_k=3),
            source_kind="deterministic_rules_plus_rag_plus_financial_calculator",
        )
        db.save_recommendations(
            session_id, [item.model_dump(mode="json") for item in recommendations]
        )

        selected_crop = profile.chosen_crop_id
        if selected_crop in {"__index_1", "__index_2", "__index_3"}:
            index_map = {"__index_1": 0, "__index_2": 1, "__index_3": 2}
            idx = index_map[selected_crop]
            if idx < len(recommendations):
                selected_crop = recommendations[idx].crop_id
                profile = profile.model_copy(update={"chosen_crop_id": selected_crop})
                db.save_profile(session_id, profile)
            else:
                selected_crop = None

        if request.auto_select_top_crop and not selected_crop:
            eligible_recs = [rec for rec in recommendations if rec.eligible]
            top_rec = eligible_recs[0] if eligible_recs else recommendations[0]
            selected_crop = top_rec.crop_id
            profile = profile.model_copy(update={"chosen_crop_id": selected_crop})
            db.save_profile(session_id, profile)
        if selected_crop and selected_crop not in self.services.kb.supported_crop_ids:
            selected_crop = None

        if not selected_crop:
            names = ", ".join(
                f"{item.rank}) {item.crop_name} ({item.suitability_score:.0f}/100)"
                for item in recommendations
            )
            message = (
                f"I ranked three candidates using your farm profile, the geocoded location, the returned weather, "
                f"the RAG evidence, and inspectable mock economics: {names}. Which crop should I turn into the dated season plan?"
            )
            db.add_message(session_id, "assistant", message)
            return self._response(
                session_id=session_id,
                trace_id=trace.trace_id,
                status="awaiting_crop_selection",
                message=message,
                missing_fields=[],
                follow_up_questions=["Choose one of the ranked crops for the dated plan."],
                profile=profile,
                recommendations=recommendations,
                safety_flags=safety_flags,
                decision_summary=self._decision_summary(profile, weather, recommendations),
            )

        selected_recommendation = next(
            (item for item in recommendations if item.crop_id == selected_crop), None
        )
        if selected_recommendation is None:
            # A supported crop outside the top three can still be planned, but the agent makes the trade-off visible.
            full_ranking = self.services.recommender.rank(
                profile.model_copy(update={"chosen_crop_id": selected_crop}), weather, top_k=16
            )
            selected_recommendation = next(item for item in full_ranking if item.crop_id == selected_crop)

        if not selected_recommendation.eligible or not selected_recommendation.season_compatible:
            profile = profile.model_copy(update={"chosen_crop_id": None})
            db.save_profile(session_id, profile)
            eligible_crops = [rec.crop_name for rec in recommendations if rec.eligible]
            eligible_str = (
                ", ".join(eligible_crops) if eligible_crops else "another eligible crop from the list"
            )
            reason_details = (
                "; ".join(selected_recommendation.hard_eligibility_reasons)
                if selected_recommendation.hard_eligibility_reasons
                else "Planting window is incompatible with the target season."
            )
            message = (
                f"{selected_recommendation.crop_name} is not compatible with the selected "
                f"{(profile.target_season or '').title()} season ({reason_details}), so I cannot create it as "
                f"the recommended {(profile.target_season or '').title()} plan. Please select an eligible crop "
                f"such as {eligible_str}, or change the target season before continuing."
            )
            db.add_message(session_id, "assistant", message)
            return self._response(
                session_id=session_id,
                trace_id=trace.trace_id,
                status="awaiting_crop_selection",
                message=message,
                missing_fields=[],
                follow_up_questions=[
                    f"Select an eligible crop ({eligible_str}) or update your target season."
                ],
                profile=profile,
                recommendations=recommendations,
                safety_flags=safety_flags,
                decision_summary=self._decision_summary(profile, weather, recommendations)
                + [f"Blocked ineligible crop selection for {selected_recommendation.crop_name}."],
            )
        baseline = self.services.finance.calculate(selected_crop, profile)
        yield_factor = (
            selected_recommendation.estimated_revenue_bdt / baseline.expected_revenue_bdt
            if baseline.expected_revenue_bdt
            else 1.0
        )
        plan = await trace.call(
            "generate_dated_season_plan",
            {
                "crop_id": selected_crop,
                "profile": profile.model_dump(mode="json"),
                "weather_summary": weather["summary"],
                "yield_factor_from_recommendation": yield_factor,
            },
            lambda: self.services.planner.build(
                selected_crop,
                profile,
                weather,
                recommendation_yield_factor=yield_factor,
            ),
            source_kind="calendar_rules_plus_rag_plus_financial_calculator",
        )
        db.save_plan(session_id, selected_crop, plan.model_dump(mode="json"))
        message = (
            f"The dated {plan.crop_name} plan is ready from {plan.planned_sowing_date.isoformat()} to "
            f"{plan.expected_harvest_date.isoformat()}. Mock projected cost is BDT "
            f"{plan.financial_projection.total_cost_bdt:,.2f}, mock net profit is BDT "
            f"{plan.financial_projection.net_profit_bdt:,.2f}, and ROI is "
            f"{plan.financial_projection.roi_percent:.1f}%. Future tasks beyond the returned weather horizon are marked for refresh."
        )
        db.add_message(session_id, "assistant", message)
        return self._response(
            session_id=session_id,
            trace_id=trace.trace_id,
            status="plan_ready",
            message=message,
            missing_fields=[],
            follow_up_questions=[],
            profile=profile,
            recommendations=recommendations,
            selected_crop_id=selected_crop,
            plan=plan,
            safety_flags=safety_flags,
            decision_summary=self._decision_summary(profile, weather, recommendations)
            + [f"Selected crop: {selected_crop}. A dated calendar and financial projection were computed."],
        )

    def _response(self, **kwargs: Any) -> AgentTurnResponse:
        session_id = kwargs["session_id"]
        trace_rows = self.services.database.get_trace(session_id, None)
        kwargs["trace"] = [
            ToolTraceItem.model_validate(
                {
                    "step_no": row["step_no"],
                    "tool_name": row["tool_name"],
                    "parameters": row["parameters"],
                    "raw_result": row["raw_result"],
                    "status": row["status"],
                    "duration_ms": row["duration_ms"],
                    "source_kind": row["source_kind"],
                    "created_at": row["created_at"],
                }
            )
            for row in trace_rows
        ]
        return AgentTurnResponse.model_validate(kwargs)

    @staticmethod
    def _collecting_message(profile: FarmProfile, weather: dict[str, Any] | None, questions: list[str], safety_flags: list[str]) -> str:
        parts = []
        if safety_flags:
            parts.append("I will not invent missing farm or weather values.")

        known = []
        if profile.location_text:
            known.append(f"location: {profile.location_text}")
        if profile.farm_size_acre:
            known.append(f"land size: {profile.farm_size_acre:g} acres")
        if profile.soil_type:
            known.append(f"soil: {profile.soil_type}")
        if profile.water_availability:
            known.append(f"water: {profile.water_availability}")
        if profile.budget_bdt:
            known.append(f"budget: BDT {profile.budget_bdt:,.0f}")
        if profile.target_season:
            known.append(f"season: {profile.target_season}")

        if known:
            parts.append(f"I have recorded your farm details ({', '.join(known)}).")

        if weather and weather.get("summary") and profile.location_text:
            s = weather["summary"]
            parts.append(
                f"I've fetched the live weather forecast for {profile.location_text} "
                f"(mean temperature {s['temperature_avg_c']}°C, {s['rainfall_forecast_total_mm']} mm 7-day rainfall)."
            )

        if len(questions) == 1:
            q = questions[0]
            parts.append(f"To rank your crops and build your season plan, {q[0].lower() + q[1:] if q else q}")
        else:
            parts.append("I still need: " + " ".join(f"{index}. {question}" for index, question in enumerate(questions, 1)))

        return " ".join(parts)

    @staticmethod
    def _decision_summary(profile: FarmProfile, weather: dict[str, Any], recommendations: list[Any]) -> list[str]:
        summary = weather["summary"]
        return [
            f"Inputs: {profile.farm_size_acre:g} acres, {profile.soil_type} soil, {profile.water_availability} water, BDT {profile.budget_bdt:,.0f}, target {profile.target_season}.",
            f"Location used: {profile.location_text}; coordinates {profile.latitude:.5f}, {profile.longitude:.5f} from {profile.geocode_source}.",
            f"Weather used: {summary['rainfall_next_72h_mm']} mm rain in 72h, {summary['rainfall_forecast_total_mm']} mm over the returned horizon, mean temperature {summary['temperature_avg_c']} C; source {weather['source']}.",
            f"Top crop score: {recommendations[0].crop_name} at {recommendations[0].suitability_score}/100.",
            "Operational trace exposes tool parameters and returned values; it does not expose private chain-of-thought.",
        ]
