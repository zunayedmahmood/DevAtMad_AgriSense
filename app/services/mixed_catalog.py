from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from app.utils import json_dumps, json_loads


_QUERY_SPACE_RE = re.compile(r"\s+")
_REQUIRED_TABLES = {
    "products",
    "product_aliases",
    "product_varieties",
    "agronomic_summaries",
    "fertilizer_summaries",
    "regional_profiles",
    "codebase_crop_mapping",
    "rag_documents",
    "metadata",
    "validation_metrics",
}


def normalize_catalog_query(value: str) -> str:
    """Normalize English, Banglish, and Bangla lookup text without dropping Unicode."""
    value = value.casefold().strip().replace("-", " ").replace("_", " ")
    value = re.sub(r"[^\w\u0980-\u09ff]+", " ", value, flags=re.UNICODE)
    return _QUERY_SPACE_RE.sub(" ", value).strip()


class MixedCatalogRepository:
    """Read-only access to the 60% authentic / 40% synthetic crop catalog.

    The catalog database is deliberately separate from the runtime user/session database.
    Synthetic rows are excluded by default and are never marked planner-eligible.
    """

    def __init__(self, path: Path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.exists():
            raise FileNotFoundError(
                f"Mixed agricultural catalog not found at {self.path}. "
                "Restore data/raw/mixed_60_40/bangladesh_agri_60_40.db."
            )
        self._validate_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.path.as_posix()}?mode=ro",
            uri=True,
            timeout=30,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _validate_schema(self) -> None:
        with self.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                ).fetchall()
            }
            missing = sorted(_REQUIRED_TABLES - tables)
            if missing:
                raise RuntimeError(f"Mixed catalog schema is incomplete; missing: {', '.join(missing)}")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"Mixed catalog integrity check failed: {integrity}")

    @staticmethod
    def _parse_json_columns(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
        for key in keys:
            if key in payload:
                payload[key.removesuffix("_json")] = json_loads(payload.pop(key), [])
        return payload

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            product_rows = connection.execute(
                """
                SELECT data_origin, is_synthetic, COUNT(*) AS count
                FROM products
                GROUP BY data_origin, is_synthetic
                ORDER BY is_synthetic, data_origin
                """
            ).fetchall()
            document_rows = connection.execute(
                """
                SELECT source_kind, is_mock, COUNT(*) AS count
                FROM rag_documents
                GROUP BY source_kind, is_mock
                ORDER BY is_mock, source_kind
                """
            ).fetchall()
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS products,
                    SUM(CASE WHEN is_synthetic = 0 THEN 1 ELSE 0 END) AS authentic_products,
                    SUM(CASE WHEN is_synthetic = 1 THEN 1 ELSE 0 END) AS synthetic_products,
                    SUM(CASE WHEN eligible_for_recommendation = 1 THEN 1 ELSE 0 END) AS planner_eligible_products,
                    SUM(CASE WHEN safe_for_prescriptive_advice = 1 THEN 1 ELSE 0 END) AS prescriptive_products
                FROM products
                """
            ).fetchone()
            rag_totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS documents,
                    SUM(CASE WHEN is_mock = 0 THEN 1 ELSE 0 END) AS authentic_documents,
                    SUM(CASE WHEN is_mock = 1 THEN 1 ELSE 0 END) AS synthetic_documents,
                    SUM(CASE WHEN safe_for_prescriptive_advice = 1 THEN 1 ELSE 0 END) AS prescriptive_documents
                FROM rag_documents
                """
            ).fetchone()
            metadata = {
                row["key"]: json_loads(row["value_json"], row["value_json"])
                for row in connection.execute("SELECT key, value_json FROM metadata")
            }
            validation = {
                row["metric"]: json_loads(row["value_json"], row["value_json"])
                for row in connection.execute("SELECT metric, value_json FROM validation_metrics")
            }

        product_total = int(totals["products"] or 0)
        document_total = int(rag_totals["documents"] or 0)
        return {
            "path": str(self.path),
            "mode": "read_only",
            "products": product_total,
            "authentic_products": int(totals["authentic_products"] or 0),
            "synthetic_products": int(totals["synthetic_products"] or 0),
            "authentic_product_ratio": round(
                int(totals["authentic_products"] or 0) / product_total, 4
            )
            if product_total
            else 0.0,
            "planner_eligible_products": int(totals["planner_eligible_products"] or 0),
            "prescriptive_products": int(totals["prescriptive_products"] or 0),
            "rag_documents": document_total,
            "authentic_rag_documents": int(rag_totals["authentic_documents"] or 0),
            "synthetic_rag_documents": int(rag_totals["synthetic_documents"] or 0),
            "authentic_rag_ratio": round(
                int(rag_totals["authentic_documents"] or 0) / document_total, 4
            )
            if document_total
            else 0.0,
            "prescriptive_rag_documents": int(rag_totals["prescriptive_documents"] or 0),
            "by_product_origin": [dict(row) for row in product_rows],
            "by_rag_origin": [dict(row) for row in document_rows],
            "metadata": metadata,
            "validation": validation,
            "safety_policy": {
                "default_lookup": "authentic_only",
                "synthetic_visibility": "explicit_opt_in",
                "synthetic_prescriptive_use": "blocked",
                "planner_gate": "codebase_crop_mapping.enabled_for_planning=1",
            },
        }

    def _aliases_for_products(
        self, connection: sqlite3.Connection, product_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        if not product_ids:
            return {}
        placeholders = ",".join("?" for _ in product_ids)
        rows = connection.execute(
            f"""
            SELECT product_id, alias_text, normalized_alias, language_code, script,
                   alias_type, data_origin, is_ambiguous
            FROM product_aliases
            WHERE product_id IN ({placeholders})
            ORDER BY product_id, is_ambiguous, alias_type, alias_text
            """,
            product_ids,
        ).fetchall()
        output: dict[str, list[dict[str, Any]]] = {product_id: [] for product_id in product_ids}
        for row in rows:
            item = dict(row)
            item["is_ambiguous"] = bool(item["is_ambiguous"])
            output[row["product_id"]].append(item)
        return output

    def _mappings_for_products(
        self, connection: sqlite3.Connection, product_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        if not product_ids:
            return {}
        placeholders = ",".join("?" for _ in product_ids)
        rows = connection.execute(
            f"""
            SELECT product_id, codebase_crop_id, mapping_type, enabled_for_planning
            FROM codebase_crop_mapping
            WHERE product_id IN ({placeholders})
            ORDER BY product_id, codebase_crop_id
            """,
            product_ids,
        ).fetchall()
        output: dict[str, list[dict[str, Any]]] = {product_id: [] for product_id in product_ids}
        for row in rows:
            item = dict(row)
            item["enabled_for_planning"] = bool(item["enabled_for_planning"])
            output[row["product_id"]].append(item)
        return output

    @staticmethod
    def _product_payload(
        row: sqlite3.Row,
        aliases: list[dict[str, Any]],
        mappings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = dict(row)
        for key in (
            "is_synthetic",
            "safe_for_identity_lookup",
            "safe_for_prescriptive_advice",
            "eligible_for_recommendation",
        ):
            payload[key] = bool(payload[key])
        payload["aliases"] = aliases
        payload["codebase_mappings"] = mappings
        payload["planner_supported"] = any(
            mapping["enabled_for_planning"] for mapping in mappings
        )
        payload["display_badges"] = [
            "Synthetic test data" if payload["is_synthetic"] else "Authentic source-derived",
            "Planner-supported" if payload["planner_supported"] else "Lookup only",
        ]
        return payload

    def search_products(
        self,
        query: str = "",
        *,
        include_synthetic: bool = False,
        eligible_only: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        normalized = normalize_catalog_query(query)
        filters = ["1=1"]
        params: list[Any] = []
        if not include_synthetic:
            filters.append("p.is_synthetic = 0")
        if eligible_only:
            filters.append("p.eligible_for_recommendation = 1")

        with self.connect() as connection:
            if normalized:
                like = f"%{normalized}%"
                prefix = f"{normalized}%"
                filters.append(
                    """
                    (
                        LOWER(REPLACE(REPLACE(p.canonical_name_en, '-', ' '), '_', ' ')) LIKE ?
                        OR LOWER(REPLACE(REPLACE(COALESCE(p.canonical_name_bn, ''), '-', ' '), '_', ' ')) LIKE ?
                        OR EXISTS (
                            SELECT 1 FROM product_aliases a
                            WHERE a.product_id = p.product_id
                              AND a.is_ambiguous = 0
                              AND (a.normalized_alias = ? OR a.normalized_alias LIKE ? OR a.normalized_alias LIKE ?)
                        )
                    )
                    """
                )
                params.extend([like, like, normalized, prefix, like])
                order_sql = """
                    ORDER BY
                        CASE WHEN LOWER(REPLACE(REPLACE(p.canonical_name_en, '-', ' '), '_', ' ')) = ? THEN 0
                             WHEN LOWER(REPLACE(REPLACE(COALESCE(p.canonical_name_bn, ''), '-', ' '), '_', ' ')) = ? THEN 0
                             WHEN EXISTS (SELECT 1 FROM product_aliases ea WHERE ea.product_id=p.product_id AND ea.is_ambiguous=0 AND ea.normalized_alias=?) THEN 1
                             WHEN LOWER(p.canonical_name_en) LIKE ? THEN 2
                             ELSE 3 END,
                        p.is_synthetic,
                        p.canonical_name_en
                """
                order_params = [normalized, normalized, normalized, prefix]
            else:
                order_sql = "ORDER BY p.is_synthetic, p.eligible_for_recommendation DESC, p.canonical_name_en"
                order_params = []

            rows = connection.execute(
                f"""
                SELECT p.*
                FROM products p
                WHERE {' AND '.join(filters)}
                {order_sql}
                LIMIT ?
                """,
                [*params, *order_params, limit],
            ).fetchall()
            product_ids = [row["product_id"] for row in rows]
            aliases = self._aliases_for_products(connection, product_ids)
            mappings = self._mappings_for_products(connection, product_ids)

        return [
            self._product_payload(row, aliases.get(row["product_id"], []), mappings.get(row["product_id"], []))
            for row in rows
        ]

    def get_product(
        self, product_id: str, *, include_synthetic: bool = False
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
            if not row or (bool(row["is_synthetic"]) and not include_synthetic):
                return None
            aliases = self._aliases_for_products(connection, [product_id]).get(product_id, [])
            mappings = self._mappings_for_products(connection, [product_id]).get(product_id, [])
            product = self._product_payload(row, aliases, mappings)

            varieties = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT variety_id, variety_name, season_context, yield_goal_raw, data_origin,
                           source_record_id, source_page, safe_for_prescriptive_advice
                    FROM product_varieties
                    WHERE product_id = ?
                    ORDER BY variety_name
                    """,
                    (product_id,),
                ).fetchall()
            ]
            for variety in varieties:
                variety["safe_for_prescriptive_advice"] = bool(
                    variety["safe_for_prescriptive_advice"]
                )

            agronomic_row = connection.execute(
                "SELECT * FROM agronomic_summaries WHERE product_id = ?", (product_id,)
            ).fetchone()
            agronomic = dict(agronomic_row) if agronomic_row else None
            if agronomic:
                self._parse_json_columns(
                    agronomic,
                    "seasons_json",
                    "planting_periods_json",
                    "growth_periods_json",
                    "harvest_periods_json",
                    "temperature_profiles_json",
                    "humidity_profiles_json",
                )
                agronomic["safe_for_prescriptive_advice"] = bool(
                    agronomic["safe_for_prescriptive_advice"]
                )

            fertilizer_row = connection.execute(
                "SELECT * FROM fertilizer_summaries WHERE product_id = ?", (product_id,)
            ).fetchone()
            fertilizer = dict(fertilizer_row) if fertilizer_row else None
            if fertilizer:
                self._parse_json_columns(fertilizer, "rates_json")
                fertilizer["safe_for_prescriptive_advice"] = bool(
                    fertilizer["safe_for_prescriptive_advice"]
                )

            regional_profiles = []
            for item in connection.execute(
                """
                SELECT profile_id, district_name, upazila_name, metric_type, metric_value,
                       metric_unit, profile_json, data_origin, source_record_id,
                       safe_for_prescriptive_advice
                FROM regional_profiles
                WHERE product_id = ?
                ORDER BY district_name, upazila_name, metric_type
                LIMIT 100
                """,
                (product_id,),
            ).fetchall():
                payload = dict(item)
                payload["profile"] = json_loads(payload.pop("profile_json"), {})
                payload["safe_for_prescriptive_advice"] = bool(
                    payload["safe_for_prescriptive_advice"]
                )
                regional_profiles.append(payload)

        product.update(
            {
                "varieties": varieties,
                "agronomic_summary": agronomic,
                "fertilizer_summary": fertilizer,
                "regional_profiles": regional_profiles,
            }
        )
        return product

    def iter_rag_documents(self) -> Iterable[dict[str, Any]]:
        """Yield catalog documents in the existing HybridRAGStore ingestion format."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.*, p.data_origin, p.is_synthetic, p.eligible_for_recommendation,
                       p.canonical_name_en, p.canonical_name_bn
                FROM rag_documents r
                JOIN products p ON p.product_id = r.product_id
                ORDER BY r.document_id
                """
            ).fetchall()
            mappings = self._mappings_for_products(
                connection, sorted({row["product_id"] for row in rows})
            )

        for row in rows:
            metadata = json_loads(row["metadata_json"], {}) or {}
            product_mappings = mappings.get(row["product_id"], [])
            metadata.update(
                {
                    "catalog_product_id": row["product_id"],
                    "catalog_data_origin": row["data_origin"],
                    "catalog_is_synthetic": bool(row["is_synthetic"]),
                    "safe_for_prescriptive_advice": bool(
                        row["safe_for_prescriptive_advice"]
                    ),
                    "eligible_for_recommendation": bool(
                        row["eligible_for_recommendation"]
                    ),
                    "codebase_crop_ids": [
                        mapping["codebase_crop_id"]
                        for mapping in product_mappings
                        if mapping["enabled_for_planning"]
                    ],
                    "canonical_name_en": row["canonical_name_en"],
                    "canonical_name_bn": row["canonical_name_bn"],
                }
            )
            yield {
                "document_id": row["document_id"],
                "title": row["title"],
                "content": row["content"],
                "source": row["source"],
                "source_kind": row["source_kind"],
                "is_mock": bool(row["is_mock"]),
                "crop_id": row["crop_id"],
                "crop_group": row["crop_group"],
                "district": row["district"],
                "upazila": row["upazila"],
                "knowledge_type": row["knowledge_type"],
                "metadata_json": json_dumps(metadata),
                "safe_for_prescriptive_advice": bool(
                    row["safe_for_prescriptive_advice"]
                ),
            }
