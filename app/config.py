from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "sandbox"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    geoapify_api_key: str | None = None
    external_mode: str = "sandbox"
    http_timeout_seconds: float = 15.0
    weather_cache_ttl_seconds: int = 900
    geocode_cache_ttl_seconds: int = 2_592_000
    geoapify_min_confidence: float = 0.45

    # LLM Provider Configuration
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    agrisense_backend_url: str = "http://localhost:8000"

    rag_db_path: Path = BASE_DIR / "data/processed/rag.sqlite3"
    app_db_path: Path = BASE_DIR / "data/runtime/agrisense.sqlite3"
    raw_unified_kb_path: Path = BASE_DIR / "data/raw/bangladesh_agriculture_unified_knowledge.json"
    mixed_catalog_db_path: Path = BASE_DIR / "data/raw/mixed_60_40/bangladesh_agri_60_40.db"
    raw_mock_kb_dir: Path = BASE_DIR / "data/raw/mock_agri_kb"
    generated_kb_path: Path = BASE_DIR / "data/generated/generated_gap_kb.jsonl"
    generated_gazetteer_path: Path = BASE_DIR / "data/generated/mock_location_centroids.json"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    max_followup_fields: int = 6
    default_forecast_days: int = 7
    allow_admin_rebuild: bool = False

    @field_validator("external_mode")
    @classmethod
    def validate_external_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"live", "sandbox", "offline"}:
            raise ValueError("EXTERNAL_MODE must be live, sandbox, or offline")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def ensure_directories(self) -> None:
        for path in (self.rag_db_path, self.app_db_path, self.generated_kb_path):
            path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
