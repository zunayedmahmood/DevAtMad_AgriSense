from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app.schemas import SourceEvidence
from app.utils import json_loads


_TOKEN_RE = re.compile(r"[a-z0-9_\u0980-\u09ff]+", re.IGNORECASE)

_CROP_FILTER_ALIASES = {
    "rice_boro": ("rice_boro", "rice"),
    "rice_aman": ("rice_aman", "rice"),
}


def hashed_embedding(text: str, dimensions: int = 384) -> np.ndarray:
    """Create a deterministic local embedding without downloading a model.

    This is intentionally lightweight for a hackathon sandbox. It combines token and
    adjacent-token hashes, then L2 normalizes the vector. The store also uses SQLite FTS5,
    so retrieval is hybrid lexical + vector rather than model-recall-only.
    """
    tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    vector = np.zeros(dimensions, dtype=np.float32)
    features = tokens + [f"{a}::{b}" for a, b in zip(tokens, tokens[1:])]
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, "little")
        index = raw % dimensions
        sign = 1.0 if (raw >> 8) & 1 else -1.0
        vector[index] += sign
    norm = float(np.linalg.norm(vector))
    if norm:
        vector /= norm
    return vector


def _fts_query(query: str) -> str:
    tokens = [token.lower() for token in _TOKEN_RE.findall(query) if len(token) > 1]
    if not tokens:
        return '"agriculture"'
    return " OR ".join(f'"{token}"' for token in tokens[:30])


class HybridRAGStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"RAG database not found at {self.path}. Run: python scripts/build_rag.py --force"
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            by_source = connection.execute(
                "SELECT source_kind, is_mock, COUNT(*) count FROM documents GROUP BY source_kind, is_mock"
            ).fetchall()
            metadata = connection.execute("SELECT key, value FROM rag_metadata").fetchall()
        return {
            "documents": total,
            "by_source": [dict(row) for row in by_source],
            "metadata": {row["key"]: row["value"] for row in metadata},
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        crop_id: str | None = None,
        district: str | None = None,
        upazila: str | None = None,
        source_kind: str | None = None,
        include_mock: bool = True,
    ) -> list[SourceEvidence]:
        query_vector = hashed_embedding(query)
        filters: list[str] = []
        params: list[Any] = []
        if crop_id:
            crop_values = _CROP_FILTER_ALIASES.get(crop_id, (crop_id,))
            placeholders = ",".join("?" for _ in crop_values)
            filters.append(
                f"(d.crop_id IN ({placeholders}) OR d.crop_group IN ({placeholders}))"
            )
            params.extend(crop_values)
            params.extend(crop_values)
        if district:
            filters.append("LOWER(d.district) = LOWER(?)")
            params.append(district)
        if upazila:
            filters.append("LOWER(d.upazila) = LOWER(?)")
            params.append(upazila)
        if source_kind:
            filters.append("d.source_kind = ?")
            params.append(source_kind)
        if not include_mock:
            filters.append("d.is_mock = 0")
        where = " AND " + " AND ".join(filters) if filters else ""

        sql = f"""
            SELECT d.*, bm25(documents_fts) AS bm25_score
            FROM documents_fts
            JOIN documents d ON d.document_id = documents_fts.document_id
            WHERE documents_fts MATCH ? {where}
            ORDER BY bm25_score
            LIMIT 160
        """
        with self.connect() as connection:
            try:
                rows = connection.execute(sql, [_fts_query(query), *params]).fetchall()
            except sqlite3.OperationalError:
                rows = []
            if not rows:
                fallback_where = " WHERE " + " AND ".join(filters) if filters else ""
                rows = connection.execute(
                    f"SELECT d.*, 0.0 AS bm25_score FROM documents d{fallback_where} LIMIT 1200",
                    params,
                ).fetchall()

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
            vector_score = float(np.dot(query_vector, embedding)) if embedding.size else 0.0
            bm25_raw = float(row["bm25_score"] or 0.0)
            lexical_score = 1.0 / (1.0 + max(0.0, bm25_raw)) if bm25_raw >= 0 else 1.0
            metadata_bonus = 0.0
            lowered_query = query.lower()
            if row["crop_group"] and row["crop_group"].replace("_", " ") in lowered_query:
                metadata_bonus += 0.08
            if row["district"] and row["district"].lower() in lowered_query:
                metadata_bonus += 0.08
            if row["source_kind"] == "official_public_source" or not bool(row["is_mock"]):
                metadata_bonus += 0.12
            score = 0.62 * vector_score + 0.38 * lexical_score + metadata_bonus
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        evidence: list[SourceEvidence] = []
        seen: set[str] = set()
        for score, row in scored:
            if row["document_id"] in seen:
                continue
            seen.add(row["document_id"])
            content = row["content"]
            snippet = content if len(content) <= 500 else content[:497].rstrip() + "..."
            evidence.append(
                SourceEvidence(
                    document_id=row["document_id"],
                    title=row["title"],
                    source=row["source"],
                    source_kind=row["source_kind"],
                    is_mock=bool(row["is_mock"]),
                    score=round(score, 6),
                    snippet=snippet,
                    metadata=json_loads(row["metadata_json"], {}),
                )
            )
            if len(evidence) >= top_k:
                break
        return evidence


def initialize_rag_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS documents_fts;
        DROP TABLE IF EXISTS rag_metadata;
        CREATE TABLE documents (
            document_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            is_mock INTEGER NOT NULL,
            crop_id TEXT,
            crop_group TEXT,
            district TEXT,
            upazila TEXT,
            knowledge_type TEXT,
            metadata_json TEXT NOT NULL,
            safe_for_prescriptive_advice INTEGER NOT NULL DEFAULT 0,
            embedding BLOB NOT NULL
        );
        CREATE INDEX idx_docs_crop_id ON documents(crop_id);
        CREATE INDEX idx_docs_crop_group ON documents(crop_group);
        CREATE INDEX idx_docs_district ON documents(district);
        CREATE INDEX idx_docs_upazila ON documents(upazila);
        CREATE INDEX idx_docs_source_kind ON documents(source_kind);
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            document_id UNINDEXED,
            title,
            content,
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE TABLE rag_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )


def insert_documents(connection: sqlite3.Connection, documents: Iterable[dict[str, Any]]) -> int:
    count = 0
    for document in documents:
        embedding = hashed_embedding(document["title"] + "\n" + document["content"]).tobytes()
        values = (
            document["document_id"],
            document["title"],
            document["content"],
            document["source"],
            document["source_kind"],
            1 if document.get("is_mock") else 0,
            document.get("crop_id"),
            document.get("crop_group"),
            document.get("district"),
            document.get("upazila"),
            document.get("knowledge_type"),
            document.get("metadata_json", "{}"),
            1 if document.get("safe_for_prescriptive_advice") else 0,
            embedding,
        )
        connection.execute(
            """
            INSERT INTO documents(
                document_id,title,content,source,source_kind,is_mock,crop_id,crop_group,
                district,upazila,knowledge_type,metadata_json,safe_for_prescriptive_advice,embedding
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            values,
        )
        connection.execute(
            "INSERT INTO documents_fts(document_id,title,content) VALUES(?,?,?)",
            (document["document_id"], document["title"], document["content"]),
        )
        count += 1
    return count
