from __future__ import annotations

from enum import Enum


class AgentState(str, Enum):
    RECEIVED = "received"
    SAFETY_CHECK = "safety_check"
    LOAD_MEMORY = "load_memory"
    PARSE_INTAKE = "parse_intake"
    RESOLVE_MEMORY = "resolve_memory"
    NEEDS_INPUT = "needs_input"
    RESOLVE_LOCATION = "resolve_location"
    FETCH_WEATHER = "fetch_weather"
    RETRIEVE_EVIDENCE = "retrieve_evidence"
    ASSESS_EVIDENCE = "assess_evidence"
    RANK_CROPS = "rank_crops"
    AWAIT_CROP_SELECTION = "await_crop_selection"
    BUILD_PLAN = "build_plan"
    RUN_SCENARIO = "run_scenario"
    VERIFY = "verify"
    REPAIR = "repair"
    ABSTAIN = "abstain"
    COMMIT = "commit"
    SYNTHESIZE = "synthesize"
    COMPLETE = "complete"
    FAILED = "failed"


TERMINAL_STATES = {
    AgentState.NEEDS_INPUT,
    AgentState.AWAIT_CROP_SELECTION,
    AgentState.COMPLETE,
    AgentState.ABSTAIN,
    AgentState.FAILED,
}
