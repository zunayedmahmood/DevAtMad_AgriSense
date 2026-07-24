from app.schemas import AgentTurnRequest
from app.services.agent import TierZeroAgent


async def test_cross_turn_memory_and_full_tier_zero_plan(services):
    agent = TierZeroAgent(services)
    first = await agent.turn(AgentTurnRequest(message="I have land in Rangpur"))
    assert first.status == "collecting_profile"
    assert first.profile.location_text == "Rangpur"
    assert "location_text" not in first.missing_fields

    second = await agent.turn(
        AgentTurnRequest(
            session_id=first.session_id,
            message=(
                "The farm is 1.5 acres, loam soil, limited irrigation, budget 60000 taka, "
                "and I want rabi."
            ),
        )
    )
    assert second.status == "awaiting_crop_selection"
    assert second.profile.location_text == "Rangpur"
    assert len(second.recommendations) >= 3
    assert any(item.tool_name == "get_live_weather_forecast" for item in second.trace)
    assert any(item.tool_name == "retrieve_agronomic_context" for item in second.trace)

    third = await agent.turn(
        AgentTurnRequest(
            session_id=first.session_id,
            message="Build the plan for the best option.",
            auto_select_top_crop=True,
        )
    )
    assert third.status == "plan_ready"
    assert third.plan is not None
    assert third.plan.financial_projection.total_cost_bdt > 0
    assert third.plan.tasks[0].start_date <= third.plan.planned_sowing_date
    assert any(task.weather_refresh_required for task in third.plan.tasks)

    session = services.database.get_session(first.session_id)
    assert session is not None
    assert session["plan"] is not None


def test_health_check_operational_readiness(services):
    from app.api.routes import health
    res = health()
    assert res["status"] == "ok"
    assert res["agent_service_healthy"] is True
    assert res["sandbox_service_healthy"] is True
    assert res["kb_ready"] is True
    assert "external_weather_mode_enabled" in res


def test_trace_serializes_tool_results_as_structures(services):
    services.database.ensure_session("trace-test")
    services.database.write_trace(
        trace_id="t1",
        session_id="trace-test",
        step_no=1,
        tool_name="example",
        parameters={"x": 1},
        result={"value": 2},
        status="success",
        duration_ms=1.2,
        source_kind="test",
    )
    rows = services.database.get_trace("trace-test", "t1")
    assert rows[0]["raw_result"] == {"value": 2}


async def test_ineligible_crop_selection_is_blocked(services):
    agent = TierZeroAgent(services)
    first = await agent.turn(
        AgentTurnRequest(
            message=(
                "we have a plot of land in moulovibazar. it is 2 acre and has reliable irrigation and "
                "sandy-loamy soil. wehave a budget of 60 thousand taka. we are planing for the boro season."
            )
        )
    )
    assert first.status == "awaiting_crop_selection"
    assert len(first.recommendations) >= 3

    # Attempting to select an ineligible crop (e.g., rice_aman which is kharif_monsoon crop, incompatible with rabi/boro season)
    ineligible_choice = await agent.turn(
        AgentTurnRequest(
            session_id=first.session_id,
            message="want aman rice",
        )
    )
    assert ineligible_choice.status == "awaiting_crop_selection"
    assert "not compatible with the selected" in ineligible_choice.message
    assert ineligible_choice.plan is None

    # Now select an eligible crop (e.g. Boro rice or 1)
    eligible_choice = await agent.turn(
        AgentTurnRequest(
            session_id=first.session_id,
            message="1",
        )
    )
    assert eligible_choice.status == "plan_ready"
    assert eligible_choice.plan is not None
    assert eligible_choice.plan.fertilizer_split_reconciliation_passed is True
    assert eligible_choice.plan.financial_reconciliation_passed is True
    assert eligible_choice.plan.validation_status["passed"] is True


async def test_golden_journey_integration(services):
    """P0-D Golden-Journey Integration Test representing exact judge sequence:
    Turn 1: Location statement ("I have some land in Rangpur, Bangladesh.")
    Turn 2: Farm details ("2 acres, loam soil, reliable irrigation, BDT 200000 budget, targeting Rabi.")
    Turn 3: Crop selection ("1")
    Turn 4: What-if budget cut ("What if my budget is cut by 40%?")
    """
    agent = TierZeroAgent(services)

    # Turn 1: Location statement
    t1 = await agent.turn(AgentTurnRequest(message="I have some land in Rangpur, Bangladesh."))
    assert t1.status == "collecting_profile"
    assert t1.profile.location_text == "Rangpur"

    # Turn 2: Remaining profile parameters
    t2 = await agent.turn(
        AgentTurnRequest(
            session_id=t1.session_id,
            message="2 acres, loam soil, reliable irrigation, BDT 200000 budget, targeting Rabi.",
        )
    )
    assert t2.status == "awaiting_crop_selection"
    assert t2.profile.farm_size_acre == 2.0
    assert t2.profile.budget_bdt == 200000.0
    assert len(t2.recommendations) >= 3

    # Turn 3: Choose crop #1
    t3 = await agent.turn(
        AgentTurnRequest(
            session_id=t1.session_id,
            message="1",
        )
    )
    assert t3.status == "plan_ready"
    assert t3.plan is not None
    initial_cost = t3.plan.financial_projection.total_cost_bdt

    # Turn 4: What if budget cut by 40%? (BDT 200,000 * 0.6 = BDT 120,000)
    t4 = await agent.turn(
        AgentTurnRequest(
            session_id=t1.session_id,
            message="What if my budget is cut by 40%?",
        )
    )
    assert t4.status == "plan_ready"
    assert t4.profile.budget_bdt == 120000.0
    assert t4.plan is not None
    assert t4.plan.financial_projection.budget_bdt == 120000.0


