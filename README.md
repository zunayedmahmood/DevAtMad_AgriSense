# AgriSense Tier-0 Agentic Agriculture Platform

A runnable Python/FastAPI backend for the required AgriSense path:

**short farmer conversation -> missing-field recovery -> cleaned geocoding -> live weather -> RAG retrieval -> at least three crop recommendations -> chosen crop -> dated season plan -> inspectable financial projection -> persisted memory and visible tool trace**

This repository includes a FastAPI backend and a browser frontend. The UI or an external LLM can use it in these ways:

1. `POST /v1/agent/turn` - deterministic Tier-0 state machine that already performs the tool sequence safely.
2. `GET /v1/tools/catalog` + `POST /v1/tools/invoke` - OpenAI-compatible function schemas and direct tool execution for another agent runtime.
3. `GET /v1/catalog/products` - multilingual English, Banglish, and Bangla lookup over the integrated 60/40 catalog.

## Key behavior

- Collects only the missing minimum fields: location, farm size, soil type, water availability, budget, and target season.
- Does not treat the entire farmer message as a geocoding query. For example, `I have some land in moulovibazar` becomes `Moulvibazar, Bangladesh`.
- Does not infer reliable irrigation from vague pump wording. Multi-acre + single/small/unquantified pump triggers a capacity follow-up.
- Calls Geoapify for forward geocoding when a key is configured.
- Calls Open-Meteo for current/daily rainfall, temperature, humidity, probability, and ET0 values.
- Stores every operational call with sanitized parameters, returned values, duration, status, and source kind.
- Uses a persistent SQLite hybrid RAG database: FTS5 lexical retrieval plus deterministic 384-dimensional local hash embeddings and cosine similarity.
- Integrates a separate read-only 100-product Bangladesh agricultural catalog with 60 authentic and 40 explicitly synthetic test products.
- Imports 300 provenance-labelled catalog documents into RAG while preserving exact 60/40 origin ratios.
- Excludes synthetic catalog products and mock RAG evidence by default unless the caller explicitly opts in.
- Separates source-derived, supplied mock, generated mock-gap, live external, and fallback data.
- Computes financial math deterministically. Changing area, budget, yield factor, or price factor changes the result.
- Marks calendar tasks outside the weather horizon for a future weather refresh instead of inventing forecasts.

## Data included

| Layer | Status | Purpose |
|---|---|---|
| `bangladesh_agriculture_unified_knowledge.json` | Supplied source-derived data | 11,598 district agronomy and upazila suitability records |
| `mock_agri_kb/` | Supplied synthetic data | 16 supported crops; calendars, fertilizer, irrigation, pests, costs, yields, prices |
| `generated_gap_kb.jsonl` | Generated synthetic data | Missing stage durations, stage offsets, season aliases, safeguards, conversions |
| `mixed_60_40/bangladesh_agri_60_40.db` | Integrated read-only catalog | 100 products: 60 authentic, 40 synthetic; aliases, varieties, agronomy, fertilizer context, regional profiles, safety flags |
| Geoapify | Live external API | Farm location -> coordinates |
| Open-Meteo | Live external API | Actual returned weather values |

All synthetic values are labeled in API output and RAG metadata. They are not real farming advice.

## Supported planning crops

Boro rice, Aman rice, maize, wheat, potato, jute, sugarcane, mustard, soybean, lentil, mungbean, onion, garlic, chilli, tomato, and brinjal.

## Quick start

### Option A: local Python

```bash
cd sandbox
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Set the Geoapify key in `.env`:

```env
GEOAPIFY_API_KEY=your_key_here
EXTERNAL_MODE=sandbox
```

The prebuilt RAG database is included. To rebuild it:

```bash
python scripts/build_rag.py --force
```

Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- Swagger: `http://localhost:8000/docs`
- Health/RAG stats: `http://localhost:8000/health`
- Tool catalog: `http://localhost:8000/v1/tools/catalog`
- Crop catalog: `http://localhost:8000/v1/catalog/products`
- Browser UI: `http://localhost:8000/ui/`

### Option B: Docker

```bash
cp .env.example .env
# Add GEOAPIFY_API_KEY to .env
docker compose up --build
```

## External modes

```env
EXTERNAL_MODE=live
```

- Requires Geoapify key.
- Fails explicitly when Geoapify/Open-Meteo fails.
- No synthetic external fallback.

```env
EXTERNAL_MODE=sandbox
```

- Tries live external calls.
- Missing Geoapify key or transient API failure returns a clearly tagged synthetic fallback.
- Recommended for a hackathon demo because the trace makes fallback use visible.

```env
EXTERNAL_MODE=offline
```

- Makes no network calls.
- Uses clearly tagged synthetic geocoding/weather outputs.
- Useful for tests and UI development only.

## Conversation example

First turn:

```bash
curl -sS -X POST http://localhost:8000/v1/agent/turn \
  -H 'content-type: application/json' \
  -d '{
    "message": "I have 2 acres of sandy-loam land in Moulovibazar. My budget is 80000 taka, I have limited irrigation, and I want the rabi season."
  }'
```

The backend returns at least three candidates and a `session_id`. Continue the same chat:

```bash
curl -sS -X POST http://localhost:8000/v1/agent/turn \
  -H 'content-type: application/json' \
  -d '{
    "session_id": "PASTE_SESSION_ID",
    "message": "Choose lentil and build the complete plan."
  }'
```

For a one-request demo, set `auto_select_top_crop`:

```bash
curl -sS -X POST http://localhost:8000/v1/agent/turn \
  -H 'content-type: application/json' \
  -d '{
    "message": "I have 2 acres of sandy-loam land in Moulovibazar. My budget is 80000 taka, I have limited irrigation, and I want the rabi season.",
    "auto_select_top_crop": true
  }'
```

A ready-made script is at `examples/curl_demo.sh`.

## Missing-information example

```json
{
  "message": "I have land in Rangpur"
}
```

The response asks only for the still-missing area, soil, water, budget, and target season. It does not call weather prematurely.

## Pump-capacity safeguard

```json
{
  "message": "I have 5 acres in Rangpur with one small pump that gives a good amount of water. Budget 200000 taka, loam soil, rabi season."
}
```

The backend does not convert `good amount of water` into `reliable irrigation`. It asks whether the pump can cover all five acres within about two to three days and how many hours water is available.

## Direct tool calling

Get the function definitions:

```bash
curl -sS http://localhost:8000/v1/tools/catalog
```

Invoke one:

```bash
curl -sS -X POST http://localhost:8000/v1/tools/invoke \
  -H 'content-type: application/json' \
  -d '{
    "name": "geocode_location",
    "arguments": {"location_text": "I have some land in moulovibazar"}
  }'
```

The actual Geoapify `text` parameter is cleaned before the request.

## Integrated crop catalog

Authentic-only lookup is the default:

```bash
curl 'http://localhost:8000/v1/catalog/products?query=begun&limit=10'
curl 'http://localhost:8000/v1/catalog/products?query=%E0%A6%AC%E0%A7%87%E0%A6%97%E0%A7%81%E0%A6%A8&limit=10'
```

Synthetic test records require explicit opt-in:

```bash
curl 'http://localhost:8000/v1/catalog/products?query=synthetic&include_synthetic=true&limit=10'
```

Dataset status and full product detail:

```bash
curl http://localhost:8000/v1/catalog/stats
curl http://localhost:8000/v1/catalog/products/brinjal
```

See `docs/MIXED_DATABASE_INTEGRATION.md` for the architecture, safety gates, update process, and verification checklist.

## RAG search

```bash
curl -sS -X POST http://localhost:8000/v1/rag/search \
  -H 'content-type: application/json' \
  -d '{
    "query": "lentil sowing and suitability in Moulvibazar during rabi",
    "crop_id": "lentil",
    "district": "Moulvibazar",
    "top_k": 8,
    "include_mock": false
  }'
```

Each result contains:

- `source_kind`
- `is_mock`
- source and document ID
- retrieval score
- snippet
- traceability metadata where available

## Memory and traces

```bash
curl -sS http://localhost:8000/v1/sessions/SESSION_ID
curl -sS http://localhost:8000/v1/sessions/SESSION_ID/trace
```

Memory is persisted in SQLite across API restarts. The visible trace is an operational trace, not hidden chain-of-thought.

## Architecture

```text
FastAPI
  ├── TierZeroAgent state machine
  │     ├── IntakeParser + ambiguity safeguards
  │     ├── GeoapifyClient
  │     ├── OpenMeteoClient
  │     ├── MixedCatalogRepository (read-only 60/40 SQLite catalog)
  │     ├── HybridRAGStore (SQLite FTS5 + vector cosine, including 300 catalog documents)
  │     ├── CropRecommender
  │     ├── FinancialCalculator
  │     ├── SeasonPlanner
  │     └── TraceRecorder
  ├── App SQLite: sessions, messages, plans, cache, traces
  ├── Catalog SQLite: products, aliases, varieties, agronomy, provenance, safety gates
  └── ToolRegistry: schemas and direct invocation
```

See `docs/API_FLOW.md`, `docs/REAL_VS_MOCK.md`, `docs/ARCHITECTURE.md`, and `docs/MIXED_DATABASE_INTEGRATION.md`.

## Tests

```bash
python scripts/verify_database_integration.py
pytest -q
```

The test suite checks:

- exact missing-field behavior
- Moulvibazar query cleaning
- single-pump capacity clarification
- financial arithmetic consistency
- source/mock RAG retrieval
- exact catalog 60/40 ratios and SQLite integrity
- English, Banglish, and Bangla catalog aliases
- authentic-only default lookup and synthetic opt-in
- catalog-to-RAG ingestion and planner safety mapping
- weather normalization and fallback labels
- cross-turn session memory
- end-to-end Tier-0 plan generation

## Important demo notes

- Put `EXTERNAL_MODE=live` before judging when you have a working Geoapify key and stable internet.
- Keep the tool trace panel visible in the frontend.
- Display `source`, `is_mock`, and RAG evidence beside recommendations.
- Do not describe synthetic financial/agronomic values as real.
- Open-Meteo forecasts cover a limited horizon. The backend intentionally asks for refreshes on later season tasks.
