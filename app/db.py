from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from app.schemas import FarmProfile
from app.utils import json_dumps, json_loads, utc_now_iso


class AppDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    recommendations_json TEXT,
                    selected_crop_id TEXT,
                    plan_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    step_no INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    result_json TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    source_kind TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_trace_session ON tool_traces(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_trace_id ON tool_traces(trace_id, step_no);
                CREATE TABLE IF NOT EXISTS external_cache (
                    cache_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    expires_at_epoch INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_session(self, profile: FarmProfile | None = None) -> str:
        session_id = str(uuid.uuid4())
        now = utc_now_iso()
        payload = (profile or FarmProfile()).model_dump(mode="json")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(session_id, profile_json, created_at, updated_at) VALUES(?,?,?,?)",
                (session_id, json_dumps(payload), now, now),
            )
        return session_id

    def ensure_session(self, session_id: str | None) -> str:
        if not session_id:
            return self.create_session()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row:
            return session_id
        now = utc_now_iso()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(session_id, profile_json, created_at, updated_at) VALUES(?,?,?,?)",
                (session_id, json_dumps(FarmProfile().model_dump(mode="json")), now, now),
            )
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "profile": json_loads(row["profile_json"], {}),
            "recommendations": json_loads(row["recommendations_json"], []),
            "selected_crop_id": row["selected_crop_id"],
            "plan": json_loads(row["plan_json"], None),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def save_profile(self, session_id: str, profile: FarmProfile) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET profile_json = ?, updated_at = ? WHERE session_id = ?",
                (json_dumps(profile.model_dump(mode="json")), utc_now_iso(), session_id),
            )

    def save_recommendations(self, session_id: str, recommendations: list[dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET recommendations_json = ?, updated_at = ? WHERE session_id = ?",
                (json_dumps(recommendations), utc_now_iso(), session_id),
            )

    def save_plan(self, session_id: str, crop_id: str, plan: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET selected_crop_id = ?, plan_json = ?, updated_at = ? WHERE session_id = ?",
                (crop_id, json_dumps(plan), utc_now_iso(), session_id),
            )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES(?,?,?,?)",
                (session_id, role, content, utc_now_iso()),
            )

    def list_messages(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def delete_session(self, session_id: str) -> bool:
        with self.connect() as connection:
            result = connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        return result.rowcount > 0

    def write_trace(
        self,
        *,
        trace_id: str,
        session_id: str,
        step_no: int,
        tool_name: str,
        parameters: dict[str, Any],
        result: Any,
        status: str,
        duration_ms: float,
        source_kind: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_traces(
                    trace_id, session_id, step_no, tool_name, parameters_json, result_json,
                    status, duration_ms, source_kind, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    trace_id,
                    session_id,
                    step_no,
                    tool_name,
                    json_dumps(parameters),
                    json_dumps(result),
                    status,
                    duration_ms,
                    source_kind,
                    utc_now_iso(),
                ),
            )

    def get_trace(self, session_id: str, trace_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tool_traces WHERE session_id = ?"
        params: list[Any] = [session_id]
        if trace_id:
            query += " AND trace_id = ?"
            params.append(trace_id)
        query += " ORDER BY id"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "trace_id": row["trace_id"],
                "step_no": row["step_no"],
                "tool_name": row["tool_name"],
                "parameters": json_loads(row["parameters_json"], {}),
                "raw_result": json_loads(row["result_json"], None),
                "status": row["status"],
                "duration_ms": row["duration_ms"],
                "source_kind": row["source_kind"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def cache_get(self, key: str, now_epoch: int) -> Any | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value_json, expires_at_epoch FROM external_cache WHERE cache_key = ?", (key,)
            ).fetchone()
        if not row or row["expires_at_epoch"] < now_epoch:
            return None
        return json_loads(row["value_json"], None)

    def cache_set(self, key: str, value: Any, expires_at_epoch: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO external_cache(cache_key, value_json, expires_at_epoch, created_at)
                VALUES(?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    value_json=excluded.value_json,
                    expires_at_epoch=excluded.expires_at_epoch,
                    created_at=excluded.created_at
                """,
                (key, json_dumps(value), expires_at_epoch, utc_now_iso()),
            )
