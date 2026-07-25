from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.services.mixed_catalog import MixedCatalogRepository
from app.services.rag import HybridRAGStore


def main() -> None:
    settings = get_settings()
    catalog = MixedCatalogRepository(settings.mixed_catalog_db_path)
    rag = HybridRAGStore(settings.rag_db_path)
    catalog_stats = catalog.stats()
    rag_stats = rag.stats()

    checks = {
        "catalog_products_100": catalog_stats["products"] == 100,
        "catalog_product_ratio_60_40": (
            catalog_stats["authentic_products"] == 60
            and catalog_stats["synthetic_products"] == 40
        ),
        "catalog_rag_ratio_60_40": (
            catalog_stats["authentic_rag_documents"] == 180
            and catalog_stats["synthetic_rag_documents"] == 120
        ),
        "rag_ingested_300_catalog_documents": (
            rag_stats["metadata"].get("mixed_catalog_documents") == "300"
        ),
        "banglish_alias_lookup": (
            bool(catalog.search_products("begun", limit=1))
            and catalog.search_products("begun", limit=1)[0]["product_id"] == "brinjal"
        ),
        "bangla_alias_lookup": (
            bool(catalog.search_products("বেগুন", limit=1))
            and catalog.search_products("বেগুন", limit=1)[0]["product_id"] == "brinjal"
        ),
        "synthetic_hidden_by_default": catalog.search_products("synthetic", limit=100) == [],
        "rice_alias_not_polluted": [
            item["product_id"] for item in catalog.search_products("rice", limit=10)
        ]
        == ["rice"],
    }
    output = {
        "status": "ok" if all(checks.values()) else "failed",
        "checks": checks,
        "catalog": {
            "products": catalog_stats["products"],
            "authentic_products": catalog_stats["authentic_products"],
            "synthetic_products": catalog_stats["synthetic_products"],
            "rag_documents": catalog_stats["rag_documents"],
        },
        "hybrid_rag_documents": rag_stats["documents"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
