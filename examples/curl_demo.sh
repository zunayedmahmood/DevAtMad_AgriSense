#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"

FIRST=$(curl -sS -X POST "$BASE_URL/v1/agent/turn" \
  -H 'content-type: application/json' \
  -d '{"message":"I have 2 acres of sandy-loam land in Moulovibazar. My budget is 80000 taka and I want the rabi season. I have limited irrigation."}')

echo "$FIRST" | python -m json.tool
SESSION_ID=$(echo "$FIRST" | python -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')

echo "\nSelecting the top crop automatically for a full demo plan..."
curl -sS -X POST "$BASE_URL/v1/agent/turn" \
  -H 'content-type: application/json' \
  -d "{\"session_id\":\"$SESSION_ID\",\"message\":\"Build the full plan for the best option.\",\"auto_select_top_crop\":true}" \
  | python -m json.tool
