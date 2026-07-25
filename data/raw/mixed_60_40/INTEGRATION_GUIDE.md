# AgriSense database integration guide

## 1. What the existing codebase does

The uploaded project uses FastAPI, a runtime SQLite database for users/sessions, and a separate SQLite hybrid RAG database. `scripts/build_rag.py` calls `app.services.ingestion.build_rag()`. That function converts source records into documents and inserts them into `data/processed/rag.sqlite3`. Retrieval uses FTS5 plus deterministic 384-dimensional hash embeddings.

Do not replace `data/runtime/agrisense.sqlite3` with this catalog. Runtime memory and agricultural knowledge are different databases.

## 2. Integration architecture

```text
bangladesh_agri_60_40.db
  ├─ products / aliases / varieties
  ├─ agronomic and fertilizer summaries
  ├─ real/synthetic provenance and safety fields
  └─ rag_documents
           │
           ▼
app/services/mixed_catalog.py
           │ yields existing RAG document dictionaries
           ▼
app/services/ingestion.py::build_rag()
           │
           ▼
data/processed/rag.sqlite3
           │
           ├─ /v1/rag/search
           ├─ recommendation evidence retrieval
           └─ planner evidence retrieval
```

## 3. Files added to the patched codebase

- `data/raw/mixed_60_40/bangladesh_agri_60_40.db`
- `app/services/mixed_catalog.py`
- `tests/test_mixed_catalog.py`
- `docs/MIXED_DATABASE_INTEGRATION.md`

Files changed:

- `app/config.py`: adds `mixed_catalog_db_path`
- `app/services/ingestion.py`: inserts mixed-catalog RAG documents
- `app/dependencies.py`: exposes a catalog repository
- `app/api/routes.py`: adds catalog endpoints and source-policy labels

## 4. Rebuild sequence

```bash
cd sandbox
source .venv/bin/activate
python scripts/build_rag.py --force
pytest -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The builder reads the mixed catalog, marks authentic records as `is_mock=0`, marks fictional records as `is_mock=1`, and records counts in `rag_metadata`.

## 5. API usage

### Catalog stats

```bash
curl http://localhost:8000/v1/catalog/stats
```

### Search authentic products only — default

```bash
curl 'http://localhost:8000/v1/catalog/products?query=begun&limit=10'
```

### Include fictional test entities

```bash
curl 'http://localhost:8000/v1/catalog/products?query=synthetic&include_synthetic=true&limit=10'
```

### RAG search excluding made-up data

```bash
curl -X POST http://localhost:8000/v1/rag/search   -H 'content-type: application/json'   -d '{"query":"brinjal fertilizer evidence","top_k":8,"include_mock":false}'
```

### RAG search including made-up test data

```bash
curl -X POST http://localhost:8000/v1/rag/search   -H 'content-type: application/json'   -d '{"query":"synthetic crop simulation","top_k":8,"include_mock":true}'
```

## 6. Recommendation-layer rule

Only products in `codebase_crop_mapping` with `enabled_for_planning=1` may enter the current `CropRecommender`. The 40 fictional products have no mapping and `eligible_for_recommendation=0`. This prevents a retrieved fictional document from becoming a cultivation recommendation.

The current planner supports 16 crop-cycle IDs. The catalog can contain more authentic products for lookup and RAG without automatically expanding the planner. To support a new real crop in planning, add all of these together:

1. `crop_master.jsonl`
2. crop calendar
3. suitability rules
4. fertilizer plan
5. irrigation plan
6. economics assumptions
7. stage plan
8. pest/disease rows
9. `CROP_DURATIONS`
10. source-to-planner mapping
11. deterministic tests

Do not add a crop to the planner merely because its name exists in the catalog.

## 7. Frontend integration

Use the catalog API for autocomplete and badges:

```javascript
const response = await fetch(
  `/v1/catalog/products?query=${encodeURIComponent(input)}&include_synthetic=false&limit=8`
);
const { products } = await response.json();
```

Show these fields:

- `canonical_name_en`
- `canonical_name_bn`
- `data_origin`
- `is_synthetic`
- `eligible_for_recommendation`
- `aliases`

Recommended badges:

- Authentic source-derived
- Synthetic test data
- Planner-supported
- Lookup only

Never hide the synthetic badge when `is_synthetic=true`.

## 8. Production migration

SQLite is suitable for the hackathon. For production PostgreSQL:

1. Recreate normalized tables with UUID/text primary keys.
2. Keep provenance and safety fields `NOT NULL`.
3. Add trigram indexes for aliases.
4. Move embeddings to pgvector or Qdrant.
5. Keep the runtime user/session database logically separate.
6. Add versioned dataset releases and immutable source hashes.
7. Add an approval workflow before any record can set `safe_for_prescriptive_advice=true`.

## 9. Update workflow

```text
new source files
  -> staging tables
  -> normalization and alias review
  -> source hash and provenance
  -> validation
  -> release database
  -> rebuild RAG
  -> regression tests
  -> deploy
```

Never overwrite authentic rows with synthetic gap fills. Store missing values as missing, and add synthetic alternatives as separate records with explicit origin fields.

## 10. Required tests

- exact 60/40 product ratio
- exact 60/40 RAG-document ratio
- synthetic products absent when `include_synthetic=false`
- synthetic documents absent when `include_mock=false`
- no synthetic product is planner-eligible
- Bangla and Banglish alias lookup
- SQLite integrity and foreign keys
- RAG rebuild count and health endpoint
- regression test for all existing 16 planning crops
