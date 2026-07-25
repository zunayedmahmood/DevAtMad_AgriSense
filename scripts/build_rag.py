from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.services.ingestion import build_rag


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the persistent AgriSense hybrid RAG database.")
    parser.add_argument("--force", action="store_true", help="Rebuild even if the database exists")
    parser.add_argument("--skip-if-present", action="store_true", help="Explicitly skip if present")
    args = parser.parse_args()
    result = build_rag(get_settings(), force=args.force and not args.skip_if_present)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
