from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


class KnowledgeRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mock_dir = settings.raw_mock_kb_dir
        self.generated_path = settings.generated_kb_path
        self._load()

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _indexed(self, filename: str) -> dict[str, Any]:
        return {row["crop_id"]: row for row in self._load_jsonl(self.mock_dir / filename)}

    def _load(self) -> None:
        self.crop_master = self._indexed("crop_master.jsonl")
        self.crop_calendar = self._indexed("crop_calendar.jsonl")
        self.suitability_rules = self._indexed("crop_suitability_rules.jsonl")
        self.economics = self._indexed("economics_mock.jsonl")
        self.fertilizer = self._indexed("fertilizer_plans.jsonl")
        self.irrigation = self._indexed("irrigation_plans.jsonl")
        self.stage_plans = self._indexed("stage_plans.jsonl")
        self.pests: dict[str, list[dict[str, Any]]] = {}
        for row in self._load_jsonl(self.mock_dir / "pest_disease_risks.jsonl"):
            self.pests.setdefault(row["crop_id"], []).append(row)
        self.agent_rules = json.loads((self.mock_dir / "agent_rules.json").read_text(encoding="utf-8"))
        self.input_prices = json.loads(
            (self.mock_dir / "input_price_defaults_mock.json").read_text(encoding="utf-8")
        )

        self.generated_docs = self._load_jsonl(self.generated_path)
        self.generated_by_type: dict[str, list[dict[str, Any]]] = {}
        for row in self.generated_docs:
            self.generated_by_type.setdefault(row.get("knowledge_type", "unknown"), []).append(row)
        self.duration_by_crop = {
            row["metadata"]["crop_id"]: row["metadata"]
            for row in self.generated_by_type.get("generated_crop_duration", [])
        }

        manifest_path = self.mock_dir / "source_manifest.json"
        self.source_manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        )
        self.public_principles = self._load_jsonl(self.mock_dir / "public_source_principles.jsonl")
        self.reviewed_crops = self._load_jsonl(self.mock_dir / "reviewed_public_tier0_crops.jsonl")

        compact_path = self.settings.rag_db_path.parent / "agronomy_lookup.json"
        self.agronomy_lookup = (
            json.loads(compact_path.read_text(encoding="utf-8")) if compact_path.exists() else {}
        )
        gazetteer_path = self.settings.generated_gazetteer_path
        self.gazetteer = (
            json.loads(gazetteer_path.read_text(encoding="utf-8")) if gazetteer_path.exists() else {}
        )

    @property
    def supported_crop_ids(self) -> list[str]:
        return list(self.crop_master)

    def crop_name(self, crop_id: str) -> str:
        return self.crop_master.get(crop_id, {}).get("crop_name", crop_id.replace("_", " ").title())

    def get_crop_bundle(self, crop_id: str) -> dict[str, Any]:
        if crop_id not in self.crop_master:
            raise KeyError(f"Unsupported crop_id: {crop_id}")
        return {
            "master": self.crop_master[crop_id],
            "calendar": self.crop_calendar.get(crop_id, {}),
            "suitability": self.suitability_rules.get(crop_id, {}),
            "economics": self.economics.get(crop_id, {}),
            "fertilizer": self.fertilizer.get(crop_id, {}),
            "irrigation": self.irrigation.get(crop_id, {}),
            "stage_plan": self.stage_plans.get(crop_id, {}),
            "pests": self.pests.get(crop_id, []),
            "duration": self.duration_by_crop.get(crop_id, {}),
        }

    def district_agronomy(self, crop_id: str, district: str | None) -> list[dict[str, Any]]:
        if not district:
            return []
        return (
            self.agronomy_lookup.get("district_agronomy", {})
            .get(crop_id, {})
            .get(district.lower(), [])
        )

    def suitability(self, crop_id: str, district: str | None, upazila: str | None) -> dict[str, Any] | None:
        data = self.agronomy_lookup.get("upazila_suitability", {}).get(crop_id, {})
        if upazila and district:
            exact = data.get(f"{district.lower()}::{upazila.lower()}")
            if exact:
                return exact
        if district:
            district_rows = [row for key, row in data.items() if key.startswith(district.lower() + "::")]
            if district_rows:
                values = [
                    row.get("weighted_suitability_score_0_100")
                    for row in district_rows
                    if row.get("weighted_suitability_score_0_100") is not None
                ]
                if values:
                    return {
                        "weighted_suitability_score_0_100": sum(values) / len(values),
                        "dominant_suitability_classes": ["district_average"],
                        "aggregation": "mean of supplied upazila suitability scores",
                        "records": len(values),
                    }
        return None


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeRepository:
    return KnowledgeRepository(get_settings())
