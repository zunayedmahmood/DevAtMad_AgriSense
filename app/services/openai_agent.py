from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.dependencies import Services
from app.schemas import AgentTurnRequest, AgentTurnResponse, FarmProfile, ToolTraceItem
from app.services.agent import TierZeroAgent
from app.services.key_pool import OpenAIKeyPool
from app.services.trace import TraceRecorder
from app.tools.registry import TOOL_CATALOG, ToolRegistry

logger = logging.getLogger("agrisense.openai_agent")

AGRISENSE_SYSTEM_PROMPT = """You are AgriSense AI, an expert agricultural agentic advisor for Bangladesh farmers.
Your goal is to complete conversational farm intake, run accurate tool calls, assess weather and agronomy, and generate actionable dated seasonal farm plans with financial projections.

WORKFLOW INSTRUCTIONS:
1. Identify known farm profile fields from conversation history or memory:
   - Location (District & Upazila)
   - Farm Size (acres)
   - Soil Type
   - Water Availability / Source
   - Budget (BDT)
   - Target Season / Crop

2. Execute tool calls as needed:
   - Use `geocode_location` to resolve lat/long coordinates.
   - Use `get_weather_forecast` to fetch real weather data.
   - Use `retrieve_agronomy` to search agronomic knowledge base.
   - Use `rank_crop_candidates` to rank crops matching constraints.
   - Use `generate_season_plan` to build dated crop calendars.
   - Use `calculate_financial_projection` to compute costs, yield, revenue, net profit, and ROI.

3. After tool results are received, produce the complete farm plan for the farmer.
4. Refuse non-agricultural topics politely.
"""


class OpenAIAgenticEngine:
    """Agentic AI Engine powered by OpenAI Function Calling with multi-key pool rotation."""

    def __init__(self, services: Services):
        self.services = services
        self.settings = services.settings
        self.registry = ToolRegistry(services)
        self.fallback_agent = TierZeroAgent(services)
        self.key_pool = OpenAIKeyPool.from_settings_and_env(services.settings)

    def _convert_catalog_to_openai_tools(self) -> List[Dict[str, Any]]:
        """Returns TOOL_CATALOG directly since it is already formatted for OpenAI."""
        return TOOL_CATALOG

    async def turn(self, payload: AgentTurnRequest) -> AgentTurnResponse:
        """Alias for run_turn() to satisfy the controller interface."""
        return await self.run_turn(payload)

    async def run_turn(self, payload: AgentTurnRequest) -> AgentTurnResponse:
        """Executes a conversational agent turn with OpenAI function tool calling."""
        farmer_id = self.services.database.ensure_farmer(payload.farmer_id)
        session_id = self.services.database.ensure_session(payload.session_id, farmer_id=farmer_id, farm_id=payload.farm_id)
        
        if not self.key_pool.has_valid_keys():
            logger.info("No valid OpenAI API keys configured. Using agentic fallback engine.")
            return await self.fallback_agent.turn(payload)

        # Save incoming user message
        self.services.database.add_message(session_id, "user", payload.message)
        trace_recorder = TraceRecorder(self.services.database, session_id)
        
        # Retrieve context & prior state
        session = self.services.database.get_session(session_id) or {}
        prior_profile_data = session.get("profile") or {}
        current_profile = FarmProfile.model_validate(prior_profile_data) if prior_profile_data else FarmProfile()

        # Memory resolution
        memory = self.services.memory
        candidates = memory.find_candidate_farms(farmer_id, current_profile, payload.farm_id)
        active_farm_id = payload.farm_id or session.get("farm_id")

        if candidates and session.get("memory_status") != "declined":
            target_farm_id = active_farm_id or candidates[0].farm_id
            saved_farm = self.services.database.get_farm(target_farm_id, farmer_id)
            if saved_farm:
                saved_prof = FarmProfile.model_validate(saved_farm["profile"])
                current_profile, _ = memory.apply_saved_memory(saved_prof, current_profile)
                self.services.database.save_profile(session_id, current_profile)
                self.services.database.attach_session_to_farm(session_id, farmer_id, target_farm_id, memory_status="applied")
                active_farm_id = target_farm_id

        # Run OpenAI Tool Calling Loop
        try:
            return await self._run_openai_loop(session_id, payload, current_profile, candidates, active_farm_id, trace_recorder)
        except Exception as exc:
            logger.warning("OpenAI API call failed (%s). Using agentic fallback engine.", str(exc))
            fallback_payload = payload.model_copy(update={"farmer_id": farmer_id, "session_id": session_id})
            return await self.fallback_agent.turn(fallback_payload)

    async def _run_openai_loop(
        self,
        session_id: str,
        payload: AgentTurnRequest,
        profile: FarmProfile,
        candidates: list,
        active_farm_id: Optional[str],
        trace_recorder: TraceRecorder
    ) -> AgentTurnResponse:
        from openai import AsyncOpenAI

        model_name = self.settings.openai_model or "gpt-5.5"
        openai_tools = self._convert_catalog_to_openai_tools()

        # Construct conversation history
        db_messages = self.services.database.list_messages(session_id)
        messages: List[Dict[str, Any]] = []

        # System prompt with persistent farm memory overlay
        durable_memory_str = json.dumps([c.model_dump(mode="json") for c in candidates]) if candidates else "[]"
        profile_dict = profile.model_dump(mode="json")
        has_active_farm = active_farm_id is not None
        has_profile_data = any(v is not None for v in [
            profile_dict.get("location_text"), profile_dict.get("farm_size_acre"),
            profile_dict.get("soil_type"), profile_dict.get("water_availability")
        ])

        if has_active_farm and has_profile_data:
            context_overlay = (
                f"\n\n=== FARMER MEMORY IS ALREADY LOADED — DO NOT ASK FOR FARM DETAILS ===\n"
                f"ACTIVE FARM ID: {active_farm_id}\n"
                f"CURRENT FARM PROFILE: {json.dumps(profile_dict)}\n"
                f"ALL SAVED FARMS: {durable_memory_str}\n"
                f"INSTRUCTION: The farmer's profile is loaded above. DO NOT ask them to repeat it. "
                f"Proceed directly to answering using tools.\n"
                f"=== END FARMER MEMORY ===\n"
            )
        else:
            context_overlay = (
                f"\n\nCURRENT KNOWN FARM PROFILE: {json.dumps(profile_dict)}\n"
                f"SAVED PERSISTENT FARM MEMORY: {durable_memory_str}\n"
            )
        
        system_instruction = AGRISENSE_SYSTEM_PROMPT + context_overlay
        messages.append({"role": "system", "content": system_instruction})

        for msg in db_messages[-10:]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

        turn_count = 0
        max_turns = 10

        while turn_count < max_turns:
            turn_count += 1

            async def _call_openai(key: str):
                client = AsyncOpenAI(api_key=key)
                return await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )

            response = await self.key_pool.execute_with_retry(_call_openai)
            message = response.choices[0].message

            # Check for tool calls
            if message.tool_calls:
                messages.append(message.model_dump())

                for call in message.tool_calls:
                    fn_name = call.function.name
                    try:
                        fn_args = json.loads(call.function.arguments) if call.function.arguments else {}
                    except Exception:
                        fn_args = {}

                    logger.info("Executing OpenAI tool call: %s with args %s", fn_name, fn_args)

                    try:
                        result = await trace_recorder.call(
                            fn_name,
                            fn_args,
                            lambda: self.registry.invoke(fn_name, fn_args),
                            source_kind="agentic_tool_invocation"
                        )
                    except Exception as exc:
                        result = {"error": str(exc), "status": "failed"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result)
                    })
            else:
                # Assistant produced text response
                reply_text = message.content or "I have processed your farm planning request."
                self.services.database.add_message(session_id, "assistant", reply_text)

                raw_traces = self.services.database.get_trace(session_id, None)
                formatted_traces = [
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
                    for row in raw_traces
                ]

                intake = self.fallback_agent.intake
                parsed = intake.parse(payload.message, current=profile)
                extracted_profile = intake.merge(profile, parsed, None)
                missing_fields = intake.missing_fields(extracted_profile)
                status_val = "collecting_profile" if missing_fields else "plan_ready"

                self.services.database.save_profile(session_id, extracted_profile)
                if extracted_profile.location_text or extracted_profile.district or extracted_profile.farm_size_acre:
                    self.services.memory.save_confirmed_farm_memory(
                        farmer_id=payload.farmer_id,
                        farm_id=active_farm_id,
                        profile=extracted_profile,
                        session_id=session_id,
                    )

                return AgentTurnResponse(
                    session_id=session_id,
                    trace_id=trace_recorder.trace_id,
                    status=status_val,
                    message=reply_text,
                    missing_fields=missing_fields,
                    profile=extracted_profile,
                    trace=formatted_traces,
                )

        # Fallback if loop exhausted
        reply = "Your farm plan data has been processed. Please review the tool traces panel."
        self.services.database.add_message(session_id, "assistant", reply)
        raw_traces = self.services.database.get_trace(session_id, trace_recorder.trace_id)
        formatted_traces = [
            ToolTraceItem.model_validate({
                "step_no": row["step_no"],
                "tool_name": row["tool_name"],
                "parameters": row["parameters"],
                "raw_result": row["raw_result"],
                "status": row["status"],
                "duration_ms": row["duration_ms"],
                "source_kind": row["source_kind"],
                "created_at": row["created_at"],
            }) for row in raw_traces
        ]
        return AgentTurnResponse(
            session_id=session_id,
            trace_id=trace_recorder.trace_id,
            status="plan_ready",
            message=reply,
            missing_fields=[],
            profile=profile,
            trace=formatted_traces,
        )
