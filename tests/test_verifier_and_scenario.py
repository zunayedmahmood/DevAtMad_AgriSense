from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.schemas import FarmProfile
from app.services.verifier import PlanVerifier
from app.services.repair import RepairService
from app.services.scenario import ScenarioSimulator, ScenarioPatch
from app.dependencies import get_services


# Reusable mock weather payload — mirrors the shape returned by OpenMeteoClient.forecast()
MOCK_WEATHER = {
    "source": "open_meteo",
    "latitude": 25.7439,
    "longitude": 89.2517,
    "timezone": "Asia/Dhaka",
    "cache_hit": True,
    "summary": {
        "temperature_avg_c": 22.5,
        "temperature_max_c": 28.0,
        "temperature_min_c": 14.0,
        "humidity_avg_percent": 72.0,
        "rainfall_next_48h_mm": 0.0,
        "rainfall_next_72h_mm": 0.0,
        "rainfall_next_5d_mm": 1.2,
        "rainfall_forecast_total_mm": 4.8,
        "precipitation_probability_max_percent": 20,
        "dry_next_5d": True,
        "heavy_rain_next_48h": False,
        "heavy_rain_next_72h": False,
        "forecast_start": "2026-07-25",
        "forecast_end": "2026-07-31",
    },
    "current": {
        "temperature_2m": 24.0,
        "relative_humidity_2m": 70,
        "precipitation": 0.0,
        "rain": 0.0,
        "weather_code": 1,
    },
    "daily": [],
}


@pytest.mark.asyncio
async def test_plan_verifier_detects_math_error():
    services = get_services()
    verifier = PlanVerifier()
    profile = FarmProfile(
        location_text="Rangpur", farm_size_acre=2.0, budget_bdt=200000.0,
        target_season="Rabi", latitude=25.7439, longitude=89.2517
    )

    plan = services.planner.build("rice_boro", profile, MOCK_WEATHER)
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
    profile = FarmProfile(
        location_text="Rangpur", farm_size_acre=2.0, budget_bdt=200000.0,
        target_season="Rabi", latitude=25.7439, longitude=89.2517
    )

    plan = services.planner.build("rice_boro", profile, MOCK_WEATHER)
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
    profile = FarmProfile(
        location_text="Rangpur", farm_size_acre=2.0, budget_bdt=200000.0,
        target_season="Rabi", latitude=25.7439, longitude=89.2517
    )

    plan = services.planner.build("rice_boro", profile, MOCK_WEATHER)
    patch = ScenarioPatch(budget_bdt=120000.0)
    result = simulator.run_simulation(plan, profile, patch)

    assert result.baseline_metrics["budget_bdt"] == 200000.0
    assert result.scenario_metrics["budget_bdt"] == 120000.0
    assert result.feasibility_status == "feasible"
    assert "total_cost" in result.deltas
