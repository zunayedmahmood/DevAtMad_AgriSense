from __future__ import annotations

import inspect
import time
import uuid
from collections.abc import Callable
from typing import Any

from app.db import AppDatabase
from app.utils import redact_secrets


class TraceRecorder:
    """Records operational tool calls and decision inputs, not hidden chain-of-thought."""

    def __init__(self, database: AppDatabase, session_id: str, trace_id: str | None = None):
        self.database = database
        self.session_id = session_id
        self.trace_id = trace_id or str(uuid.uuid4())
        self.step_no = 0

    async def call(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        function: Callable[[], Any],
        *,
        source_kind: str,
    ) -> Any:
        self.step_no += 1
        started = time.perf_counter()
        try:
            result = function()
            if inspect.isawaitable(result):
                result = await result
            status = "success"
            return result
        except Exception as exc:
            result = {"error": type(exc).__name__, "message": str(exc)}
            status = "error"
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            self.database.write_trace(
                trace_id=self.trace_id,
                session_id=self.session_id,
                step_no=self.step_no,
                tool_name=tool_name,
                parameters=redact_secrets(parameters),
                result=redact_secrets(result),
                status=status,
                duration_ms=duration_ms,
                source_kind=source_kind,
            )
