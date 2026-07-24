# AgriSense Mixed-Evidence Knowledge Base

This folder contains two deliberately separated evidence classes.

## 1. Reviewed public-source evidence

`reviewed_public_tier0_crops.jsonl` and `public_source_principles.jsonl` provide the supported Tier 0 crop-master, calendar, and fertilizer-policy evidence for:

- Boro rice (`rice_boro`)
- Wheat (`wheat`)
- Maize (`maize`)

Every trusted record includes explicit classification, review state, source identity, publisher, year/status, URL, and a page/section/line/source locator. `source_manifest.json` is the source registry.

## 2. Seeded-demo operational assumptions

The remaining crop, economics, fertilizer quantity, irrigation, pest, yield, price, and cost files are synthetic prototype data. They exist so the deterministic calculators and season-plan UI can run end to end. They must not be presented as official agricultural recommendations.

## Runtime enforcement

The loader does not trust filenames. A record enters the public corpus only when it passes the fail-closed provenance gate. Public Tier 0 readiness requires at least three individual crops that each have:

```text
crop_master + calendar + fertilizer
```

The crop ranker uses the resulting reviewed crop bundles as its candidate universe. It does not silently rank every seeded crop when the public gate is active.

## Main files

- `reviewed_public_tier0_crops.jsonl` — reviewed public crop suitability/weather and calendar records
- `public_source_principles.jsonl` — BARC fertilizer usage and crop-specific timing policies
- `source_manifest.json` — source registry and coverage notes
- `crop_master.jsonl` — seeded prototype crop profiles for broader non-compliant testing
- `crop_calendar.jsonl` — seeded prototype calendars
- `fertilizer_plans.jsonl` — seeded exact product quantities and split schedules
- `irrigation_plans.jsonl` — seeded irrigation assumptions
- `economics_mock.jsonl` — seeded yield, price, and cost assumptions
- `pest_disease_risks.jsonl` — seeded risk and cost assumptions

## Production boundary

For real deployment, replace seeded exact quantities and economics with reviewed soil-test/AEZ fertilizer tables, current local input/market data, public yield references, and registered treatment guidance.
