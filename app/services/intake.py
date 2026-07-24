from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.schemas import FarmProfile, ProfilePatch
from app.services.geocoding import LocationNormalizer
from app.services.kb import KnowledgeRepository


MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

SOIL_ALIASES = {
    "sandy loam": "sandy_loam", "sandy-loam": "sandy_loam", "sandy": "sandy",
    "clay loam": "clay_loam", "clay-loam": "clay_loam", "silt loam": "silt_loam",
    "silty loam": "silt_loam", "loamy": "loam", "loam": "loam", "clayey": "clay", "clay": "clay",
}

SEASON_ALIASES = {
    "rabi": "rabi", "winter": "rabi", "dry season": "rabi", "boro season": "rabi", "boro": "rabi",
    "kharif 1": "kharif_1", "kharif-1": "kharif_1", "pre monsoon": "kharif_1",
    "pre-monsoon": "kharif_1", "aus season": "kharif_1", "aus": "kharif_1",
    "kharif 2": "kharif_2", "kharif-2": "kharif_2", "monsoon": "kharif_2",
    "aman season": "kharif_2", "aman": "kharif_2", "kharif": "kharif",
    "year round": "year_round", "year-round": "year_round",
}

WATER_PATTERNS = [
    (r"\b(no|without) (irrigation|water source)\b|\brainfed( only)?\b", "none"),
    (r"\blimited( (irrigation|water))?\b|\bwater is limited\b", "limited"),
    (r"\breliable( (irrigation|water))?\b|\bdeep tube ?well\b|\btube ?well\b|\bcan irrigate (all|the whole)\b|\bcanal( water)?\b|\briver\b", "reliable"),
    (r"\brented( (pump|irrigation))?\b|\bhire (a )?pump\b", "rented"),
]

CROP_ALIASES = {
    "boro rice": "rice_boro", "boro": "rice_boro", "aman rice": "rice_aman", "aman": "rice_aman",
    "corn": "maize", "maize": "maize", "wheat": "wheat", "potato": "potato", "jute": "jute",
    "sugarcane": "sugarcane", "mustard": "mustard", "soybean": "soybean", "soy bean": "soybean",
    "lentil": "lentil", "mungbean": "mungbean", "mung bean": "mungbean", "onion": "onion",
    "garlic": "garlic", "chilli": "chilli", "chili": "chilli", "tomato": "tomato",
    "brinjal": "brinjal", "eggplant": "brinjal",
}


@dataclass
class ParseResult:
    patch: dict[str, Any] = field(default_factory=dict)
    clarifications: list[str] = field(default_factory=list)
    extraction_notes: list[str] = field(default_factory=list)


class IntakeParser:
    required_fields = [
        "location_text", "farm_size_acre", "soil_type", "water_availability", "budget_bdt", "target_season"
    ]

    questions = {
        "location_text": "Which district or nearby upazila is the farm in?",
        "farm_size_acre": "How much land will you cultivate? Please include the unit, such as acres, bigha, decimal, or hectares.",
        "soil_type": "What is the soil type: sandy, sandy-loam, loam, silt-loam, clay-loam, or clay?",
        "water_availability": "What irrigation is actually available: none, limited, reliable, or rented?",
        "budget_bdt": "What is the total budget in BDT for this farm area?",
        "target_season": "Which season or planting month are you targeting?",
    }

    def __init__(self, kb: KnowledgeRepository, location_normalizer: LocationNormalizer):
        self.kb = kb
        self.location_normalizer = location_normalizer

    def parse(self, text: str, current: FarmProfile) -> ParseResult:
        lowered = text.lower().strip()
        result = ParseResult()

        location = self.location_normalizer.extract(text)
        if location.location_text:
            result.patch.update(
                {
                    "location_text": location.location_text,
                    "district": location.district,
                    "upazila": location.upazila,
                }
            )
            result.extraction_notes.append(
                f"Location extracted by {location.extraction_method}: {location.location_text}"
            )

        area = self._parse_area(lowered)
        if area:
            result.patch.update(area)

        for alias in sorted(SOIL_ALIASES, key=len, reverse=True):
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lowered):
                result.patch["soil_type"] = SOIL_ALIASES[alias]
                break

        budget = self._parse_budget(lowered)
        if budget is not None:
            result.patch["budget_bdt"] = budget
        else:
            pct_cut = re.search(r"\b(?:cut|reduce|decrease|drop)\s*(?:by|to)?\s*(\d+(?:\.\d+)?)\s*%", lowered)
            if pct_cut and current.budget_bdt:
                cut_pct = float(pct_cut.group(1))
                new_budget = current.budget_bdt * (1.0 - cut_pct / 100.0)
                result.patch["budget_bdt"] = round(new_budget, 2)
                result.extraction_notes.append(f"Applied budget reduction of {cut_pct:g}% to current BDT {current.budget_bdt:,.0f}.")

        month = self._parse_month(lowered)
        season = self._parse_season(lowered)
        if month:
            result.patch["target_month"] = month
            result.patch["target_season"] = season or self._season_from_month(month)
        elif season:
            result.patch["target_season"] = season
        year_match = re.search(r"\b(20[2-9]\d)\b", lowered)
        if year_match:
            result.patch["target_year"] = int(year_match.group(1))

        crop = self._parse_crop(lowered)
        if crop:
            result.patch["chosen_crop_id"] = crop

        water = self._parse_water(lowered)
        if water:
            result.patch["water_availability"] = water
        if re.search(r"\b(yes|it can|can irrigate|covers?|can cover|irrigate)\b.*\b(all|whole|entire|\d+\s*acres?)\b", lowered):
            result.patch["water_capacity_confirmed"] = True
            result.patch.setdefault("water_availability", "reliable")

        effective_area = result.patch.get("farm_size_acre") or current.farm_size_acre
        pump_mentioned = bool(re.search(r"\b(pump|tube ?well|motor)\b", lowered))
        explicitly_limited = result.patch.get("water_availability") in {"limited", "none", "rented"}
        quantified_capacity = bool(
            re.search(r"\b\d+(?:\.\d+)?\s*(lit(er|re)s?/?(second|minute|hour)|lps|cusec|hours? per day)\b", lowered)
        )
        small_or_single = bool(re.search(r"\b(one|single|small|1)\b.{0,15}\b(pump|tube ?well|motor)\b", lowered))
        if pump_mentioned and effective_area and effective_area >= 2 and not explicitly_limited:
            if (small_or_single or not quantified_capacity) and not result.patch.get("water_capacity_confirmed"):
                result.patch.pop("water_availability", None)
                result.patch["water_details"] = text[:500]
                result.clarifications.append(
                    f"Can this irrigation setup cover all {effective_area:g} acres within about 2-3 days, and how many hours per day is water available?"
                )
                result.extraction_notes.append("Pump capacity was not assumed from vague wording.")

        return result

    def merge(self, current: FarmProfile, parsed: ParseResult, explicit: ProfilePatch | None) -> FarmProfile:
        data = current.model_dump()
        data.update({key: value for key, value in parsed.patch.items() if value is not None})
        if explicit:
            data.update({key: value for key, value in explicit.model_dump(exclude_none=True).items()})
        # Location changes invalidate previous coordinates.
        if parsed.patch.get("location_text") and parsed.patch.get("location_text") != current.location_text:
            data.update({"latitude": None, "longitude": None, "geocode_source": None, "geocode_confidence": None})
        return FarmProfile.model_validate(data)

    def missing_fields(self, profile: FarmProfile) -> list[str]:
        missing = [field for field in self.required_fields if getattr(profile, field) in {None, ""}]
        if profile.water_details and profile.water_capacity_confirmed is not True and "water_availability" not in missing:
            missing.append("water_availability")
        return missing

    def followups(self, missing: list[str], clarifications: list[str], max_fields: int = 6) -> list[str]:
        questions = list(dict.fromkeys(clarifications))
        for field in missing:
            question = self.questions[field]
            if question not in questions:
                questions.append(question)
        return questions[:max_fields]

    @staticmethod
    def _parse_area(text: str) -> dict[str, Any] | None:
        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(acres?|acre|bighas?|bigha|decimals?|decimal|shotoks?|shotok|hectares?|hectare|ha)\b",
            text,
        )
        if not match:
            return None
        value = float(match.group(1))
        unit = match.group(2)
        factor = 1.0
        if unit.startswith("bigha"):
            factor = 0.3306
        elif unit.startswith("decimal") or unit.startswith("shotok"):
            factor = 0.01
        elif unit in {"hectare", "hectares", "ha"}:
            factor = 2.47105
        return {"farm_size_acre": round(value * factor, 5), "farm_size_input": match.group(0)}

    @staticmethod
    def _parse_budget(text: str) -> float | None:
        try:
            cleaned = text.replace("৳", " taka ")
            cleaned = re.sub(r"(?<=\d),(?=\d)", "", cleaned)

            patterns = [
                r"(?:budget(?: is| of)?|spend|have|cost|tk|taka|bdt)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(lakh|lac|k|thousand|crore|koti)?\b",
                r"\b(\d+(?:\.\d+)?)\s*(lakh|lac|k|thousand|crore|koti)?\s*(?:bdt|tk|taka|budget|spend|cost)\b",
                r"\b(\d+(?:\.\d+)?)\s*(lakh|lac|k|thousand|crore|koti)\b",
                r"(?:tk|taka|bdt)\s*(\d+(?:\.\d+)?)",
                r"\b(\d+(?:\.\d+)?)\s*(?:tk|taka|bdt)\b",
            ]
            for pattern in patterns:
                match = re.search(pattern, cleaned, re.IGNORECASE)
                if not match:
                    continue
                value = float(match.group(1))
                suffix = (match.group(2) if match.lastindex and match.lastindex >= 2 and match.group(2) else "").lower()

                if suffix in {"lakh", "lac"}:
                    value *= 100_000
                elif suffix in {"k", "thousand"}:
                    value *= 1_000
                elif suffix in {"crore", "koti"}:
                    value *= 10_000_000

                if value >= 1000 or suffix:
                    return round(value, 2)
            return None
        except Exception:
            return None

    @staticmethod
    def _parse_month(text: str) -> int | None:
        for alias in sorted(MONTHS, key=len, reverse=True):
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text):
                return MONTHS[alias]
        return None

    @staticmethod
    def _parse_season(text: str) -> str | None:
        lowered = text.lower()
        if re.search(r"\b(boro\s+season|rabi\s+season|rabi|winter|dry\s+season)\b", lowered):
            return "rabi"
        if re.search(r"\b(aus\s+season|kharif\s*1\s+season|kharif\s*1|pre-?monsoon)\b", lowered):
            return "kharif_1"
        if re.search(r"\b(aman\s+season|kharif\s*2\s+season|kharif\s*2|monsoon)\b", lowered):
            return "kharif_2"
        if re.search(r"\bkharif\b", lowered):
            return "kharif"
        if re.search(r"\byear-?round\b", lowered):
            return "year_round"
        return None

    @staticmethod
    def _season_from_month(month: int) -> str:
        if month in {11, 12, 1, 2, 3}:
            return "rabi"
        if month in {4, 5, 6}:
            return "kharif_1"
        return "kharif_2"

    @staticmethod
    def _parse_water(text: str) -> str | None:
        for pattern, value in WATER_PATTERNS:
            if re.search(pattern, text):
                return value
        return None

    @staticmethod
    def _parse_crop(text: str) -> str | None:
        trimmed = text.strip().lower()
        cleaned_text = re.sub(r"\b(boro|aman|aus|rabi|kharif)\s+season\b", "", trimmed).strip()

        if cleaned_text in {"1", "option 1", "option #1", "first", "#1"}:
            return "__index_1"
        if cleaned_text in {"2", "option 2", "option #2", "second", "#2"}:
            return "__index_2"
        if cleaned_text in {"3", "option 3", "option #3", "third", "#3"}:
            return "__index_3"

        selection_context = bool(
            re.search(r"\b(choose|select|plant|grow|pick|go with|plan for|want|build|for|projection|option)\b", cleaned_text)
        )

        for alias in sorted(CROP_ALIASES, key=len, reverse=True):
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", cleaned_text):
                if selection_context or len(cleaned_text.split()) <= 4:
                    return CROP_ALIASES[alias]
        return None
