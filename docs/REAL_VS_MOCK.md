# Real versus mock data

## Live when available

- Geoapify forward geocoding: real external API when `GEOAPIFY_API_KEY` is configured.
- Open-Meteo weather: real external API in `live` and `sandbox` modes when reachable.

## Provided source-derived knowledge

- `data/raw/bangladesh_agriculture_unified_knowledge.json`
- District agronomic records and upazila crop-suitability records.
- Stored in RAG as `source_kind=provided_source_derived` and `is_mock=false`.

## Provided mock knowledge

- `data/raw/mock_agri_kb/*`
- Synthetic crop profiles, calendars, fertilizer, irrigation, pests, economics, and stage plans.
- Stored as `source_kind=provided_mock` and `is_mock=true`.

## Generated mock gap knowledge

- `data/generated/generated_gap_kb.jsonl`
- Crop duration/stage offsets, season aliases, unit conversions, weather-horizon safeguards, financial labeling policy, and irrigation-capacity clarification rules.
- Stored as `source_kind=generated_mock_gap` and `is_mock=true`.

## Sandbox fallbacks

- If the Geoapify key is absent in `sandbox` mode, a generated mock coordinate is used and visibly tagged.
- If Open-Meteo fails in `sandbox` mode, a generated mock forecast is used and visibly tagged.
- `live` mode fails instead of silently falling back.
- `offline` mode never performs network calls and always returns tagged synthetic external-tool outputs.
