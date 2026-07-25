from __future__ import annotations

import pytest
from app.services.batch_tester import global_batch_tester, BENCHMARK_PROMPTS
from app.services.failure_injection import global_failure_service


def test_benchmark_prompts_loaded():
    assert len(BENCHMARK_PROMPTS) >= 20
    assert "Shibchar" in BENCHMARK_PROMPTS[3]


def test_failure_injection_service():
    global_failure_service.set_global_failure_mode("weather_failure")
    assert global_failure_service.get_active_failure_mode() == "weather_failure"
    
    with pytest.raises(RuntimeError) as exc_info:
        global_failure_service.maybe_inject_tool_failure("get_weather_forecast", "weather_failure")
    assert "SIMULATED_FAILURE" in str(exc_info.value)

    global_failure_service.set_global_failure_mode(None)
    assert global_failure_service.get_active_failure_mode() is None


def test_batch_tester_initial_status():
    status = global_batch_tester.get_status()
    assert "is_running" in status
    assert "total_count" in status
