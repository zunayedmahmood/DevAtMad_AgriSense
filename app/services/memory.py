from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.db import AppDatabase
from app.schemas import FarmProfile, MemoryConflictItem, SavedFarmSummary
from app.utils import normalize_space


DURABLE_FARM_FIELDS = {
    "location_text",
    "district",
    "upazila",
    "latitude",
    "longitude",
    "geocode_source",
    "geocode_confidence",
    "farm_size_acre",
    "farm_size_input",
    "soil_type",
    "water_availability",
    "water_details",
    "water_capacity_confirmed",
    "budget_bdt",
    "previous_crop",
    "risk_tolerance",
    "language",
}

SESSION_ONLY_FIELDS = {
    "target_season",
    "target_month",
    "target_year",
    "chosen_crop_id",
}

NEVER_AUTO_RESTORE_FIELDS = {
    "chosen_crop_id",
}


@dataclass
class MemoryConflict:
    field_name: str
    saved_value: Any
    current_value: Any
    question: str


@dataclass
class MemoryLookupResult:
    status: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_farm: dict[str, Any] | None = None
    conflicts: list[MemoryConflict] = field(default_factory=list)


class MemoryService:
    def __init__(self, database: AppDatabase):
        self.database = database

    def find_candidate_farms(
        self,
        farmer_id: str,
        parsed_profile: FarmProfile | None = None,
        farm_id_hint: str | None = None,
    ) -> list[SavedFarmSummary]:
        farms = self.database.list_farms(farmer_id, include_archived=False)
        if not farms:
            return []

        summaries: list[SavedFarmSummary] = []
        for f in farms:
            p = f.get("profile") or {}
            latest_plan = self.database.get_latest_plan(f["farm_id"])
            last_crop = latest_plan["crop_id"] if latest_plan else None

            summaries.append(
                SavedFarmSummary(
                    farm_id=f["farm_id"],
                    farm_name=f["farm_name"],
                    location_text=p.get("location_text"),
                    district=p.get("district"),
                    farm_size_acre=p.get("farm_size_acre"),
                    soil_type=p.get("soil_type"),
                    water_availability=p.get("water_availability"),
                    last_used_at=f.get("last_used_at"),
                    last_plan_crop_id=last_crop,
                )
            )

        if farm_id_hint:
            matched = [s for s in summaries if s.farm_id == farm_id_hint]
            if matched:
                return matched

        if not parsed_profile:
            return summaries

        district_match = []
        if parsed_profile.district:
            target_d = parsed_profile.district.lower()
            district_match = [
                s for s in summaries if s.district and s.district.lower() == target_d
            ]
            if district_match:
                return district_match

        location_match = []
        if parsed_profile.location_text:
            loc_clean = normalize_space(parsed_profile.location_text.lower())
            location_match = [
                s
                for s in summaries
                if s.location_text
                and (
                    loc_clean in s.location_text.lower()
                    or s.location_text.lower() in loc_clean
                )
            ]
            if location_match:
                return location_match

        return summaries

    def durable_snapshot(self, profile: FarmProfile) -> FarmProfile:
        data = profile.model_dump(mode="json")
        filtered = {k: v for k, v in data.items() if k in DURABLE_FARM_FIELDS}
        return FarmProfile.model_validate(filtered)

    def apply_saved_memory(
        self,
        saved: FarmProfile,
        current: FarmProfile,
    ) -> tuple[FarmProfile, list[str]]:
        data = current.model_dump(mode="json")
        applied: list[str] = []

        for field_name in DURABLE_FARM_FIELDS:
            saved_val = getattr(saved, field_name)
            current_val = getattr(current, field_name)

            if current_val is None and saved_val is not None:
                data[field_name] = saved_val
                applied.append(field_name)

        data["chosen_crop_id"] = current.chosen_crop_id

        return FarmProfile.model_validate(data), applied

    def detect_conflicts(
        self,
        saved: FarmProfile,
        incoming: FarmProfile,
    ) -> list[MemoryConflictItem]:
        conflicts: list[MemoryConflictItem] = []

        # Location conflict
        if (
            incoming.district
            and saved.district
            and incoming.district.lower() != saved.district.lower()
        ):
            conflicts.append(
                MemoryConflictItem(
                    field_name="district",
                    saved_value=saved.district,
                    incoming_value=incoming.district,
                    question=f"Your saved farm is in {saved.district}, but this request specifies {incoming.district}. Is this a permanent location update or a new farm?",
                )
            )

        # Farm size conflict (> 1% variation)
        if saved.farm_size_acre and incoming.farm_size_acre:
            diff = abs(saved.farm_size_acre - incoming.farm_size_acre)
            ratio = diff / saved.farm_size_acre
            if ratio > 0.01:
                conflicts.append(
                    MemoryConflictItem(
                        field_name="farm_size_acre",
                        saved_value=saved.farm_size_acre,
                        incoming_value=incoming.farm_size_acre,
                        question=f"Your saved farm size is {saved.farm_size_acre} acres, but your input states {incoming.farm_size_acre} acres. Choose whether to permanently update the farm size, use {incoming.farm_size_acre} acres temporarily for this session, or create a new farm.",
                    )
                )

        # Soil type conflict
        if (
            incoming.soil_type
            and saved.soil_type
            and incoming.soil_type.lower() != saved.soil_type.lower()
        ):
            conflicts.append(
                MemoryConflictItem(
                    field_name="soil_type",
                    saved_value=saved.soil_type,
                    incoming_value=incoming.soil_type,
                    question=f"Your saved soil type is {saved.soil_type}, but your input specifies {incoming.soil_type}. Is this a permanent soil update or temporary scenario?",
                )
            )

        # Water availability conflict
        if (
            incoming.water_availability
            and saved.water_availability
            and incoming.water_availability.lower()
            != saved.water_availability.lower()
        ):
            conflicts.append(
                MemoryConflictItem(
                    field_name="water_availability",
                    saved_value=saved.water_availability,
                    incoming_value=incoming.water_availability,
                    question=f"Your saved irrigation status is '{saved.water_availability}', but your input specifies '{incoming.water_availability}'. Update permanently or use temporarily?",
                )
            )

        return conflicts

    def save_confirmed_farm_memory(
        self,
        *,
        farmer_id: str,
        farm_id: str | None,
        profile: FarmProfile,
        session_id: str,
        farm_name: str | None = None,
    ) -> str:
        durable = self.durable_snapshot(profile)
        loc = durable.location_text or durable.district or "Bangladesh Farm"
        name = farm_name or f"{loc} Farm"

        if farm_id:
            existing = self.database.get_farm(farm_id, farmer_id)
            if existing:
                saved_prof = FarmProfile.model_validate(existing["profile"])
                merged, applied = self.apply_saved_memory(saved_prof, durable)
                self.database.update_farm_profile(
                    farm_id=farm_id,
                    farmer_id=farmer_id,
                    profile=merged,
                    expected_version=existing["profile_version"],
                )
                self.database.attach_session_to_farm(
                    session_id, farmer_id, farm_id, memory_status="updated"
                )
                self.database.add_memory_event(
                    farmer_id=farmer_id,
                    farm_id=farm_id,
                    session_id=session_id,
                    event_type="field_updated",
                    new_value=merged.model_dump(mode="json"),
                    reason="Updated confirmed durable farm facts",
                )
                return farm_id

        new_farm_id = self.database.create_farm(
            farmer_id=farmer_id, farm_name=name, profile=durable
        )
        self.database.attach_session_to_farm(
            session_id, farmer_id, new_farm_id, memory_status="applied"
        )
        self.database.add_memory_event(
            farmer_id=farmer_id,
            farm_id=new_farm_id,
            session_id=session_id,
            event_type="farm_created",
            new_value=durable.model_dump(mode="json"),
            reason="Saved new durable farm profile",
        )
        return new_farm_id

    def build_session_summary(self, session: dict[str, Any]) -> dict[str, Any]:
        prof = session.get("profile") or {}
        return {
            "session_id": session.get("session_id"),
            "farm_id": session.get("farm_id"),
            "location_text": prof.get("location_text"),
            "farm_size_acre": prof.get("farm_size_acre"),
            "soil_type": prof.get("soil_type"),
            "water_availability": prof.get("water_availability"),
            "budget_bdt": prof.get("budget_bdt"),
            "target_season": prof.get("target_season"),
            "chosen_crop_id": session.get("selected_crop_id"),
            "status": session.get("session_status", "active"),
            "important_warnings": [
                "Future weather-sensitive tasks require forecast refresh prior to execution"
            ],
        }
