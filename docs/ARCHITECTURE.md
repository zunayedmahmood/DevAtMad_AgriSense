# Architecture and decision boundaries

## Why a deterministic Tier-0 runtime

The backend does not require an LLM to decide whether mandatory data is missing, perform arithmetic, or call external APIs. Those steps are deterministic and testable. An LLM may sit above the tool registry for language generation, but the `/v1/agent/turn` route remains the reliable core path.

## State machine

1. Load the session profile.
2. Parse only supported facts from the current turn.
3. Merge explicit `profile_patch` fields.
4. Identify missing/ambiguous required fields.
5. Stop and ask targeted follow-ups when needed.
6. Normalize the location phrase.
7. Geocode with Geoapify or visibly tagged fallback depending on mode.
8. Fetch weather with Open-Meteo or visibly tagged fallback depending on mode.
9. Retrieve profile-relevant documents from RAG.
10. Rank 16 supported candidates and return at least three.
11. Wait for crop selection unless auto-select is requested.
12. Generate the dated season plan and financial projection.
13. Persist profile, messages, recommendation, plan, cache, and traces.

## RAG implementation

The RAG database is SQLite so it can be shipped as one file and run without a hosted service.

- FTS5 supplies strong exact/lexical retrieval for crop and location names.
- A deterministic 384-dimensional hashed embedding supplies a lightweight vector signal without downloading a model.
- Retrieval score combines lexical, vector, crop, and district matches.
- Metadata filters support crop, district, upazila, source kind, and mock exclusion.
- The prebuilt database contains 11,779 documents at generation time: 11,598 supplied source-derived records, 160 supplied mock records, and 21 generated mock-gap documents.

## Grounding hierarchy

1. Farmer profile values explicitly supplied or confirmed.
2. Live API values and raw returned payloads.
3. Supplied source-derived agronomy/suitability records.
4. Supplied mock structured planning/economic values.
5. Generated mock gap assumptions.

A lower layer may fill a known gap but cannot silently overwrite a higher layer.

## Trace design

Each tool call stores:

- trace/session/step IDs
- tool name
- sanitized parameters
- raw result
- source kind
- success/error status
- duration
- timestamp

API keys are never written to trace storage.
