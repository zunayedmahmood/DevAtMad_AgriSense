from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from app.config import Settings, get_settings
from app.services.mixed_catalog import MixedCatalogRepository
from app.services.rag import initialize_rag_schema, insert_documents
from app.utils import json_dumps, slugify, utc_now_iso


CROP_DURATIONS = {
    "rice_boro": 145,
    "rice_aman": 135,
    "maize": 120,
    "wheat": 115,
    "potato": 100,
    "jute": 120,
    "sugarcane": 330,
    "mustard": 90,
    "soybean": 105,
    "lentil": 100,
    "mungbean": 75,
    "onion": 120,
    "garlic": 135,
    "chilli": 150,
    "tomato": 120,
    "brinjal": 180,
}

SOURCE_TO_MOCK_CROP = {
    "rice": ["rice_boro", "rice_aman"],
    "rice_boro": ["rice_boro"],
    "rice_aman": ["rice_aman"],
    "maize": ["maize"],
    "maize_rabi": ["maize"],
    "maize_kharif_1": ["maize"],
    "wheat": ["wheat"],
    "potato": ["potato"],
    "jute": ["jute"],
    "sugarcane": ["sugarcane"],
    "mustard": ["mustard"],
    "rapeseed_and_mustard": ["mustard"],
    "soybean": ["soybean"],
    "lentil": ["lentil"],
    "mungbean": ["mungbean"],
    "mungbean_blackgram": ["mungbean"],
    "onion": ["onion"],
    "onion_garlic": ["onion", "garlic"],
    "garlic": ["garlic"],
    "chilli": ["chilli"],
    "tomato": ["tomato"],
    "brinjal": ["brinjal"],
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_generated_gap_data(settings: Settings, crop_master: list[dict[str, Any]]) -> None:
    settings.generated_kb_path.parent.mkdir(parents=True, exist_ok=True)
    docs: list[dict[str, Any]] = []
    for crop in crop_master:
        crop_id = crop["crop_id"]
        duration = CROP_DURATIONS[crop_id]
        stage_offsets = {
            "land_preparation_start_day": -14,
            "sowing_day": 0,
            "early_growth_checkpoint_day": max(10, round(duration * 0.12)),
            "vegetative_checkpoint_day": round(duration * 0.30),
            "reproductive_checkpoint_day": round(duration * 0.62),
            "pre_harvest_checkpoint_day": max(1, duration - 14),
            "harvest_day": duration,
        }
        docs.append(
            {
                "document_id": f"generated::duration::{crop_id}",
                "title": f"Generated mock stage duration for {crop['crop_name']}",
                "knowledge_type": "generated_crop_duration",
                "content": (
                    f"Synthetic planning assumption for {crop['crop_name']}: {duration} days from "
                    "sowing or transplanting to expected harvest. Stage checkpoints are generated "
                    "for demo calendar arithmetic and must not be treated as field guidance."
                ),
                "metadata": {"crop_id": crop_id, "duration_days_mock": duration, "stage_offsets": stage_offsets},
                "is_mock": True,
                "source": "AgriSense generated gap layer",
            }
        )

    shared = [
        {
            "document_id": "generated::season_aliases",
            "title": "Generated Bangladesh season and month aliases",
            "knowledge_type": "generated_season_aliases",
            "content": (
                "Synthetic normalization rules: rabi/dry/winter generally maps to November-March; "
                "kharif-1/pre-monsoon generally maps to March-June; kharif-2/monsoon generally maps "
                "to July-October. Crop-specific source calendars override these aliases."
            ),
            "metadata": {
                "aliases": {
                    "rabi": [11, 12, 1, 2, 3],
                    "rabi_dry": [11, 12, 1, 2, 3],
                    "kharif": [3, 4, 5, 6, 7, 8, 9, 10],
                    "kharif_1": [3, 4, 5, 6],
                    "kharif_2": [7, 8, 9, 10],
                    "kharif_monsoon": [7, 8, 9, 10],
                    "year_round": list(range(1, 13)),
                }
            },
            "is_mock": True,
            "source": "AgriSense generated gap layer",
        },
        {
            "document_id": "generated::water_capacity_safeguard",
            "title": "Water-capacity clarification safeguard",
            "knowledge_type": "generated_agent_safeguard",
            "content": (
                "Do not infer reliable irrigation merely because a farmer owns one pump or says it "
                "draws a good amount of water. For multi-acre farms, ask whether the system can irrigate "
                "the full area within two to three days, the approximate pump discharge or pipe size, "
                "hours available per day, and whether the source remains available through the season."
            ),
            "metadata": {"applies_when": "pump mentioned and capacity is not quantified"},
            "is_mock": True,
            "source": "AgriSense generated gap layer",
        },
        {
            "document_id": "generated::weather_horizon_rule",
            "title": "Live-weather horizon rule",
            "knowledge_type": "generated_agent_safeguard",
            "content": (
                "Use the live forecast only for dates covered by the returned API horizon. Future calendar "
                "tasks beyond the forecast horizon must be marked for a weather refresh; never invent rain "
                "or temperature for those dates."
            ),
            "metadata": {"forecast_horizon_days": 7},
            "is_mock": True,
            "source": "AgriSense generated gap layer",
        },
        {
            "document_id": "generated::financial_source_policy",
            "title": "Mock financial-data policy",
            "knowledge_type": "generated_financial_policy",
            "content": (
                "All crop input costs, prices, yields, revenue and profit values from the super mock KB are "
                "synthetic. Calculations may be arithmetically exact while the assumptions remain mock. "
                "Every response must label them and allow inputs to be replaced."
            ),
            "metadata": {"currency": "BDT", "area_unit": "acre"},
            "is_mock": True,
            "source": "AgriSense generated gap layer",
        },
        {
            "document_id": "generated::unit_conversions",
            "title": "Generated demo land-unit conversions",
            "knowledge_type": "generated_unit_conversion",
            "content": (
                "Demo conversion assumptions: 1 decimal or shotok = 0.01 acre; 1 hectare = 2.47105 acres; "
                "1 Bangladesh bigha = 0.3306 acre. Confirm local bigha conventions before field use."
            ),
            "metadata": {"decimal_to_acre": 0.01, "hectare_to_acre": 2.47105, "bigha_to_acre": 0.3306},
            "is_mock": True,
            "source": "AgriSense generated gap layer",
        },
    ]
    docs.extend(shared)
    with settings.generated_kb_path.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")


def build_mock_gazetteer(settings: Settings, districts: list[dict[str, Any]], upazilas: list[dict[str, Any]]) -> None:
    """Create deterministic, explicitly mock coordinates for offline demos only."""
    gazetteer: dict[str, Any] = {"warning": "Synthetic coordinates; Geoapify should be used in live mode.", "places": {}}
    for index, district in enumerate(districts):
        district_name = district["district_name"]
        digest = int(hashlib.sha256(district_name.encode()).hexdigest()[:12], 16)
        # Deterministic points inside a broad Bangladesh bounding box; not actual centroids.
        lat = 20.75 + ((digest % 4900) / 1000.0)
        lon = 88.05 + (((digest // 4900) % 4200) / 1000.0)
        lat = min(lat, 26.65)
        lon = min(lon, 92.65)
        gazetteer["places"][district_name.lower()] = {
            "district": district_name,
            "upazila": None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "source": "generated_mock_coordinate",
        }
    for upazila in upazilas:
        key = f"{upazila['upazila_name']}, {next((d['district_name'] for d in districts if d['district_id'] == upazila['district_id']), upazila['district_id'])}".lower()
        district_entry = gazetteer["places"].get(key.split(", ", 1)[1])
        if not district_entry:
            continue
        digest = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        offset_lat = ((digest % 101) - 50) / 5000
        offset_lon = (((digest // 101) % 101) - 50) / 5000
        gazetteer["places"][key] = {
            "district": key.split(", ", 1)[1].title(),
            "upazila": upazila["upazila_name"],
            "lat": round(district_entry["lat"] + offset_lat, 6),
            "lon": round(district_entry["lon"] + offset_lon, 6),
            "source": "generated_mock_coordinate",
        }
    settings.generated_gazetteer_path.write_text(json.dumps(gazetteer, ensure_ascii=False, indent=2), encoding="utf-8")


def unified_document(record: dict[str, Any]) -> dict[str, Any]:
    crop = record["crop"]
    location = record["location"]
    primary = crop.get("primary_crop_id") or crop.get("crop_ids", [None])[0]
    profile = crop.get("profile_id")
    zone = crop.get("zone_id")
    crop_id = profile or zone or primary
    crop_group = primary
    canonical = crop.get("canonical_name") or primary
    district = location.get("district_name")
    upazila = location.get("upazila_name")
    if record["knowledge_type"] == "district_crop_agronomic":
        agr = record["agronomic_data"]
        calendar = agr.get("cultivation_calendar", {})
        climate = agr.get("climate_profile", {})
        stats = agr.get("district_crop_statistics", {})
        season = agr.get("season", {}).get("normalized_name")
        planting = calendar.get("transplant_or_planting_period", {}).get("normalized_text")
        growth = calendar.get("growth_period", {}).get("normalized_text")
        harvest = calendar.get("harvest_period", {}).get("normalized_text")
        temp = climate.get("temperature_celsius", {})
        humidity = climate.get("relative_humidity_percent", {})
        content = (
            f"Source-derived district agronomy record for {canonical} in {district}. Season: {season}. "
            f"Planting or transplanting period: {planting}; growth period: {growth}; harvest period: {harvest}. "
            f"Temperature profile: average {temp.get('average')} C, minimum {temp.get('minimum')} C, maximum {temp.get('maximum')} C. "
            f"Relative humidity normalized range {humidity.get('minimum_normalized')} to {humidity.get('maximum_normalized')} percent. "
            f"Cultivated area {stats.get('cultivated_area_acres')} acres, production {stats.get('production_metric_tonnes')} metric tonnes, "
            f"yield {stats.get('yield_metric_tonnes_per_acre')} metric tonnes per acre."
        )
        title = f"{canonical} agronomy in {district}"
    else:
        suit = record["suitability_data"]
        metrics = suit.get("derived_metrics", {})
        shares = suit.get("suitability_share_percent", {})
        content = (
            f"Source-derived crop suitability record for {canonical} in {upazila}, {district}. "
            f"Weighted suitability score: {metrics.get('weighted_suitability_score_0_100')} out of 100. "
            f"Dominant classes: {', '.join(metrics.get('dominant_suitability_classes', []))}. "
            f"Very suitable or suitable share: {metrics.get('very_suitable_or_suitable_percent')} percent; "
            f"moderately suitable or better: {metrics.get('moderately_suitable_or_better_percent')} percent. "
            f"Class shares: {json.dumps(shares, ensure_ascii=False)}. The weighted score is derived for retrieval and ranking convenience."
        )
        title = f"{canonical} suitability in {upazila}, {district}"
    return {
        "document_id": record["record_id"],
        "title": title,
        "content": content,
        "source": record["source_id"],
        "source_kind": "provided_source_derived",
        "is_mock": False,
        "crop_id": crop_id,
        "crop_group": crop_group,
        "district": district,
        "upazila": upazila,
        "knowledge_type": record["knowledge_type"],
        "metadata_json": json_dumps(
            {
                "traceability": record.get("traceability"),
                "quality": record.get("quality"),
                "crop_ids": crop.get("crop_ids", []),
                "profile_id": profile,
                "zone_id": zone,
            }
        ),
    }


def mock_documents(settings: Settings) -> Iterable[dict[str, Any]]:
    for path in sorted(settings.raw_mock_kb_dir.glob("*.jsonl")):
        if path.name.startswith("example_") or path.name == "farmer_profiles_mock.jsonl":
            continue
        for index, row in enumerate(load_jsonl(path), 1):
            crop_id = row.get("crop_id")
            crop_name = crop_id.replace("_", " ").title() if crop_id else path.stem.replace("_", " ").title()

            is_public_source = (
                row.get("data_classification") == "public_source"
                or row.get("review_state") == "reviewed"
                or path.name in {"public_source_principles.jsonl", "reviewed_public_tier0_crops.jsonl"}
            )

            if is_public_source:
                publisher = row.get("publisher", "Official Public Source (BARC/DAE/AIS/BWMRI)")
                source_id = row.get("source_id", path.stem)
                title = row.get("title") or f"{publisher}: {crop_name} {row.get('topic', 'Guidance')}"

                parts = []
                if row.get("statement"):
                    parts.append(f"Official Statement: {row['statement']}")
                if row.get("section"):
                    parts.append(f"Section: {row['section']}")
                if row.get("source_locator"):
                    parts.append(f"Locator: {row['source_locator']}")
                if row.get("optimal_temperature_c"):
                    parts.append(f"Optimal Temperature Range: {row['optimal_temperature_c'][0]}–{row['optimal_temperature_c'][1]}°C")
                if row.get("critical_max_temperature_c"):
                    parts.append(f"Critical Max Temperature: {row['critical_max_temperature_c']}°C")
                if row.get("sowing_window_months"):
                    parts.append(f"Sowing Window Months: {', '.join(row['sowing_window_months'])}")
                if row.get("harvest_window_months"):
                    parts.append(f"Harvest Window Months: {', '.join(row['harvest_window_months'])}")
                if row.get("maturity_days"):
                    parts.append(f"Maturity Duration: {row['maturity_days'][0]}–{row['maturity_days'][1]} days")
                if row.get("url"):
                    parts.append(f"URL: {row['url']}")

                content = f"{title}. " + " | ".join(parts) if parts else json.dumps(row, ensure_ascii=False)

                yield {
                    "document_id": f"public::{source_id}::{crop_id or path.stem}::{index}",
                    "title": title,
                    "content": content,
                    "source": row.get("url") or row.get("publisher") or path.name,
                    "source_kind": "official_public_source",
                    "is_mock": False,
                    "crop_id": crop_id,
                    "crop_group": crop_id,
                    "district": row.get("district"),
                    "upazila": row.get("upazila"),
                    "knowledge_type": row.get("topic") or path.stem,
                    "metadata_json": json_dumps(row),
                }
            else:
                content = f"Synthetic/mock knowledge. File: {path.name}. Payload: {json.dumps(row, ensure_ascii=False)}"
                yield {
                    "document_id": f"mock::{path.stem}::{crop_id or index}::{index}",
                    "title": f"Mock {path.stem.replace('_', ' ')} for {crop_name}",
                    "content": content,
                    "source": path.name,
                    "source_kind": "provided_mock",
                    "is_mock": True,
                    "crop_id": crop_id,
                    "crop_group": crop_id,
                    "district": None,
                    "upazila": None,
                    "knowledge_type": path.stem,
                    "metadata_json": json_dumps({"payload": row}),
                }


def generated_documents(settings: Settings) -> Iterable[dict[str, Any]]:
    for row in load_jsonl(settings.generated_kb_path):
        metadata = row.get("metadata", {})
        crop_id = metadata.get("crop_id")
        yield {
            "document_id": row["document_id"],
            "title": row["title"],
            "content": row["content"],
            "source": row["source"],
            "source_kind": "generated_mock_gap",
            "is_mock": True,
            "crop_id": crop_id,
            "crop_group": crop_id,
            "district": None,
            "upazila": None,
            "knowledge_type": row["knowledge_type"],
            "metadata_json": json_dumps(metadata),
        }


def build_compact_lookup(settings: Settings, unified: dict[str, Any]) -> None:
    district_agronomy: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    upazila_suitability: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in unified["records"]:
        crop = record["crop"]
        primary = crop.get("primary_crop_id")
        candidates = set(SOURCE_TO_MOCK_CROP.get(primary, []))
        for extra in (crop.get("profile_id"), crop.get("zone_id")):
            if extra:
                candidates.update(SOURCE_TO_MOCK_CROP.get(extra, []))
        candidates.update(crop_id for crop_id in crop.get("crop_ids", []) if crop_id in CROP_DURATIONS)
        if not candidates:
            continue
        loc = record["location"]
        district_key = loc["district_name"].lower()
        if record["knowledge_type"] == "district_crop_agronomic":
            agr = record["agronomic_data"]
            compact = {
                "record_id": record["record_id"],
                "source_id": record["source_id"],
                "profile_id": crop.get("profile_id"),
                "season": agr.get("season", {}).get("normalized_name"),
                "calendar": agr.get("cultivation_calendar"),
                "climate": agr.get("climate_profile"),
                "statistics": agr.get("district_crop_statistics"),
            }
            for candidate in candidates:
                district_agronomy[candidate][district_key].append(compact)
        else:
            suit = record["suitability_data"]
            compact = {
                "record_id": record["record_id"],
                "source_id": record["source_id"],
                "weighted_suitability_score_0_100": suit.get("derived_metrics", {}).get("weighted_suitability_score_0_100"),
                "dominant_suitability_classes": suit.get("derived_metrics", {}).get("dominant_suitability_classes", []),
                "very_suitable_or_suitable_percent": suit.get("derived_metrics", {}).get("very_suitable_or_suitable_percent"),
                "moderately_suitable_or_better_percent": suit.get("derived_metrics", {}).get("moderately_suitable_or_better_percent"),
            }
            key = f"{district_key}::{loc['upazila_name'].lower()}"
            for candidate in candidates:
                upazila_suitability[candidate][key] = compact
    output = {
        "district_agronomy": {crop: dict(rows) for crop, rows in district_agronomy.items()},
        "upazila_suitability": {crop: dict(rows) for crop, rows in upazila_suitability.items()},
        "generated_at": utc_now_iso(),
    }
    path = settings.rag_db_path.parent / "agronomy_lookup.json"
    path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")


def build_rag(settings: Settings, force: bool = False) -> dict[str, Any]:
    if settings.rag_db_path.exists() and not force:
        return {"status": "skipped", "path": str(settings.rag_db_path)}
    unified = json.loads(settings.raw_unified_kb_path.read_text(encoding="utf-8"))
    crop_master = load_jsonl(settings.raw_mock_kb_dir / "crop_master.jsonl")
    build_generated_gap_data(settings, crop_master)
    build_mock_gazetteer(settings, unified["catalogs"]["districts"], unified["catalogs"]["upazilas"])
    build_compact_lookup(settings, unified)

    temporary = settings.rag_db_path.with_suffix(".building.sqlite3")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        initialize_rag_schema(connection)
        source_count = insert_documents(connection, (unified_document(record) for record in unified["records"]))
        mock_count = insert_documents(connection, mock_documents(settings))
        generated_count = insert_documents(connection, generated_documents(settings))
        mixed_catalog = MixedCatalogRepository(settings.mixed_catalog_db_path)
        mixed_catalog_count = insert_documents(connection, mixed_catalog.iter_rag_documents())
        metadata = {
            "built_at": utc_now_iso(),
            "embedding": "deterministic_blake2b_hash_384",
            "retrieval": "sqlite_fts5_plus_cosine",
            "provided_source_documents": str(source_count),
            "provided_mock_documents": str(mock_count),
            "generated_mock_gap_documents": str(generated_count),
            "mixed_catalog_documents": str(mixed_catalog_count),
            "mixed_catalog_db_path": str(settings.mixed_catalog_db_path),
        }
        connection.executemany("INSERT INTO rag_metadata(key,value) VALUES(?,?)", metadata.items())
        connection.commit()
    finally:
        connection.close()
    settings.rag_db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary.replace(settings.rag_db_path)
    return {
        "status": "built",
        "path": str(settings.rag_db_path),
        "provided_source_documents": source_count,
        "provided_mock_documents": mock_count,
        "generated_mock_gap_documents": generated_count,
        "mixed_catalog_documents": mixed_catalog_count,
    }
