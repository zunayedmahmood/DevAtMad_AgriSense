from __future__ import annotations

import math
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings
from app.db import AppDatabase
from app.utils import stable_id


class OpenMeteoClient:
    endpoint = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        settings: Settings,
        database: AppDatabase,
        client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings
        self.database = database
        self.client = client

    async def forecast(
        self, latitude: float, longitude: float, *, days: int = 7, force_refresh: bool = False
    ) -> dict[str, Any]:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Invalid latitude/longitude")
        days = max(1, min(int(days), 16))
        cache_key = stable_id("open_meteo", round(latitude, 4), round(longitude, 4), days, prefix="weather:")
        now = int(time.time())
        if not force_refresh:
            cached = self.database.cache_get(cache_key, now)
            if cached:
                cached["cache_hit"] = True
                return cached

        if self.settings.external_mode == "offline":
            return self._mock_forecast(latitude, longitude, days, "offline_mode")

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,rain,weather_code",
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
                "precipitation_sum,precipitation_probability_max,relative_humidity_2m_mean,"
                "et0_fao_evapotranspiration"
            ),
            "timezone": "auto",
            "forecast_days": days,
        }
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)
        try:
            response = await client.get(self.endpoint, params=params)
            response.raise_for_status()
            raw = response.json()
            output = self._normalize(raw, latitude, longitude)
            output["cache_hit"] = False
            self.database.cache_set(
                cache_key, output, now + self.settings.weather_cache_ttl_seconds
            )
            return output
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if self.settings.external_mode == "live":
                raise RuntimeError(f"Open-Meteo request failed: {exc}") from exc
            return self._mock_forecast(latitude, longitude, days, f"open_meteo_error:{type(exc).__name__}")
        finally:
            if owns_client:
                await client.aclose()

    def _normalize(self, raw: dict[str, Any], latitude: float, longitude: float) -> dict[str, Any]:
        daily = raw.get("daily") or {}
        dates = daily.get("time") or []
        keys = [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "precipitation_sum",
            "precipitation_probability_max",
            "relative_humidity_2m_mean",
            "et0_fao_evapotranspiration",
        ]
        days: list[dict[str, Any]] = []
        for index, day in enumerate(dates):
            item = {"date": day}
            for key in keys:
                values = daily.get(key) or []
                item[key] = values[index] if index < len(values) else None
            days.append(item)
        if not days:
            raise ValueError("Open-Meteo response contained no daily forecast")

        rain = [float(item.get("precipitation_sum") or 0) for item in days]
        maximums = [float(item["temperature_2m_max"]) for item in days if item.get("temperature_2m_max") is not None]
        minimums = [float(item["temperature_2m_min"]) for item in days if item.get("temperature_2m_min") is not None]
        means = [float(item["temperature_2m_mean"]) for item in days if item.get("temperature_2m_mean") is not None]
        humidity = [float(item["relative_humidity_2m_mean"]) for item in days if item.get("relative_humidity_2m_mean") is not None]
        probabilities = [float(item["precipitation_probability_max"]) for item in days if item.get("precipitation_probability_max") is not None]
        summary = {
            "rainfall_next_48h_mm": round(sum(rain[:2]), 2),
            "rainfall_next_72h_mm": round(sum(rain[:3]), 2),
            "rainfall_next_5d_mm": round(sum(rain[:5]), 2),
            "rainfall_forecast_total_mm": round(sum(rain), 2),
            "temperature_avg_c": round(sum(means) / len(means), 2) if means else None,
            "temperature_min_c": round(min(minimums), 2) if minimums else None,
            "temperature_max_c": round(max(maximums), 2) if maximums else None,
            "humidity_avg_percent": round(sum(humidity) / len(humidity), 2) if humidity else None,
            "precipitation_probability_max_percent": round(max(probabilities), 2) if probabilities else None,
            "heavy_rain_next_48h": sum(rain[:2]) >= 25,
            "heavy_rain_next_72h": sum(rain[:3]) >= 40,
            "dry_next_5d": sum(rain[:5]) < 10,
            "forecast_start": days[0]["date"],
            "forecast_end": days[-1]["date"],
        }
        return {
            "latitude_requested": latitude,
            "longitude_requested": longitude,
            "latitude_grid": raw.get("latitude"),
            "longitude_grid": raw.get("longitude"),
            "timezone": raw.get("timezone"),
            "current": raw.get("current") or {},
            "days": days,
            "summary": summary,
            "source": "open_meteo_live",
            "is_mock": False,
            "raw": raw,
            "attribution": "Weather forecast: Open-Meteo",
        }

    def _mock_forecast(self, latitude: float, longitude: float, days: int, reason: str) -> dict[str, Any]:
        start = datetime.now(UTC).date()
        output_days = []
        seed = int(abs(latitude * 1000) + abs(longitude * 1000))
        for offset in range(days):
            wave = math.sin((seed + offset) / 3.0)
            rain = round(max(0.0, 8 + 12 * wave), 1)
            temp_mean = round(27 + 2.5 * math.sin((seed + offset) / 5.0), 1)
            output_days.append(
                {
                    "date": (start + timedelta(days=offset)).isoformat(),
                    "weather_code": 61 if rain > 5 else 2,
                    "temperature_2m_max": round(temp_mean + 3.5, 1),
                    "temperature_2m_min": round(temp_mean - 3.0, 1),
                    "temperature_2m_mean": temp_mean,
                    "precipitation_sum": rain,
                    "precipitation_probability_max": min(95, round(25 + rain * 3)),
                    "relative_humidity_2m_mean": min(95, round(65 + rain)),
                    "et0_fao_evapotranspiration": round(max(1.5, 4.5 - rain / 10), 1),
                }
            )
        daily_payload = {key: [row.get(key) for row in output_days] for key in output_days[0] if key != "date"}
        daily_payload["time"] = [row["date"] for row in output_days]
        raw = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "Asia/Dhaka",
            "daily": daily_payload,
            "fallback_reason": reason,
        }
        normalized = self._normalize(raw, latitude, longitude)
        normalized.update(
            {
                "source": "generated_mock_weather",
                "is_mock": True,
                "raw": raw,
                "attribution": "Synthetic sandbox fallback; not Open-Meteo data",
                "cache_hit": False,
            }
        )
        return normalized
