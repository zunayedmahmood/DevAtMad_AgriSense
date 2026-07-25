# Integrated Bangladesh Agriculture Database

## Goal

Integrate `bangladesh_agri_60_40.db` into AgriSense without mixing agricultural knowledge with the runtime user/session database and without allowing fictional records to become farming recommendations.

## Implemented architecture

```text
Farmer / Frontend / External LLM
          |
          +-----------------------------+
          |                             |
          v                             v
Catalog APIs and tools              Agent workflow
/v1/catalog/*                       intake -> weather -> RAG -> ranking -> plan
          |                             |
          v                             v
MixedCatalogRepository             HybridRAGStore
(read-only SQLite)                 (generated SQLite FTS5 + embeddings)
          |                             ^
          | 300 provenance-labelled     |
          +------ RAG documents --------+

Runtime AppDatabase remains separate:
users, farms, sessions, messages, memory, plans, traces, caches
```

## Why the databases remain separate

`data/runtime/agrisense.sqlite3` contains mutable application state. The integrated catalog contains release-versioned agricultural identities, aliases, varieties, summaries, provenance, and test entities. Combining them would make deployment, backup, safety review, and dataset upgrades harder.

The catalog is therefore opened in SQLite `mode=ro` with `PRAGMA query_only=ON`. The application cannot accidentally modify the packaged source database.

## Files added

- `data/raw/mixed_60_40/bangladesh_agri_60_40.db`
- `data/raw/mixed_60_40/schema.sql`
- `data/raw/mixed_60_40/validation_report.json`
- `data/raw/mixed_60_40/build_database.py`
- `data/raw/mixed_60_40/catalog.json.gz`
- `app/services/mixed_catalog.py`
- `tests/test_mixed_catalog.py`
- `scripts/verify_database_integration.py`

## Files changed

- `app/config.py` — adds `mixed_catalog_db_path`.
- `app/dependencies.py` — registers `MixedCatalogRepository`.
- `app/services/ingestion.py` — imports all 300 catalog RAG documents.
- `app/services/rag.py` — stores prescriptive-safety flags, supports Bangla tokens, and maps rice evidence to `rice_boro` and `rice_aman` queries.
- `app/api/routes.py` — adds catalog stats, search, and detail endpoints; health now verifies both RAG and catalog readiness.
- `app/tools/registry.py` — adds catalog search/detail tools for the agent runtime.
- `app/schemas.py` — public RAG search excludes mock evidence unless explicitly requested.
- `frontend/index.html` and `frontend/app.js` — adds a visible multilingual catalog explorer and fixes direct-tool names.

## Safety gates

The following source fields remain authoritative:

- `data_origin`
- `is_synthetic`
- `safe_for_identity_lookup`
- `safe_for_prescriptive_advice`
- `eligible_for_recommendation`
- `codebase_crop_mapping.enabled_for_planning`

Rules enforced by code:

1. Catalog searches return authentic records only by default.
2. Synthetic records require `include_synthetic=true`.
3. Synthetic records keep their visible synthetic badge.
4. Synthetic records are not planner-supported and cannot become crop recommendations.
5. Public RAG search defaults to `include_mock=false`.
6. Internal crop planning may still use the project’s existing labelled demonstration assumptions, but mixed-catalog synthetic records have no planning mapping.
7. Ambiguous aliases are displayed for traceability but excluded from confident lookup matching.
8. Fertilizer information preserves its context warning and safety flag; existence in the database does not turn it into a blanket prescription.

## API endpoints

### Dataset status

```bash
curl http://localhost:8000/v1/catalog/stats
```

Expected core counts:

- 100 products
- 60 authentic products
- 40 synthetic products
- 300 catalog RAG documents
- 180 authentic RAG documents
- 120 synthetic RAG documents

### Multilingual authentic lookup

```bash
curl 'http://localhost:8000/v1/catalog/products?query=begun&limit=10'
curl 'http://localhost:8000/v1/catalog/products?query=%E0%A6%AC%E0%A7%87%E0%A6%97%E0%A7%81%E0%A6%A8&limit=10'
```

### Explicit synthetic test lookup

```bash
curl 'http://localhost:8000/v1/catalog/products?query=synthetic&include_synthetic=true&limit=10'
```

### Full product detail

```bash
curl http://localhost:8000/v1/catalog/products/brinjal
```

The detail response contains aliases, codebase mappings, varieties, agronomic summary, fertilizer summary, regional profiles, provenance, and safety flags.

## RAG rebuild

```bash
python scripts/build_rag.py --force
```

The build now inserts:

- 11,598 supplied source-derived documents
- existing official/mock/generated project documents
- 300 integrated mixed-catalog documents

The resulting `rag_metadata` table records `mixed_catalog_documents=300` and the source database path.

## Verification

```bash
python scripts/verify_database_integration.py
pytest -q
```

The verification covers:

- SQLite integrity and foreign keys
- exact 60/40 product ratio
- exact 60/40 catalog-document ratio
- authentic-only default lookup
- explicit synthetic opt-in
- Bangla/Banglish/English aliases
- ambiguous-alias rejection
- planner mapping safety
- RAG ingestion count
- synthetic exclusion with `include_mock=false`
- rice evidence retrieval for both Boro and Aman planner IDs
- API behavior

## Updating the database later

1. Build a new release database in staging.
2. Validate source hashes, foreign keys, ratios, and safety fields.
3. Replace `data/raw/mixed_60_40/bangladesh_agri_60_40.db`.
4. Run `python scripts/build_rag.py --force`.
5. Run `python scripts/verify_database_integration.py` and `pytest -q`.
6. Deploy the new catalog and rebuilt RAG together.

Never overwrite missing authentic facts with fabricated values. Synthetic alternatives must remain separate records with explicit provenance and disabled recommendation flags.
