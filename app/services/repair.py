from __future__ import annotations

from typing import Any
from app.schemas import SeasonPlan


class RepairService:
    """Applies deterministic repairs to draft season plans."""

    def apply(self, plan: SeasonPlan, repair_codes: list[str], context: dict[str, Any] | None = None) -> SeasonPlan:
        repaired = plan.model_copy(deep=True)

        for code in repair_codes:
            if code == "FINANCE_RECOMPUTE":
                if repaired.financial_projection:
                    fin = repaired.financial_projection
                    cost = fin.total_cost_bdt or 0.0
                    rev = fin.expected_revenue_bdt or 0.0
                    profit = rev - cost
                    roi = (profit / cost * 100.0) if cost > 0 else 0.0
                    fin.net_profit_bdt = round(profit, 2)
                    fin.roi_percent = round(roi, 2)

            elif code == "PLAN_DATE_REBUILD":
                if repaired.planned_sowing_date and repaired.expected_harvest_date:
                    if repaired.planned_sowing_date > repaired.expected_harvest_date:
                        # Swap or fix harvest date
                        from datetime import timedelta
                        repaired.expected_harvest_date = repaired.planned_sowing_date + timedelta(days=90)

        return repaired
