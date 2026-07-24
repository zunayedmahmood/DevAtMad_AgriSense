from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def stable_id(*parts: object, prefix: str = "") -> str:
    payload = "::".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}{digest}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def json_loads(value: str | bytes | None, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def redact_secrets(value: Any) -> Any:
    secret_keys = {"apikey", "api_key", "authorization", "geoapify_api_key"}
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {
            key: ("***REDACTED***" if key.lower() in secret_keys else redact_secrets(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value
