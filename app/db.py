from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

import hashlib
from app.schemas import FarmProfile
from app.utils import json_dumps, json_loads, utc_now_iso


def hash_password(password: str) -> str:
    salt = "agrisense_salt_2026"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


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

    def _column_exists(
        self,
        connection: sqlite3.Connection,
        table: str,
        column: str,
    ) -> bool:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row["name"] == column for row in rows)

    def _add_column_if_missing(
        self,
        connection: sqlite3.Connection,
        table: str,
        column: str,
        sql_type: str,
    ) -> None:
        if not self._column_exists(connection, table, column):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")

    def _migrate(self, connection: sqlite3.Connection) -> None:
        self._add_column_if_missing(connection, "sessions", "farmer_id", "TEXT")
        self._add_column_if_missing(connection, "sessions", "farm_id", "TEXT")
        self._add_column_if_missing(connection, "sessions", "title", "TEXT DEFAULT 'Farm Advisory Session'")
        self._add_column_if_missing(connection, "sessions", "memory_status", "TEXT DEFAULT 'none'")
        self._add_column_if_missing(connection, "sessions", "session_status", "TEXT DEFAULT 'active'")
        self._add_column_if_missing(connection, "sessions", "session_summary_json", "TEXT")

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
                CREATE TABLE IF NOT EXISTS users (
                    farmer_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    subscription_tier TEXT NOT NULL DEFAULT 'free',
                    subscription_status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS farmers (
                    farmer_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    identity_key TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS farms (
                    farm_id TEXT PRIMARY KEY,
                    farmer_id TEXT NOT NULL REFERENCES farmers(farmer_id),
                    farm_name TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    profile_version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT,
                    is_archived INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_farms_farmer ON farms(farmer_id, is_archived, updated_at);
                CREATE TABLE IF NOT EXISTS plan_versions (
                    plan_id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL REFERENCES farms(farm_id),
                    session_id TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
                    version_no INTEGER NOT NULL,
                    crop_id TEXT NOT NULL,
                    profile_snapshot_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_current INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(farm_id, version_no)
                );
                CREATE INDEX IF NOT EXISTS idx_plan_versions_farm ON plan_versions(farm_id, version_no DESC);
                CREATE TABLE IF NOT EXISTS memory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farmer_id TEXT NOT NULL,
                    farm_id TEXT,
                    session_id TEXT,
                    event_type TEXT NOT NULL,
                    field_name TEXT,
                    old_value_json TEXT,
                    new_value_json TEXT,
                    source_message_id INTEGER,
                    confidence REAL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_events_farm ON memory_events(farm_id, id);
                """
            )
            self._migrate(connection)

    def ensure_farmer(
        self,
        farmer_id: str | None,
        identity_key: str | None = None,
        display_name: str | None = None,
    ) -> str:
        now = utc_now_iso()
        with self.connect() as connection:
            if farmer_id:
                row = connection.execute("SELECT farmer_id FROM farmers WHERE farmer_id = ?", (farmer_id,)).fetchone()
                if row:
                    connection.execute(
                        "UPDATE farmers SET updated_at = ? WHERE farmer_id = ?",
                        (now, farmer_id),
                    )
                    return farmer_id
            
            fid = farmer_id or f"farmer_{uuid.uuid4()}"
            ikey = identity_key or fid
            dname = display_name or f"Farmer {fid[:8]}"
            connection.execute(
                "INSERT INTO farmers(farmer_id, display_name, identity_key, created_at, updated_at) VALUES(?,?,?,?,?)",
                (fid, dname, ikey, now, now),
            )
            return fid

    def create_account(
        self,
        email: str,
        password: str,
        full_name: str,
        subscription_tier: str = "free",
    ) -> dict[str, Any]:
        email_clean = email.strip().lower()
        now = utc_now_iso()
        farmer_id = f"farmer_{uuid.uuid4().hex[:12]}"
        pw_hash = hash_password(password)
        with self.connect() as connection:
            existing = connection.execute("SELECT farmer_id FROM users WHERE email = ?", (email_clean,)).fetchone()
            if existing:
                raise ValueError("An account with this email already exists.")
            connection.execute(
                """
                INSERT INTO users(farmer_id, email, password_hash, full_name, subscription_tier, subscription_status, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (farmer_id, email_clean, pw_hash, full_name, subscription_tier, "active", now, now),
            )
            connection.execute(
                "INSERT OR REPLACE INTO farmers(farmer_id, display_name, identity_key, created_at, updated_at) VALUES(?,?,?,?,?)",
                (farmer_id, full_name, email_clean, now, now),
            )
        return {
            "farmer_id": farmer_id,
            "email": email_clean,
            "full_name": full_name,
            "subscription_tier": subscription_tier,
            "subscription_status": "active",
            "created_at": now,
        }

    def authenticate_account(self, email: str, password: str) -> dict[str, Any] | None:
        email_clean = email.strip().lower()
        pw_hash = hash_password(password)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
            if not row or row["password_hash"] != pw_hash:
                return None
            return {
                "farmer_id": row["farmer_id"],
                "email": row["email"],
                "full_name": row["full_name"],
                "subscription_tier": row["subscription_tier"],
                "subscription_status": row["subscription_status"],
                "created_at": row["created_at"],
            }

    def get_account(self, farmer_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE farmer_id = ?", (farmer_id,)).fetchone()
            if not row:
                return None
            return {
                "farmer_id": row["farmer_id"],
                "email": row["email"],
                "full_name": row["full_name"],
                "subscription_tier": row["subscription_tier"],
                "subscription_status": row["subscription_status"],
                "created_at": row["created_at"],
            }

    def update_subscription(self, farmer_id: str, subscription_tier: str) -> dict[str, Any] | None:
        now = utc_now_iso()
        with self.connect() as connection:
            connection.execute(
                "UPDATE users SET subscription_tier = ?, updated_at = ? WHERE farmer_id = ?",
                (subscription_tier, now, farmer_id),
            )
        return self.get_account(farmer_id)

    def create_session(
        self,
        profile: FarmProfile | None = None,
        farmer_id: str | None = None,
        farm_id: str | None = None,
        title: str | None = None,
    ) -> str:
        session_id = str(uuid.uuid4())
        now = utc_now_iso()
        payload = (profile or FarmProfile()).model_dump(mode="json")
        session_title = title or "Farm Advisory Session"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(session_id, profile_json, farmer_id, farm_id, title, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (session_id, json_dumps(payload), farmer_id, farm_id, session_title, now, now),
            )
        return session_id

    def ensure_session(
        self,
        session_id: str | None,
        farmer_id: str | None = None,
        farm_id: str | None = None,
        title: str | None = None,
    ) -> str:
        if not session_id:
            return self.create_session(farmer_id=farmer_id, farm_id=farm_id, title=title)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT session_id, farmer_id, farm_id FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                if (farmer_id and row["farmer_id"] != farmer_id) or (farm_id and row["farm_id"] != farm_id):
                    connection.execute(
                        "UPDATE sessions SET farmer_id = COALESCE(?, farmer_id), farm_id = COALESCE(?, farm_id), updated_at = ? WHERE session_id = ?",
                        (farmer_id, farm_id, utc_now_iso(), session_id),
                    )
                return session_id
        
        now = utc_now_iso()
        session_title = title or "Farm Advisory Session"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(session_id, profile_json, farmer_id, farm_id, title, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (session_id, json_dumps(FarmProfile().model_dump(mode="json")), farmer_id, farm_id, session_title, now, now),
            )
        return session_id

    def get_session(self, session_id: str, farmer_id: str | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM sessions WHERE session_id = ?"
        params: list[Any] = [session_id]
        if farmer_id:
            query += " AND farmer_id = ?"
            params.append(farmer_id)
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        if not row:
            return None
        keys = row.keys()
        return {
            "session_id": row["session_id"],
            "farmer_id": row["farmer_id"],
            "farm_id": row["farm_id"],
            "title": row["title"] if "title" in keys and row["title"] else "Farm Advisory Session",
            "memory_status": row["memory_status"] or "none",
            "session_status": row["session_status"] or "active",
            "session_summary": json_loads(row["session_summary_json"], None),
            "profile": json_loads(row["profile_json"], {}),
            "recommendations": json_loads(row["recommendations_json"], []),
            "selected_crop_id": row["selected_crop_id"],
            "plan": json_loads(row["plan_json"], None),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_sessions_for_farmer(self, farmer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.session_id, s.farmer_id, s.farm_id, s.title, s.memory_status, s.created_at, s.updated_at,
                       COUNT(m.id) as message_count,
                       (SELECT content FROM messages WHERE session_id = s.session_id ORDER BY id DESC LIMIT 1) as last_message
                FROM sessions s
                LEFT JOIN messages m ON s.session_id = m.session_id
                WHERE s.farmer_id = ?
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (farmer_id, limit),
            ).fetchall()
        return [
            {
                "session_id": row["session_id"],
                "farmer_id": row["farmer_id"],
                "farm_id": row["farm_id"],
                "title": row["title"] or "Farm Advisory Session",
                "memory_status": row["memory_status"] or "none",
                "message_count": row["message_count"],
                "last_message": row["last_message"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def update_session_title(self, session_id: str, farmer_id: str, title: str) -> bool:
        with self.connect() as connection:
            res = connection.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ? AND farmer_id = ?",
                (title, utc_now_iso(), session_id, farmer_id),
            )
            return res.rowcount > 0

    def create_farm(
        self,
        farmer_id: str,
        farm_name: str,
        profile: FarmProfile | dict[str, Any],
    ) -> str:
        farm_id = f"farm_{uuid.uuid4()}"
        now = utc_now_iso()
        prof_dict = profile.model_dump(mode="json") if isinstance(profile, FarmProfile) else profile
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO farms(farm_id, farmer_id, farm_name, profile_json, profile_version, created_at, updated_at, last_used_at, is_archived)
                VALUES(?,?,?,?,1,?,?,?,0)
                """,
                (farm_id, farmer_id, farm_name, json_dumps(prof_dict), now, now, now),
            )
        return farm_id

    def get_farm(self, farm_id: str, farmer_id: str | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM farms WHERE farm_id = ? AND is_archived = 0"
        params: list[Any] = [farm_id]
        if farmer_id:
            query += " AND farmer_id = ?"
            params.append(farmer_id)
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        if not row:
            return None
        return {
            "farm_id": row["farm_id"],
            "farmer_id": row["farmer_id"],
            "farm_name": row["farm_name"],
            "profile": json_loads(row["profile_json"], {}),
            "profile_version": row["profile_version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_used_at": row["last_used_at"],
            "is_archived": bool(row["is_archived"]),
        }

    def list_farms(self, farmer_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM farms WHERE farmer_id = ?"
        params: list[Any] = [farmer_id]
        if not include_archived:
            query += " AND is_archived = 0"
        query += " ORDER BY updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "farm_id": row["farm_id"],
                "farmer_id": row["farmer_id"],
                "farm_name": row["farm_name"],
                "profile": json_loads(row["profile_json"], {}),
                "profile_version": row["profile_version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "last_used_at": row["last_used_at"],
                "is_archived": bool(row["is_archived"]),
            }
            for row in rows
        ]

    def update_farm_profile(
        self,
        *,
        farm_id: str,
        farmer_id: str,
        profile: FarmProfile | dict[str, Any],
        expected_version: int | None = None,
    ) -> int:
        now = utc_now_iso()
        prof_dict = profile.model_dump(mode="json") if isinstance(profile, FarmProfile) else profile
        with self.connect() as connection:
            if expected_version is not None:
                res = connection.execute(
                    """
                    UPDATE farms
                    SET profile_json = ?, profile_version = profile_version + 1, updated_at = ?, last_used_at = ?
                    WHERE farm_id = ? AND farmer_id = ? AND profile_version = ?
                    """,
                    (json_dumps(prof_dict), now, now, farm_id, farmer_id, expected_version),
                )
            else:
                res = connection.execute(
                    """
                    UPDATE farms
                    SET profile_json = ?, profile_version = profile_version + 1, updated_at = ?, last_used_at = ?
                    WHERE farm_id = ? AND farmer_id = ?
                    """,
                    (json_dumps(prof_dict), now, now, farm_id, farmer_id),
                )
            return res.rowcount

    def attach_session_to_farm(
        self,
        session_id: str,
        farmer_id: str,
        farm_id: str,
        memory_status: str = "applied",
    ) -> None:
        now = utc_now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET farmer_id = ?, farm_id = ?, memory_status = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (farmer_id, farm_id, memory_status, now, session_id),
            )
            connection.execute(
                "UPDATE farms SET last_used_at = ?, updated_at = ? WHERE farm_id = ?",
                (now, now, farm_id),
            )

    def set_session_memory_status(self, session_id: str, memory_status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET memory_status = ?, updated_at = ? WHERE session_id = ?",
                (memory_status, utc_now_iso(), session_id),
            )

    def save_session_summary(self, session_id: str, summary: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET session_summary_json = ?, updated_at = ? WHERE session_id = ?",
                (json_dumps(summary), utc_now_iso(), session_id),
            )

    def save_plan_version(
        self,
        *,
        farm_id: str,
        session_id: str,
        crop_id: str,
        profile_snapshot: dict[str, Any],
        plan: dict[str, Any],
    ) -> str:
        plan_id = f"plan_{uuid.uuid4()}"
        now = utc_now_iso()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version_no), 0) as max_v FROM plan_versions WHERE farm_id = ?",
                (farm_id,),
            ).fetchone()
            next_version = (row["max_v"] if row else 0) + 1
            
            connection.execute(
                "UPDATE plan_versions SET is_current = 0 WHERE farm_id = ?", (farm_id,)
            )
            connection.execute(
                """
                INSERT INTO plan_versions(
                    plan_id, farm_id, session_id, version_no, crop_id,
                    profile_snapshot_json, plan_json, created_at, is_current
                ) VALUES(?,?,?,?,?,?,?,?,1)
                """,
                (
                    plan_id,
                    farm_id,
                    session_id,
                    next_version,
                    crop_id,
                    json_dumps(profile_snapshot),
                    json_dumps(plan),
                    now,
                ),
            )
        return plan_id

    def get_latest_plan(self, farm_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM plan_versions WHERE farm_id = ? ORDER BY version_no DESC LIMIT 1",
                (farm_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "plan_id": row["plan_id"],
            "farm_id": row["farm_id"],
            "session_id": row["session_id"],
            "version_no": row["version_no"],
            "crop_id": row["crop_id"],
            "profile_snapshot": json_loads(row["profile_snapshot_json"], {}),
            "plan": json_loads(row["plan_json"], {}),
            "created_at": row["created_at"],
            "is_current": bool(row["is_current"]),
        }

    def list_plan_versions(self, farm_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM plan_versions WHERE farm_id = ? ORDER BY version_no DESC LIMIT ?",
                (farm_id, limit),
            ).fetchall()
        return [
            {
                "plan_id": row["plan_id"],
                "farm_id": row["farm_id"],
                "session_id": row["session_id"],
                "version_no": row["version_no"],
                "crop_id": row["crop_id"],
                "profile_snapshot": json_loads(row["profile_snapshot_json"], {}),
                "plan": json_loads(row["plan_json"], {}),
                "created_at": row["created_at"],
                "is_current": bool(row["is_current"]),
            }
            for row in rows
        ]

    def list_recent_session_summaries(self, farm_id: str, limit: int = 3) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id, session_summary_json, updated_at
                FROM sessions
                WHERE farm_id = ? AND session_summary_json IS NOT NULL
                ORDER BY updated_at DESC LIMIT ?
                """,
                (farm_id, limit),
            ).fetchall()
        return [
            {
                "session_id": row["session_id"],
                "summary": json_loads(row["session_summary_json"], {}),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def add_memory_event(
        self,
        *,
        farmer_id: str,
        farm_id: str | None = None,
        session_id: str | None = None,
        event_type: str,
        field_name: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        reason: str | None = None,
        confidence: float | None = None,
    ) -> int:
        now = utc_now_iso()
        with self.connect() as connection:
            cur = connection.execute(
                """
                INSERT INTO memory_events(
                    farmer_id, farm_id, session_id, event_type, field_name,
                    old_value_json, new_value_json, confidence, reason, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    farmer_id,
                    farm_id,
                    session_id,
                    event_type,
                    field_name,
                    json_dumps(old_value) if old_value is not None else None,
                    json_dumps(new_value) if new_value is not None else None,
                    confidence,
                    reason,
                    now,
                ),
            )
            return cur.lastrowid or 0

    def archive_farm(self, farm_id: str, farmer_id: str) -> bool:
        with self.connect() as connection:
            res = connection.execute(
                "UPDATE farms SET is_archived = 1, updated_at = ? WHERE farm_id = ? AND farmer_id = ?",
                (utc_now_iso(), farm_id, farmer_id),
            )
            return res.rowcount > 0

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
        now = utc_now_iso()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES(?,?,?,?)",
                (session_id, role, content, now),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            if role == "user":
                row = connection.execute("SELECT title FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
                if row and (not row["title"] or row["title"] in ("Farm Advisory Session", "New Farm Chat")):
                    snippet = content.strip().replace("\n", " ")
                    new_title = (snippet[:32] + "...") if len(snippet) > 32 else snippet
                    connection.execute(
                        "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                        (new_title, now, session_id),
                    )

    def list_messages(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def delete_session(self, session_id: str, farmer_id: str | None = None) -> bool:
        query = "DELETE FROM sessions WHERE session_id = ?"
        params: list[Any] = [session_id]
        if farmer_id:
            query += " AND farmer_id = ?"
            params.append(farmer_id)
        with self.connect() as connection:
            result = connection.execute(query, params)
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
