# AgriSense Tier-0 Sandbox Backend

A runnable Python/FastAPI backend for the required AgriSense path:

**short farmer conversation -> missing-field recovery -> cleaned geocoding -> live weather -> RAG retrieval -> at least three crop recommendations -> chosen crop -> dated season plan -> inspectable financial projection -> persisted memory and visible tool trace**

This repository is deliberately backend-only. A frontend or an external LLM can use it in two ways:

1. `POST /v1/agent/turn` - deterministic Tier-0 state machine that already performs the tool sequence safely.
2. `GET /v1/tools/catalog` + `POST /v1/tools/invoke` - OpenAI-compatible function schemas and direct tool execution for another agent runtime.

## Key behavior

- Collects only the missing minimum fields: location, farm size, soil type, water availability, budget, and target season.
- Does not treat the entire farmer message as a geocoding query. For example, `I have some land in moulovibazar` becomes `Moulvibazar, Bangladesh`.
- Does not infer reliable irrigation from vague pump wording. Multi-acre + single/small/unquantified pump triggers a capacity follow-up.
- Calls Geoapify for forward geocoding when a key is configured.
- Calls Open-Meteo for current/daily rainfall, temperature, humidity, probability, and ET0 values.
- Stores every operational call with sanitized parameters, returned values, duration, status, and source kind.
- Uses a persistent SQLite hybrid RAG database: FTS5 lexical retrieval plus deterministic 384-dimensional local hash embeddings and cosine similarity.
- Separates source-derived, supplied mock, generated mock-gap, live external, and fallback data.
- Computes financial math deterministically. Changing area, budget, yield factor, or price factor changes the result.
- Marks calendar tasks outside the weather horizon for a future weather refresh instead of inventing forecasts.

## Data included

| Layer | Status | Purpose |
|---|---|---|
| `bangladesh_agriculture_unified_knowledge.json` | Supplied source-derived data | 11,598 district agronomy and upazila suitability records |
| `mock_agri_kb/` | Supplied synthetic data | 16 supported crops; calendars, fertilizer, irrigation, pests, costs, yields, prices |
| `generated_gap_kb.jsonl` | Generated synthetic data | Missing stage durations, stage offsets, season aliases, safeguards, conversions |
| Geoapify | Live external API | Farm location -> coordinates |
| Open-Meteo | Live external API | Actual returned weather values |

All synthetic values are labeled in API output and RAG metadata. They are not real farming advice.

## Supported planning crops

Boro rice, Aman rice, maize, wheat, potato, jute, sugarcane, mustard, soybean, lentil, mungbean, onion, garlic, chilli, tomato, and brinjal.

## Quick start

### Option A: local Python

```bash
cd agrisense_tier0_sandbox
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

## RAG search

```bash
curl -sS -X POST http://localhost:8000/v1/rag/search \
  -H 'content-type: application/json' \
  -d '{
    "query": "lentil sowing and suitability in Moulvibazar during rabi",
    "crop_id": "lentil",
    "district": "Moulvibazar",
    "top_k": 8,
    "include_mock": true
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
  │     ├── HybridRAGStore (SQLite FTS5 + vector cosine)
  │     ├── CropRecommender
  │     ├── FinancialCalculator
  │     ├── SeasonPlanner
  │     └── TraceRecorder
  ├── App SQLite: sessions, messages, plans, cache, traces
  └── ToolRegistry: schemas and direct invocation
```

See `docs/API_FLOW.md`, `docs/REAL_VS_MOCK.md`, and `docs/ARCHITECTURE.md`.

## Tests

```bash
pytest -q
```

The test suite checks:

- exact missing-field behavior
- Moulvibazar query cleaning
- single-pump capacity clarification
- financial arithmetic consistency
- source/mock RAG retrieval
- weather normalization and fallback labels
- cross-turn session memory
- end-to-end Tier-0 plan generation

## Important demo notes

- Put `EXTERNAL_MODE=live` before judging when you have a working Geoapify key and stable internet.
- Keep the tool trace panel visible in the frontend.
- Display `source`, `is_mock`, and RAG evidence beside recommendations.
- Do not describe synthetic financial/agronomic values as real.
- Open-Meteo forecasts cover a limited horizon. The backend intentionally asks for refreshes on later season tasks.
