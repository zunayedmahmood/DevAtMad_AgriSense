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

