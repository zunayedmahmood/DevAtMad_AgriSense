# Bangladesh Agriculture 60/40 Mixed Database v3

This package contains an exact **60% real/authentic + 40% made-up** product catalog designed for AgriSense.

## Composition

- 100 product entities
- 60 authentic crop/horticulture products taken from the supplied BARC/SPAS-derived master database
- 40 entirely fictional products generated for testing
- 300 RAG documents: 180 authentic and 120 synthetic, preserving the same 60/40 ratio
- Synthetic records are blocked from prescriptive advice and crop recommendation
- 15 authentic products map to the current Tier-0 planning crop enum

## Important safety rule

`data_origin`, `is_synthetic`, `safe_for_prescriptive_advice`, and `eligible_for_recommendation` are mandatory filters. Synthetic records may be used for UI, retrieval and adversarial tests only.

## Files

- `bangladesh_agri_60_40.db` — normalized SQLite database
- `rag_documents.jsonl` — codebase-compatible RAG export
- `catalog.json.gz` — compressed product catalog
- `exports/` — CSV exports
- `INTEGRATION_GUIDE.md` — detailed codebase integration process
- `schema.sql` — SQL schema
- `build_database.py` — reproducible builder
- `validation_report.json` — integrity and ratio checks
- `AgriSense_60_40_DB_Integrated.zip` — patched runnable codebase, delivered separately

## Authentic-data interpretation

The authentic side preserves source-derived identity, aliases, varieties, crop profiles, fertilizer table context and available location evidence. Fertilizer values are not blanket prescriptions: they depend on the source table's crop context, units, soil-test condition, AEZ and yield goal.

## Synthetic-data interpretation

All fictional products begin with `Synthetic` and carry `data_origin='synthetic_made_up'`. Their calendars, climate ranges, fertilizer values and district scores are deterministic simulation values, not observations.

## Verification

The integrated project passed all 34 existing and new tests. See `TEST_REPORT.md`.
