import math

from app.schemas import FarmProfile


def test_financial_math_is_internally_consistent(services):
    profile = FarmProfile(
        location_text="Rangpur",
        district="Rangpur",
        farm_size_acre=2,
        soil_type="loam",
        water_availability="limited",
        budget_bdt=100000,
        target_season="rabi",
    )
    projection = services.finance.calculate("lentil", profile)
    assert math.isclose(
        projection.expected_revenue_bdt,
        projection.total_expected_yield_kg * projection.expected_price_bdt_per_kg,
        abs_tol=0.01,
    )
    assert math.isclose(
        projection.net_profit_bdt,
        projection.expected_revenue_bdt - projection.total_cost_bdt,
        abs_tol=0.01,
    )
    assert math.isclose(
        projection.break_even_price_bdt_per_kg,
        projection.total_cost_bdt / projection.total_expected_yield_kg,
        abs_tol=0.01,
    )
    assert projection.data_status == "mock_economics"
