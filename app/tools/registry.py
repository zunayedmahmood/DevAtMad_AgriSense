from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.dependencies import Services
from app.schemas import FarmProfile


TOOL_CATALOG = [
    {
        "type": "function",
        "function": {
            "name": "geocode_location",
            "description": "Clean and geocode a Bangladesh farm location with Geoapify. Never pass the full farmer utterance as the address.",
            "parameters": {
                "type": "object",
                "required": ["location_text"],
                "properties": {
                    "location_text": {"type": "string"},
                    "district": {"type": "string", "nullable": True},
                    "upazila": {"type": "string", "nullable": True},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Get a real Open-Meteo forecast for coordinates and return rainfall/temperature decision summaries.",
            "parameters": {
                "type": "object",
                "required": ["latitude", "longitude"],
                "properties": {
                    "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                    "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                    "days": {"type": "integer", "minimum": 1, "maximum": 16, "default": 7},
                    "force_refresh": {"type": "boolean", "default": False},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_agronomy",
            "description": "Search the persistent hybrid RAG database over provided source-derived, provided mock, and generated mock-gap knowledge.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 8},
                    "crop_id": {"type": "string", "nullable": True},
                    "district": {"type": "string", "nullable": True},
                    "upazila": {"type": "string", "nullable": True},
                    "include_mock": {"type": "boolean", "default": True},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_crop_candidates",
            "description": "Rank at least three supported crops from a complete Tier-0 farm profile and a weather result.",
            "parameters": {
                "type": "object",
                "required": ["profile", "weather"],
                "properties": {
                    "profile": {"type": "object"},
                    "weather": {"type": "object"},
                    "top_k": {"type": "integer", "minimum": 3, "maximum": 16, "default": 3},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_financial_projection",
            "description": "Calculate inspectable mock cost, yield, revenue, net profit, ROI and break-even for a crop and farm profile.",
            "parameters": {
                "type": "object",
                "required": ["crop_id", "profile"],
                "properties": {
                    "crop_id": {"type": "string"},
                    "profile": {"type": "object"},
                    "yield_factor": {"type": "number", "minimum": 0.1, "maximum": 3, "default": 1},
                    "price_factor": {"type": "number", "minimum": 0.1, "maximum": 3, "default": 1},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_season_plan",
            "description": "Generate a dated land-preparation-to-harvest plan for a chosen crop, with fertilizer, irrigation, pest checkpoints, finance, and weather-refresh markers.",
            "parameters": {
                "type": "object",
                "required": ["crop_id", "profile", "weather"],
                "properties": {
                    "crop_id": {"type": "string"},
                    "profile": {"type": "object"},
                    "weather": {"type": "object"},
                    "yield_factor": {"type": "number", "minimum": 0.1, "maximum": 3, "default": 1},
                },
            },
        },
    },
]


class ToolRegistry:
    def __init__(self, services: Services):
        self.services = services

    @property
    def catalog(self) -> list[dict[str, Any]]:
        return TOOL_CATALOG

    async def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        functions: dict[str, Callable[[dict[str, Any]], Awaitable[Any] | Any]] = {
            "geocode_location": self._geocode,
            "get_weather_forecast": self._weather,
            "retrieve_agronomy": self._rag,
            "rank_crop_candidates": self._rank,
            "calculate_financial_projection": self._finance,
            "generate_season_plan": self._plan,
        }
        if name not in functions:
            raise KeyError(f"Unknown tool: {name}")
        result = functions[name](arguments)
        if hasattr(result, "__await__"):
            result = await result
        return result

    async def _geocode(self, args: dict[str, Any]) -> Any:
        normalized = self.services.location_normalizer.extract(args["location_text"])
        district = args.get("district") or normalized.district
        upazila = args.get("upazila") or normalized.upazila
        location_text = normalized.location_text or args["location_text"]
        return await self.services.geocoder.geocode(
            location_text,
            district=district,
            upazila=upazila,
            exact_catalog_match=normalized.exact_catalog_match,
        )

    async def _weather(self, args: dict[str, Any]) -> Any:
        return await self.services.weather.forecast(
            float(args["latitude"]),
            float(args["longitude"]),
            days=int(args.get("days", 7)),
            force_refresh=bool(args.get("force_refresh", False)),
        )

    def _rag(self, args: dict[str, Any]) -> Any:
        return [
            item.model_dump(mode="json")
            for item in self.services.rag.search(
                args["query"],
                top_k=int(args.get("top_k", 8)),
                crop_id=args.get("crop_id"),
                district=args.get("district"),
                upazila=args.get("upazila"),
                include_mock=bool(args.get("include_mock", True)),
            )
        ]

    def _rank(self, args: dict[str, Any]) -> Any:
        profile = FarmProfile.model_validate(args["profile"])
        return [
            item.model_dump(mode="json")
            for item in self.services.recommender.rank(profile, args["weather"], int(args.get("top_k", 3)))
        ]

    def _finance(self, args: dict[str, Any]) -> Any:
        profile = FarmProfile.model_validate(args["profile"])
        return self.services.finance.calculate(
            args["crop_id"],
            profile,
            yield_factor=float(args.get("yield_factor", 1.0)),
            price_factor=float(args.get("price_factor", 1.0)),
        ).model_dump(mode="json")

    def _plan(self, args: dict[str, Any]) -> Any:
        profile = FarmProfile.model_validate(args["profile"])
        return self.services.planner.build(
            args["crop_id"],
            profile,
            args["weather"],
            recommendation_yield_factor=float(args.get("yield_factor", 1.0)),
        ).model_dump(mode="json")
