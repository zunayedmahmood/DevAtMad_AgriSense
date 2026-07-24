from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FarmProfile(StrictModel):
    location_text: str | None = None
    district: str | None = None
    upazila: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geocode_source: str | None = None
    geocode_confidence: float | None = None

    farm_size_acre: float | None = Field(default=None, gt=0, le=100_000)
    farm_size_input: str | None = None
    soil_type: str | None = None
    water_availability: str | None = None
    water_details: str | None = None
    water_capacity_confirmed: bool | None = None
    budget_bdt: float | None = Field(default=None, gt=0)
    target_season: str | None = None
    target_month: int | None = Field(default=None, ge=1, le=12)
    target_year: int | None = Field(default=None, ge=2020, le=2100)
    chosen_crop_id: str | None = None
    previous_crop: str | None = None
    risk_tolerance: str | None = None
    language: str = "en"

    @field_validator("soil_type", "water_availability", "target_season", mode="before")
    @classmethod
    def normalize_enums(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower().replace("-", "_").replace(" ", "_")
        return value


class ProfilePatch(StrictModel):
    location_text: str | None = None
    district: str | None = None
    upazila: str | None = None
    farm_size_acre: float | None = Field(default=None, gt=0, le=100_000)
    soil_type: str | None = None
    water_availability: str | None = None
    water_capacity_confirmed: bool | None = None
    budget_bdt: float | None = Field(default=None, gt=0)
    target_season: str | None = None
    target_month: int | None = Field(default=None, ge=1, le=12)
    target_year: int | None = Field(default=None, ge=2020, le=2100)
    chosen_crop_id: str | None = None
    previous_crop: str | None = None
    risk_tolerance: str | None = None


class SavedFarmSummary(StrictModel):
    farm_id: str
    farm_name: str
    location_text: str | None = None
    district: str | None = None
    farm_size_acre: float | None = None
    soil_type: str | None = None
    water_availability: str | None = None
    last_used_at: str | None = None
    last_plan_crop_id: str | None = None


class MemoryConflictItem(StrictModel):
    field_name: str
    saved_value: Any
    incoming_value: Any
    question: str


class MemoryContext(StrictModel):
    status: Literal[
        "none",
        "offered",
        "applied",
        "declined",
        "conflict",
        "updated",
    ] = "none"
    farmer_id: str | None = None
    farm_id: str | None = None
    saved_farms: list[SavedFarmSummary] = Field(default_factory=list)
    applied_fields: list[str] = Field(default_factory=list)
    conflicts: list[MemoryConflictItem] = Field(default_factory=list)
    recent_session_summaries: list[dict[str, Any]] = Field(default_factory=list)


class AgentTurnRequest(StrictModel):
    session_id: str | None = None
    farmer_id: str | None = None
    farm_id: str | None = None
    memory_action: Literal[
        "apply",
        "decline",
        "create_new",
        "confirm_update",
        "reject_update",
        "use_temporarily",
    ] | None = None
    message: str = Field(min_length=1, max_length=5000)
    profile_patch: ProfilePatch | None = None
    auto_select_top_crop: bool = False
    force_refresh_weather: bool = False


class SourceEvidence(StrictModel):
    document_id: str
    title: str
    source: str
    source_kind: str
    is_mock: bool
    score: float
    snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CropRecommendation(StrictModel):
    rank: int
    crop_id: str
    crop_name: str
    suitability_score: float
    suitability_label: str
    water_need: str
    risk_level: str
    estimated_total_cost_bdt: float
    estimated_revenue_bdt: float
    estimated_net_profit_bdt: float
    roi_percent: float
    budget_fit: str
    reasons: list[str]
    warnings: list[str]
    evidence: list[SourceEvidence] = Field(default_factory=list)
    data_status: Literal["mixed_real_and_mock", "mock"] = "mixed_real_and_mock"
    eligible: bool = True
    season_compatible: bool = True
    hard_eligibility_reasons: list[str] = Field(default_factory=list)


class FinancialProjection(StrictModel):
    crop_id: str
    crop_name: str
    area_acre: float
    cost_components_bdt: dict[str, float]
    total_cost_bdt: float
    budget_bdt: float
    budget_surplus_or_gap_bdt: float
    expected_yield_kg_per_acre: float
    total_expected_yield_kg: float
    expected_price_bdt_per_kg: float
    expected_revenue_bdt: float
    net_profit_bdt: float
    roi_percent: float
    break_even_price_bdt_per_kg: float
    break_even_yield_kg: float
    scenario_projection: dict[str, dict[str, float]]
    assumptions: list[str]
    math_trace: list[str]
    data_status: Literal["mock_economics"] = "mock_economics"


class PlanTask(StrictModel):
    task_id: str
    stage: str
    start_date: date
    end_date: date | None = None
    action: str
    quantity: str | None = None
    condition: str | None = None
    reasoning: list[str]
    source_tags: list[str]
    weather_refresh_required: bool = False


class SeasonPlan(StrictModel):
    crop_id: str
    crop_name: str
    planned_sowing_date: date
    expected_harvest_date: date
    tasks: list[PlanTask]
    fertilizer_summary_kg_for_farm: dict[str, float]
    irrigation_summary: dict[str, Any]
    pest_watchlist: list[dict[str, Any]]
    financial_projection: FinancialProjection
    plan_assumptions: list[str]
    evidence: list[SourceEvidence] = Field(default_factory=list)
    weather_temporally_relevant: bool = False
    plan_marked_provisional: bool = True
    weather_adjustments: list[str] = Field(default_factory=list)
    fertilizer_split_reconciliation_passed: bool = True
    financial_reconciliation_passed: bool = True
    validation_status: dict[str, Any] = Field(default_factory=dict)


class ToolTraceItem(StrictModel):
    step_no: int
    tool_name: str
    parameters: dict[str, Any]
    raw_result: Any
    status: str
    duration_ms: float
    source_kind: str
    created_at: str


class AgentTurnResponse(StrictModel):
    session_id: str
    trace_id: str
    status: Literal[
        "collecting_profile",
        "needs_location_confirmation",
        "needs_memory_confirmation",
        "needs_memory_conflict_resolution",
        "awaiting_crop_selection",
        "plan_ready",
        "error",
    ]
    message: str
    missing_fields: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    profile: FarmProfile
    memory: MemoryContext = Field(default_factory=MemoryContext)
    recommendations: list[CropRecommendation] = Field(default_factory=list)
    selected_crop_id: str | None = None
    plan: SeasonPlan | None = None
    decision_summary: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    trace: list[ToolTraceItem] = Field(default_factory=list)


class ToolInvokeRequest(StrictModel):
    session_id: str | None = None
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class RAGSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=50)
    crop_id: str | None = None
    district: str | None = None
    upazila: str | None = None
    source_kind: str | None = None
    include_mock: bool = True


class SignUpRequest(StrictModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=4, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    subscription_tier: Literal["free", "pro", "enterprise"] = "free"


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=100)


class SubscriptionUpdateRequest(StrictModel):
    farmer_id: str
    subscription_tier: Literal["free", "pro", "enterprise"]


class AuthResponse(StrictModel):
    farmer_id: str
    email: str
    full_name: str
    subscription_tier: str
    subscription_status: str
    created_at: str


class ChatSessionSummary(StrictModel):
    session_id: str
    farmer_id: str
    farm_id: str | None = None
    title: str
    memory_status: str = "none"
    message_count: int = 0
    last_message: str | None = None
    created_at: str
    updated_at: str


class CreateChatSessionRequest(StrictModel):
    farmer_id: str
    farm_id: str | None = None
    title: str | None = None


class UpdateSessionTitleRequest(StrictModel):
    farmer_id: str
    title: str
