# Database Integration Test Report

Date: 2026-07-25

## Automated results

- `python scripts/verify_database_integration.py`: passed
- `pytest -q`: 40 passed
- `python -m compileall -q app scripts tests`: passed
- `node --check frontend/app.js`: passed
- Catalog SQLite `PRAGMA integrity_check`: `ok`
- Catalog SQLite foreign-key check: no violations

## Verified dataset counts

- Products: 100
- Authentic products: 60
- Synthetic products: 40
- Catalog RAG documents: 300
- Authentic catalog documents: 180
- Synthetic catalog documents: 120
- Total rebuilt hybrid RAG documents: 12,091

## Verified behavior

- English lookup: `brinjal`
- Banglish lookup: `begun`
- Bangla lookup: `বেগুন`
- Synthetic records hidden by default
- Synthetic records available only through explicit opt-in
- Synthetic records blocked from planner mappings
- Ambiguous aliases excluded from confident search
- Rice catalog evidence retrievable for `rice_boro` and `rice_aman`
- Catalog API and frontend explorer operational
