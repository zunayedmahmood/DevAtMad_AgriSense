# Tier-0 API flow

1. Send each farmer message to `POST /v1/agent/turn`.
2. Reuse the returned `session_id` on later turns.
3. The state machine extracts only supported farm facts and asks for fields still missing.
4. Once the minimum profile is complete, it cleans the location phrase and invokes Geoapify.
5. It invokes Open-Meteo with the returned coordinates.
6. It retrieves source-derived and mock agronomic documents from the persistent hybrid RAG database.
7. It ranks at least three crops and asks the farmer to select one, unless `auto_select_top_crop=true`.
8. It builds the dated calendar and inspectable financial projection.
9. Every operational call is returned in `trace` and is also available at `/v1/sessions/{session_id}/trace`.

The trace is an operational/tool trace, not private chain-of-thought. It includes parameters, raw returned values, source kind, status, and duration.
