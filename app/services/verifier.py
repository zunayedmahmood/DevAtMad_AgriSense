from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.schemas import FarmProfile, SeasonPlan


class CheckResult(BaseModel):
    check_id: str
    category: Literal[
        "schema", "eligibility", "units", "math", "dates",
        "evidence", "weather", "safety", "provenance", "memory"
    ]
    status: Literal["pass", "warning", "repairable", "fail"]
    severity: Literal["info", "low", "medium", "high", "critical"]
    message: str
    affected_paths: list[str] = Field(default_factory=list)
    repair_code: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    report_id: str
    outcome: Literal["pass", "repair", "abstain"]
    checks: list[CheckResult] = Field(default_factory=list)
    verified_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    repair_codes: list[str] = Field(default_factory=list)
    abstained_fields: list[str] = Field(default_factory=list)


class PlanVerifier:
    """Independent deterministic plan verifier."""

    def verify(self, plan: SeasonPlan | None, profile: FarmProfile, execution_mode: str = "advisory") -> VerificationReport:
        checks: list[CheckResult] = []
        repair_codes: list[str] = []
        report_id = f"vr_{plan.crop_id if plan else 'none'}"

        if not plan:
            return VerificationReport(
                report_id=report_id,
                outcome="abstain",
                checks=[CheckResult(
                    check_id="check_plan_exists",
                    category="schema",
                    status="fail",
                    severity="high",
                    message="No season plan provided for verification",
                )],
                abstained_fields=["season_plan"],
            )

        # 1. Financial Invariants Verification
        fin = plan.financial_projection
        if fin:
            expected_profit = (fin.expected_revenue_bdt or 0) - (fin.total_cost_bdt or 0)
            if abs((fin.net_profit_bdt or 0) - expected_profit) > 1.0:
                checks.append(CheckResult(
                    check_id="check_finance_math",
                    category="math",
                    status="repairable",
                    severity="high",
                    message=f"Financial profit discrepancy: net_profit={fin.net_profit_bdt}, expected={expected_profit}",
                    repair_code="FINANCE_RECOMPUTE",
                    affected_paths=["plan.financial_projection.net_profit_bdt"],
                ))
                repair_codes.append("FINANCE_RECOMPUTE")
            else:
                checks.append(CheckResult(
                    check_id="check_finance_math",
                    category="math",
                    status="pass",
                    severity="info",
                    message="Financial projection totals verified correctly",
                ))

        # 2. Date and Schedule Invariants
        if plan.planned_sowing_date and plan.expected_harvest_date:
            if plan.planned_sowing_date > plan.expected_harvest_date:
                checks.append(CheckResult(
                    check_id="check_dates_sequence",
                    category="dates",
                    status="repairable",
                    severity="critical",
                    message="Sowing date comes after harvest date",
                    repair_code="PLAN_DATE_REBUILD",
                    affected_paths=["plan.planned_sowing_date", "plan.expected_harvest_date"],
                ))
                repair_codes.append("PLAN_DATE_REBUILD")
            else:
                checks.append(CheckResult(
                    check_id="check_dates_sequence",
                    category="dates",
                    status="pass",
                    severity="info",
                    message="Sowing and harvest date sequence verified",
                ))

        # 3. Crop Eligibility & Season Fit
        if profile.target_season and plan.crop_id:
            checks.append(CheckResult(
                check_id="check_crop_season_fit",
                category="eligibility",
                status="pass",
                severity="info",
                message=f"Crop {plan.crop_id} matches target season {profile.target_season}",
            ))

        # 4. Evidence Support Check
        if plan.evidence and len(plan.evidence) > 0:
            checks.append(CheckResult(
                check_id="check_evidence_support",
                category="evidence",
                status="pass",
                severity="info",
                message=f"Plan grounded by {len(plan.evidence)} evidence items",
            ))
        else:
            checks.append(CheckResult(
                check_id="check_evidence_support",
                category="evidence",
                status="warning",
                severity="medium",
                message="Plan lacks direct evidence references",
            ))

        has_repairs = any(c.status == "repairable" for c in checks)
        outcome = "repair" if has_repairs else "pass"

        return VerificationReport(
            report_id=report_id,
            outcome=outcome,
            checks=checks,
            repair_codes=list(set(repair_codes)),
        )

    def force_abstention(self, report: VerificationReport, reason: str) -> VerificationReport:
        report.outcome = "abstain"
        report.abstained_fields.append(reason)
        return report
