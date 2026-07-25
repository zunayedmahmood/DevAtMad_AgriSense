from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.agent.states import AgentState, TERMINAL_STATES
from app.agent.budget import RunBudget
from app.schemas import AgentTurnRequest, AgentTurnResponse, FarmProfile
from app.services.verifier import PlanVerifier, VerificationReport
from app.services.repair import RepairService
from app.services.scenario import ScenarioSimulator, ScenarioPatch


class AgentController:
    """Typed control plane controller for AgriSense."""

    def __init__(self, services: Any):
        self.services = services
        self.verifier = PlanVerifier()
        self.repair_service = RepairService()
        self.scenario_simulator = ScenarioSimulator(self.verifier)

    async def handle_turn(self, request: AgentTurnRequest) -> AgentTurnResponse:
        return await self.execute_turn(request)

    async def execute_turn(self, request: AgentTurnRequest) -> AgentTurnResponse:
        budget = RunBudget()
        session_id = self.services.database.ensure_session(
            request.session_id, farmer_id=request.farmer_id, farm_id=request.farm_id
        )

        # Delegate execution turn through the underlying verified agent pipeline
        response = await self.services.fallback_agent.turn(request)

        # Attach verification report
        if response.plan:
            report = self.verifier.verify(response.plan, response.profile)
            if report.outcome == "repair" and budget.used_repairs < budget.max_repairs:
                response.plan = self.repair_service.apply(response.plan, report.repair_codes)
                budget.used_repairs += 1
                report = self.verifier.verify(response.plan, response.profile)

            # Update validation_status on plan
            response.plan.validation_status = {
                "passed": report.outcome in {"pass", "verified_with_warnings"},
                "checks": [c.model_dump(mode="json") for c in report.checks],
                "report_id": report.report_id,
            }

        # Check for scenario request
        has_patch_budget = bool(request.profile_patch and request.profile_patch.budget_bdt is not None)
        is_hypo = "what if" in request.message.lower() or has_patch_budget
        if is_hypo and response.plan:
            patch = ScenarioPatch(budget_bdt=request.profile_patch.budget_bdt if request.profile_patch else None)
            scen_res = self.scenario_simulator.run_simulation(
                baseline_plan=response.plan,
                profile=response.profile,
                patch=patch,
            )
            response.scenario = scen_res.model_dump(mode="json")

        return response
