from __future__ import annotations

import httpx

from app.services.geocoding import GeoapifyClient
from app.services.weather import OpenMeteoClient


async def test_geoapify_live_request_uses_clean_text_and_bangladesh_filter(services):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "lat": 24.4829,
                        "lon": 91.7774,
                        "formatted": "Moulvibazar, Sylhet Division, Bangladesh",
                        "country_code": "bd",
                        "county": "Moulvibazar District",
                        "result_type": "city",
                        "place_id": "mock-place-id",
                        "rank": {
                            "confidence": 0.96,
                            "confidence_city_level": 0.99,
                            "match_type": "full_match",
                        },
                    }
                ],
                "query": {"text": "Moulvibazar, Bangladesh"},
            },
        )

    settings = services.settings.model_copy(
        update={"external_mode": "live", "geoapify_api_key": "test-secret"}
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        geo = GeoapifyClient(settings, services.database, services.kb, client=client)
        result = await geo.geocode(
            "Moulvibazar", district="Moulvibazar", exact_catalog_match=True
        )

    assert captured["params"]["text"] == "Moulvibazar, Bangladesh"
    assert captured["params"]["filter"] == "countrycode:bd"
    assert captured["params"]["apiKey"] == "test-secret"
    assert result["source"] == "geoapify_live"
    assert result["is_mock"] is False


async def test_open_meteo_live_response_is_normalized(services):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "latitude": 24.5,
                "longitude": 91.8,
                "timezone": "Asia/Dhaka",
                "current": {
                    "temperature_2m": 29.1,
                    "relative_humidity_2m": 82,
                    "precipitation": 0,
                    "rain": 0,
                    "weather_code": 3,
                },
                "daily": {
                    "time": ["2026-07-24", "2026-07-25", "2026-07-26"],
                    "weather_code": [3, 61, 63],
                    "temperature_2m_max": [32, 31, 30],
                    "temperature_2m_min": [25, 25, 24],
                    "temperature_2m_mean": [28, 28, 27],
                    "precipitation_sum": [2, 15, 30],
                    "precipitation_probability_max": [30, 80, 90],
                    "relative_humidity_2m_mean": [75, 84, 88],
                    "et0_fao_evapotranspiration": [4, 3, 2],
                },
            },
        )

    settings = services.settings.model_copy(update={"external_mode": "live"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        weather = OpenMeteoClient(settings, services.database, client=client)
        result = await weather.forecast(24.5, 91.8, days=3, force_refresh=True)

    assert captured["params"]["forecast_days"] == "3"
    assert "precipitation_sum" in captured["params"]["daily"]
    assert result["source"] == "open_meteo_live"
    assert result["is_mock"] is False
    assert result["summary"]["rainfall_next_72h_mm"] == 47
    assert result["summary"]["heavy_rain_next_72h"] is True
