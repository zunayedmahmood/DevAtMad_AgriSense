from __future__ import annotations

from pydantic import BaseModel, Field


class RunBudget(BaseModel):
    max_tool_calls: int = 10
    max_rag_queries: int = 4
    max_llm_calls: int = 2
    max_repairs: int = 2
    max_external_retries_per_tool: int = 1
    max_clarification_rounds: int = 2
    max_elapsed_ms: int = 20_000

    used_tool_calls: int = 0
    used_rag_queries: int = 0
    used_llm_calls: int = 0
    used_repairs: int = 0

    def assert_not_exhausted(self) -> None:
        if self.used_repairs >= self.max_repairs:
            raise RuntimeError("Repair budget exhausted")
        if self.used_tool_calls >= self.max_tool_calls:
            raise RuntimeError("Tool call budget exhausted")
