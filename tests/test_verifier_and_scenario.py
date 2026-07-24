from __future__ import annotations

import pytest
from app.schemas import FarmProfile
from app.services.verifier import PlanVerifier
from app.services.repair import RepairService
from app.services.scenario import ScenarioSimulator, ScenarioPatch
from app.dependencies import get_services


@pytest.mark.asyncio
async def test_plan_verifier_detects_math_error():
    services = get_services()
    verifier = PlanVerifier()
    profile = FarmProfile(location_text="Rangpur", farm_size_acre=2.0, budget_bdt=200000.0, target_season="Rabi", latitude=25.7439, longitude=89.2517)
    weather = await services.weather.forecast(profile.latitude, profile.longitude)
    
    plan = services.planner.build("rice_boro", profile, weather)
    # Tamper with net profit to simulate a calculation discrepancy
    plan.financial_projection.net_profit_bdt += 5000.0
    
    report = verifier.verify(plan, profile)
    assert report.outcome == "repair"
    assert "FINANCE_RECOMPUTE" in report.repair_codes
    assert any(c.check_id == "check_finance_math" and c.status == "repairable" for c in report.checks)


@pytest.mark.asyncio
async def test_repair_service_fixes_math_error():
    services = get_services()
    verifier = PlanVerifier()
    repair = RepairService()
    profile = FarmProfile(location_text="Rangpur", farm_size_acre=2.0, budget_bdt=200000.0, target_season="Rabi", latitude=25.7439, longitude=89.2517)
    weather = await services.weather.forecast(profile.latitude, profile.longitude)

    plan = services.planner.build("rice_boro", profile, weather)
    plan.financial_projection.net_profit_bdt += 5000.0

    report = verifier.verify(plan, profile)
    repaired_plan = repair.apply(plan, report.repair_codes)
    
    fin = repaired_plan.financial_projection
    expected_profit = fin.expected_revenue_bdt - fin.total_cost_bdt
    assert repaired_plan.financial_projection.net_profit_bdt == round(expected_profit, 2)

    post_report = verifier.verify(repaired_plan, profile)
    assert post_report.outcome == "pass"


@pytest.mark.asyncio
async def test_scenario_simulator_budget_cut():
    services = get_services()
    simulator = ScenarioSimulator()
    profile = FarmProfile(location_text="Rangpur", farm_size_acre=2.0, budget_bdt=200000.0, target_season="Rabi", latitude=25.7439, longitude=89.2517)
    weather = await services.weather.forecast(profile.latitude, profile.longitude)
    
    plan = services.planner.build("rice_boro", profile, weather)
    patch = ScenarioPatch(budget_bdt=120000.0)
    result = simulator.run_simulation(plan, profile, patch)

    assert result.baseline_metrics["budget_bdt"] == 200000.0
    assert result.scenario_metrics["budget_bdt"] == 120000.0
    assert result.feasibility_status == "feasible"
    assert "total_cost" in result.deltas
