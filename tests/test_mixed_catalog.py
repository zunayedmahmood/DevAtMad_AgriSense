from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.ingestion import build_rag
from app.services.mixed_catalog import MixedCatalogRepository
from app.services.rag import HybridRAGStore


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/raw/mixed_60_40/bangladesh_agri_60_40.db"


def repository() -> MixedCatalogRepository:
    return MixedCatalogRepository(CATALOG_PATH)


def test_mixed_catalog_integrity_and_exact_ratios():
    repo = repository()
    stats = repo.stats()
    assert stats["products"] == 100
    assert stats["authentic_products"] == 60
    assert stats["synthetic_products"] == 40
    assert stats["authentic_product_ratio"] == 0.6
    assert stats["rag_documents"] == 300
    assert stats["authentic_rag_documents"] == 180
    assert stats["synthetic_rag_documents"] == 120
    assert stats["authentic_rag_ratio"] == 0.6

    with repo.connect() as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_catalog_default_filter_and_multilingual_aliases():
    repo = repository()
    assert repo.search_products("synthetic", limit=100) == []

    for query in ("brinjal", "begun", "বেগুন"):
        results = repo.search_products(query, limit=5)
        assert results
        assert results[0]["product_id"] == "brinjal"
        assert results[0]["is_synthetic"] is False
        assert results[0]["planner_supported"] is True

    synthetic = repo.search_products("synthetic", include_synthetic=True, limit=100)
    assert synthetic
    assert all(item["is_synthetic"] for item in synthetic)
    assert all(not item["eligible_for_recommendation"] for item in synthetic)
    assert all(not item["safe_for_prescriptive_advice"] for item in synthetic)


def test_ambiguous_alias_does_not_pollute_catalog_search():
    results = repository().search_products("rice", limit=10)
    assert [item["product_id"] for item in results] == ["rice"]


def test_catalog_product_detail_preserves_safety_and_mapping():
    repo = repository()
    product = repo.get_product("rice")
    assert product is not None
    assert product["is_synthetic"] is False
    assert product["planner_supported"] is True
    assert {item["codebase_crop_id"] for item in product["codebase_mappings"]} == {
        "rice_aman",
        "rice_boro",
    }
    assert product["aliases"]
    assert product["varieties"]
    assert product["agronomic_summary"]
    assert product["fertilizer_summary"]

    synthetic_id = repository().search_products(
        "synthetic", include_synthetic=True, limit=1
    )[0]["product_id"]
    assert repo.get_product(synthetic_id) is None
    synthetic = repo.get_product(synthetic_id, include_synthetic=True)
    assert synthetic is not None
    assert synthetic["is_synthetic"] is True
    assert synthetic["planner_supported"] is False


def test_rag_rebuild_ingests_catalog_and_keeps_synthetic_filter(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        external_mode="offline",
        app_db_path=tmp_path / "runtime.sqlite3",
        rag_db_path=tmp_path / "rag.sqlite3",
        raw_unified_kb_path=ROOT / "data/raw/bangladesh_agriculture_unified_knowledge.json",
        raw_mock_kb_dir=ROOT / "data/raw/mock_agri_kb",
        mixed_catalog_db_path=CATALOG_PATH,
        generated_kb_path=tmp_path / "generated_gap_kb.jsonl",
        generated_gazetteer_path=tmp_path / "mock_location_centroids.json",
    )
    result = build_rag(settings, force=True)
    assert result["mixed_catalog_documents"] == 300

    rag = HybridRAGStore(settings.rag_db_path)
    stats = rag.stats()
    assert stats["metadata"]["mixed_catalog_documents"] == "300"

    authentic = rag.search(
        "synthetic crop simulation", include_mock=False, top_k=50
    )
    assert all(not item.is_mock for item in authentic)
    mixed = rag.search(
        "synthetic crop simulation", include_mock=True, top_k=50
    )
    assert any(item.source_kind == "synthetic_mixed_catalog_40" for item in mixed)

    rice_boro = rag.search(
        "rice agronomic profile", crop_id="rice_boro", include_mock=False, top_k=20
    )
    assert any(
        item.metadata.get("catalog_product_id") == "rice" for item in rice_boro
    )

    with sqlite3.connect(settings.rag_db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(documents)")
        }
        assert "safe_for_prescriptive_advice" in columns


def test_catalog_api_defaults_to_authentic_only():
    client = TestClient(app)
    stats = client.get("/v1/catalog/stats")
    assert stats.status_code == 200
    assert stats.json()["products"] == 100

    authentic = client.get("/v1/catalog/products", params={"query": "begun"})
    assert authentic.status_code == 200
    assert authentic.json()["products"][0]["product_id"] == "brinjal"

    hidden = client.get("/v1/catalog/products", params={"query": "synthetic"})
    assert hidden.status_code == 200
    assert hidden.json()["products"] == []

    visible = client.get(
        "/v1/catalog/products",
        params={"query": "synthetic", "include_synthetic": "true", "limit": 3},
    )
    assert visible.status_code == 200
    assert len(visible.json()["products"]) == 3
    assert all(item["is_synthetic"] for item in visible.json()["products"])
