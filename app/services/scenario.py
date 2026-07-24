from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from app.schemas import FarmProfile, SeasonPlan
from app.services.verifier import VerificationReport, PlanVerifier


class ScenarioPatch(BaseModel):
    budget_bdt: float | None = None
    rainfall_factor: float | None = None
    fertilizer_price_factor: float | None = None
    planting_delay_days: int | None = None
    sale_price_factor: float | None = None
    water_availability: str | None = None


class ScenarioResult(BaseModel):
    scenario_id: str
    baseline_plan_id: str
    baseline_plan_version: int
    applied_patch: ScenarioPatch
    affected_components: list[str] = Field(default_factory=list)
    baseline_metrics: dict[str, Any] = Field(default_factory=dict)
    scenario_metrics: dict[str, Any] = Field(default_factory=dict)
    deltas: dict[str, Any] = Field(default_factory=dict)
    changed_actions: list[dict[str, Any]] = Field(default_factory=list)
    unchanged_actions: list[str] = Field(default_factory=list)
    feasibility_status: str = "feasible"
    assumptions: list[str] = Field(default_factory=list)
    verification_report: VerificationReport | None = None


class ScenarioSimulator:
    """Simulates hypothetical scenarios on an isolated temporary overlay."""

    def __init__(self, verifier: PlanVerifier | None = None):
        self.verifier = verifier or PlanVerifier()

    def run_simulation(
        self,
        baseline_plan: SeasonPlan,
        profile: FarmProfile,
        patch: ScenarioPatch,
        scenario_id: str = "scen_sim",
    ) -> ScenarioResult:
        # Deep copy baseline plan and profile metrics
        fin = baseline_plan.financial_projection
        base_cost = fin.total_cost_bdt or 0.0
        base_rev = fin.expected_revenue_bdt or 0.0
        base_profit = fin.net_profit_bdt or 0.0
        base_roi = fin.roi_percent or 0.0
        base_budget = profile.budget_bdt or base_cost

        scen_budget = patch.budget_bdt if patch.budget_bdt is not None else base_budget
        scale_ratio = (scen_budget / base_budget) if base_budget > 0 else 1.0

        scen_cost = round(base_cost * scale_ratio, 2)
        scen_rev = round(base_rev * scale_ratio, 2)
        scen_profit = round(scen_rev - scen_cost, 2)
        scen_roi = round((scen_profit / scen_cost * 100.0), 2) if scen_cost > 0 else 0.0

        baseline_metrics = {
            "budget_bdt": base_budget,
            "total_cost_bdt": base_cost,
            "expected_revenue_bdt": base_rev,
            "net_profit_bdt": base_profit,
            "roi_percent": base_roi,
        }

        scenario_metrics = {
            "budget_bdt": scen_budget,
            "total_cost_bdt": scen_cost,
            "expected_revenue_bdt": scen_rev,
            "net_profit_bdt": scen_profit,
            "roi_percent": scen_roi,
        }

        deltas = {
            "capital_budget": {
                "baseline": f"BDT {base_budget:,.0f}",
                "scenario": f"BDT {scen_budget:,.0f}",
                "delta": f"{((scen_budget - base_budget) / base_budget * 100.0):.1f}%" if base_budget > 0 else "0.0%",
            },
            "total_cost": {
                "baseline": f"BDT {base_cost:,.0f}",
                "scenario": f"BDT {scen_cost:,.0f}",
                "delta": f"{((scen_cost - base_cost) / base_cost * 100.0):.1f}%" if base_cost > 0 else "0.0%",
            },
            "net_profit": {
                "baseline": f"BDT {base_profit:,.0f}",
                "scenario": f"BDT {scen_profit:,.0f}",
                "delta": f"{((scen_profit - base_profit) / base_profit * 100.0):.1f}%" if base_profit != 0 else "0.0%",
            },
            "projected_roi": {
                "baseline": f"{base_roi:.1f}%",
                "scenario": f"{scen_roi:.1f}%",
                "delta": f"{(scen_roi - base_roi):.1f}%",
            },
        }

        # Verify scenario plan
        scen_plan = baseline_plan.model_copy(deep=True)
        if scen_plan.financial_projection:
            scen_plan.financial_projection.total_cost_bdt = scen_cost
            scen_plan.financial_projection.expected_revenue_bdt = scen_rev
            scen_plan.financial_projection.net_profit_bdt = scen_profit
            scen_plan.financial_projection.roi_percent = scen_roi

        ver_report = self.verifier.verify(scen_plan, profile)

        return ScenarioResult(
            scenario_id=scenario_id,
            baseline_plan_id=baseline_plan.crop_id,
            baseline_plan_version=1,
            applied_patch=patch,
            affected_components=["capital_budget", "total_cost", "expected_revenue", "net_profit", "roi"],
            baseline_metrics=baseline_metrics,
            scenario_metrics=scenario_metrics,
            deltas=deltas,
            feasibility_status="feasible" if scen_cost <= scen_budget else "budget_exceeded",
            assumptions=["Scenario overlay evaluated without mutating persistent farm profile or database baseline."],
            verification_report=ver_report,
        )
