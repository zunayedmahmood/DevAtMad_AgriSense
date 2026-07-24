from datetime import UTC, datetime, timedelta
from app.schemas import FarmProfile
from app.services.planner import SeasonPlanner


def test_planner_forecast_horizon_rule(services):
    planner = SeasonPlanner(services.kb, services.rag, services.finance)
    today = datetime.now(UTC).date()
    
    mock_weather = {
        "source": "open_meteo_live",
        "summary": {
            "temperature_avg_c": 26.5,
            "rainfall_forecast_total_mm": 45.0,
            "rainfall_next_72h_mm": 50.0,
            "heavy_rain_next_72h": True,
            "rainfall_next_48h_mm": 30.0,
            "heavy_rain_next_48h": True,
            "rainfall_next_5d_mm": 40.0,
            "dry_next_5d": False,
            "forecast_start": today.isoformat(),
            "forecast_end": (today + timedelta(days=7)).isoformat(),
        },
    }

    profile = FarmProfile(
        location_text="Rangpur",
        district="Rangpur",
        upazila="Rangpur Sadar",
        farm_size_acre=2.0,
        soil_type="loam",
        water_availability="reliable",
        budget_bdt=100000.0,
        target_season="rabi",
    )

    plan = planner.build("wheat", profile, mock_weather)
    assert plan is not None
    assert len(plan.tasks) > 0

    distant_tasks = [task for task in plan.tasks if (task.start_date - today).days > 7]
    assert len(distant_tasks) > 0, "Expected tasks scheduled beyond 7-day forecast horizon"

    for task in distant_tasks:
        assert task.weather_refresh_required is True
        assert "outside current forecast horizon" in task.condition.lower()
        assert any("FORECAST HORIZON CHECK" in r for r in task.reasoning)

    near_term_tasks = [task for task in plan.tasks if 0 <= (task.start_date - today).days <= 7]
    for task in near_term_tasks:
        assert not any("FORECAST HORIZON CHECK" in r for r in task.reasoning)
