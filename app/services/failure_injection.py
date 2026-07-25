from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("agrisense.failure_injection")


class FailureInjectionService:
    """Service to simulate controlled failures on demand for hackathon judges & audit tests.
    
    Supported simulated failures:
    - 'weather_failure': Simulates Open-Meteo connection timeout / 503 service outage.
    - 'geocode_failure': Simulates Geoapify geocoding service failure.
    - 'rag_failure': Simulates RAG vector store search timeout / empty result.
    - 'rate_limit_failure': Simulates LLM 429 RESOURCE_EXHAUSTED quota error.
    - 'finance_discrepancy': Tampers financial calculation math to test PlanVerifier repair.
    """

    def __init__(self):
        self._global_failure_mode: Optional[str] = None

    def set_global_failure_mode(self, mode: Optional[str]) -> None:
        if mode and mode.lower() in {"none", "off", "disabled"}:
            self._global_failure_mode = None
        else:
            self._global_failure_mode = mode.lower() if mode else None
        logger.info("Controlled failure injection mode set to: %s", self._global_failure_mode)

    def get_active_failure_mode(self, request_override: Optional[str] = None) -> Optional[str]:
        if request_override and request_override.lower() not in {"none", "off", "disabled"}:
            return request_override.lower()
        return self._global_failure_mode

    def maybe_inject_tool_failure(self, tool_name: str, active_mode: Optional[str]) -> None:
        if not active_mode:
            return

        mode = active_mode.lower()
        if mode == "weather_failure" and tool_name == "get_weather_forecast":
            logger.warning("[SIMULATED FAILURE] Injecting Open-Meteo connection failure")
            raise RuntimeError("SIMULATED_FAILURE: Open-Meteo API connection timeout (HTTP 503)")

        if mode == "geocode_failure" and tool_name == "geocode_location":
            logger.warning("[SIMULATED FAILURE] Injecting Geoapify geocoding failure")
            raise RuntimeError("SIMULATED_FAILURE: Geoapify location service unavailable (HTTP 502)")

        if mode == "rag_failure" and tool_name == "retrieve_agronomy":
            logger.warning("[SIMULATED FAILURE] Injecting RAG search failure")
            raise RuntimeError("SIMULATED_FAILURE: RAG vector store search timeout")

    def transform_finance_result(self, result: dict[str, Any], active_mode: Optional[str]) -> dict[str, Any]:
        if active_mode and active_mode.lower() == "finance_discrepancy":
            logger.warning("[SIMULATED FAILURE] Tampering net profit by +5000 BDT to trigger PlanVerifier repair")
            tampered = dict(result)
            if "net_profit_bdt" in tampered:
                tampered["net_profit_bdt"] = round(tampered["net_profit_bdt"] + 5000.0, 2)
            return tampered
        return result


global_failure_service = FailureInjectionService()
