from __future__ import annotations

import difflib
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.db import AppDatabase
from app.services.kb import KnowledgeRepository
from app.utils import normalize_space, stable_id


MANUAL_ALIASES = {
    "moulovibazar": "Moulvibazar",
    "moulvi bazar": "Moulvibazar",
    "maulvibazar": "Moulvibazar",
    "moulavi bazar": "Moulvibazar",
    "chittagong": "Chattogram",
    "comilla": "Cumilla",
    "barisal": "Barishal",
    "jessore": "Jashore",
    "bogra": "Bogura",
    "nawabganj": "Chapai Nawabganj",
}

_STOP_WORDS = {
    "land",
    "farm",
    "field",
    "acre",
    "acres",
    "soil",
    "budget",
    "water",
    "irrigation",
    "village",
    "district",
    "upazila",
    "bangladesh",
    "and",
    "with",
    "where",
    "which",
    "for",
    "my",
}


@dataclass
class NormalizedLocation:
    location_text: str | None
    district: str | None
    upazila: str | None
    exact_catalog_match: bool
    extraction_method: str


class LocationNormalizer:
    def __init__(self, kb: KnowledgeRepository):
        self.kb = kb
        places = kb.gazetteer.get("places", {})
        self.district_names: dict[str, str] = {}
        self.upazila_entries: list[tuple[str, str, str]] = []
        for key, value in places.items():
            district = value.get("district")
            upazila = value.get("upazila")
            if district and not upazila:
                self.district_names[key.lower()] = district
            if district and upazila:
                self.upazila_entries.append((upazila.lower(), upazila, district))
        for alias, canonical in MANUAL_ALIASES.items():
            self.district_names[alias] = canonical

    @staticmethod
    def _clean(text: str) -> str:
        text = text.lower().replace("’", "'")
        text = re.sub(r"[^a-z0-9' -]+", " ", text)
        return normalize_space(text)

    def extract(self, text: str) -> NormalizedLocation:
        cleaned = self._clean(text)
        # Prefer exact district aliases anywhere in the utterance.
        for alias in sorted(self.district_names, key=len, reverse=True):
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", cleaned):
                district = self.district_names[alias]
                upazila = self._find_upazila(cleaned, district)
                location_text = f"{upazila}, {district}" if upazila else district
                return NormalizedLocation(location_text, district, upazila, True, "catalog_alias")

        # Exact upazila can establish both upazila and district.
        for alias, canonical, district in sorted(self.upazila_entries, key=lambda row: len(row[0]), reverse=True):
            if len(alias) < 4:
                continue
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", cleaned):
                return NormalizedLocation(
                    f"{canonical}, {district}", district, canonical, True, "upazila_catalog"
                )

        # Extract only the location phrase, never the whole farmer sentence.
        match = re.search(
            r"(?:located\s+in|farm\s+in|land\s+in|field\s+in|near|at|from|in)\s+([a-z][a-z .'-]{1,60})",
            cleaned,
        )
        candidate = ""
        if match:
            words = []
            for word in match.group(1).split():
                if word in _STOP_WORDS or re.fullmatch(r"\d+(?:\.\d+)?", word):
                    break
                words.append(word)
                if len(words) >= 4:
                    break
            candidate = " ".join(words).strip(" ,.-")

        if candidate:
            canonical = self._fuzzy_district(candidate)
            if canonical:
                return NormalizedLocation(canonical, canonical, None, False, "fuzzy_district")
            return NormalizedLocation(candidate.title(), None, None, False, "preposition_phrase")
        return NormalizedLocation(None, None, None, False, "not_found")

    def _find_upazila(self, cleaned: str, district: str) -> str | None:
        matches = [
            canonical
            for alias, canonical, row_district in self.upazila_entries
            if row_district.lower() == district.lower()
            and canonical.lower() != district.lower()
            and re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", cleaned)
        ]
        return max(matches, key=len) if matches else None

    def _fuzzy_district(self, candidate: str) -> str | None:
        candidate = candidate.lower().strip()
        choices = list(self.district_names)
        result = difflib.get_close_matches(candidate, choices, n=1, cutoff=0.78)
        return self.district_names[result[0]] if result else None


class GeoapifyClient:
    endpoint = "https://api.geoapify.com/v1/geocode/search"

    def __init__(
        self,
        settings: Settings,
        database: AppDatabase,
        kb: KnowledgeRepository,
        client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings
        self.database = database
        self.kb = kb
        self.client = client

    async def geocode(
        self,
        location_text: str,
        *,
        district: str | None = None,
        upazila: str | None = None,
        exact_catalog_match: bool = False,
    ) -> dict[str, Any]:
        query = self._build_query(location_text, district, upazila)
        cache_key = stable_id("geoapify", query.lower(), prefix="geocode:")
        now = int(time.time())
        cached = self.database.cache_get(cache_key, now)
        if cached:
            cached["cache_hit"] = True
            return cached

        if self.settings.external_mode == "offline":
            return self._mock_fallback(location_text, district, upazila, "offline_mode")
        if not self.settings.geoapify_api_key:
            if self.settings.external_mode == "live":
                raise RuntimeError("GEOAPIFY_API_KEY is required in live mode")
            return self._mock_fallback(location_text, district, upazila, "missing_geoapify_key")

        params = {
            "text": query,
            "filter": "countrycode:bd",
            "bias": "countrycode:bd",
            "type": "locality",
            "lang": "en",
            "limit": 5,
            "format": "json",
            "apiKey": self.settings.geoapify_api_key,
        }
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)
        try:
            response = await client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results") or []
            if not results:
                if self.settings.external_mode == "live":
                    raise RuntimeError(f"Geoapify returned no Bangladesh result for {query!r}")
                return self._mock_fallback(location_text, district, upazila, "no_geoapify_result")
            selected = results[0]
            rank = selected.get("rank") or {}
            confidence = float(rank.get("confidence_city_level") or rank.get("confidence") or 0.0)
            output = {
                "query_sent": query,
                "latitude": float(selected["lat"]),
                "longitude": float(selected["lon"]),
                "formatted": selected.get("formatted") or query,
                "district": district or selected.get("county") or selected.get("state"),
                "upazila": upazila or selected.get("city") or selected.get("district"),
                "country_code": selected.get("country_code"),
                "confidence": confidence,
                "match_type": rank.get("match_type"),
                "result_type": selected.get("result_type"),
                "place_id": selected.get("place_id"),
                "source": "geoapify_live",
                "is_mock": False,
                "needs_confirmation": bool(
                    not exact_catalog_match and confidence < self.settings.geoapify_min_confidence
                ),
                "cache_hit": False,
                "raw": {"results": results[:5], "query": payload.get("query")},
                "attribution": "Geoapify / OpenStreetMap contributors",
            }
            self.database.cache_set(
                cache_key, output, now + self.settings.geocode_cache_ttl_seconds
            )
            return output
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            if self.settings.external_mode == "live":
                raise RuntimeError(f"Geoapify request failed: {exc}") from exc
            return self._mock_fallback(location_text, district, upazila, f"geoapify_error:{type(exc).__name__}")
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _build_query(location_text: str, district: str | None, upazila: str | None) -> str:
        if upazila and district:
            base = f"{upazila}, {district}"
        elif district:
            base = district
        else:
            base = normalize_space(location_text)
        base = re.sub(r"\b(i|we|have|some|land|farm|field|located|live)\b", " ", base, flags=re.I)
        base = normalize_space(base.strip(" ,.-"))
        if not base:
            raise ValueError("No clean location phrase was available for geocoding")
        return f"{base}, Bangladesh"

    def _mock_fallback(
        self, location_text: str, district: str | None, upazila: str | None, reason: str
    ) -> dict[str, Any]:
        places = self.kb.gazetteer.get("places", {})
        keys = []
        if upazila and district:
            keys.append(f"{upazila}, {district}".lower())
        if district:
            keys.append(district.lower())
        keys.append(location_text.lower())
        entry = next((places[key] for key in keys if key in places), None)
        if not entry:
            # A fixed sandbox-only point near central Bangladesh; clearly marked mock.
            entry = {
                "lat": 23.685,
                "lon": 90.3563,
                "district": district,
                "upazila": upazila,
            }
        return {
            "query_sent": self._build_query(location_text, district, upazila),
            "latitude": float(entry["lat"]),
            "longitude": float(entry["lon"]),
            "formatted": f"{location_text}, Bangladesh (sandbox fallback)",
            "district": district or entry.get("district"),
            "upazila": upazila or entry.get("upazila"),
            "country_code": "bd",
            "confidence": 0.0,
            "match_type": "generated_mock_fallback",
            "result_type": "locality",
            "place_id": None,
            "source": "generated_mock_geocode",
            "is_mock": True,
            "needs_confirmation": False,
            "cache_hit": False,
            "raw": {"fallback_reason": reason, "entry": entry},
            "attribution": "Synthetic sandbox fallback; not Geoapify data",
        }
