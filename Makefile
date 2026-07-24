.PHONY: install ingest run test lint clean-runtime
install:
	python -m pip install -r requirements-dev.txt

ingest:
	python scripts/build_rag.py --force

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check app scripts tests

clean-runtime:
	rm -f data/runtime/*.sqlite3 data/runtime/*.sqlite3-shm data/runtime/*.sqlite3-wal
