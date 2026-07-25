from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

from app.schemas import AgentTurnRequest
from app.services.failure_injection import global_failure_service

logger = logging.getLogger("agrisense.batch_tester")

# Benchmark prompt template list covering Bangladeshi farming scenarios across districts, soil types, crops, and budgets
BENCHMARK_PROMPTS = [
    "we have a plot of land in moulovibazar. it is 2 acre and has reliable irrigation and sandy-loamy soil. wehave a budget of 60 thousand taka. we are planing for the boro season.",
    "my farm is in rangpur. 1.5 bigha, loam soil, tubewell water. budget 25000 taka for rabi season wheat or maize.",
    "আমার বাড়ি ময়মনসিংহে। ৩ একর জমি আছে, পলি মাটি, খাল থেকে পানি আনবো। ৪০ হাজার টাকা বাজেট।",
    "we have 2 acres in Shibchar Madaripur. sandy loam soil, canal water, budget 50000 BDT for garlic cultivation.",
    "farm located in Bogra, 1 acre land, clay loam, shallow tubewell, budget 35000 BDT for potato.",
    "3 bigha land in Comilla, silt loam soil, rainfed irrigation, budget 45000 BDT for aman rice.",
    "farm in Jessore, 2.5 acres, sandy clay loam, deep tubewell, budget 70000 BDT for mustard and vegetables.",
    "2 bigha land in Dinajpur, sandy loam, tubewell water, budget 30000 BDT for maize cultivation.",
    "farm in Sylhet, 2 acres tea garden land, hilly loam, rainfed, budget 60000 BDT for tea and pineapple.",
    "1.8 acre plot in Rajshahi, sandy soil, river water, budget 40000 BDT for mango intercropping.",
    "farm in Khulna, 2 bigha saline soil, brackish water access, budget 50000 BDT for watermelon.",
    "farm in Barisal, 3 acres low-lying land, canal water, budget 65000 BDT for aus rice.",
    "farm in Mymensingh, 1 acre loam, tubewell water, budget 20000 BDT for brinjal (begun).",
    "farm in Tangail, 2.2 acres clay loam, river irrigation, budget 55000 BDT for boro rice.",
    "farm in Kushtia, 1.5 bigha loam soil, tubewell water, budget 28000 BDT for tobacco or mustard.",
    "farm in Pabna, 2 acres silt loam, canal water, budget 48000 BDT for onion and chili.",
    "farm in Faridpur, 1 acre sandy loam, river water, budget 32000 BDT for jute cultivation.",
    "farm in Noakhali, 2.5 bigha saline loam, rainfed, budget 38000 BDT for groundnut.",
    "farm in Cox's Bazar, 1.2 acres sandy soil, rainfed, budget 42000 BDT for betel leaf and coconut.",
    "farm in Jamalpur, 2 acres silt loam, tubewell water, budget 50000 BDT for mustard."
]

SIMULATED_FAILURES_LIST = [
    "none",
    "weather_failure",
    "geocode_failure",
    "rag_failure",
    "rate_limit_failure",
    "finance_discrepancy"
]


class BatchTestingManager:
    """Manages automated batch test execution across up to 1200 prompts.
    
    Provides:
    - Start, Pause, Resume, Cancel batch test runs.
    - Live progress metrics (completed count, success rate, avg latency, active prompt).
    - Controlled failure injection mixing across prompts.
    - Single-click large JSON export of full chat prompts, traces, thinking, and outputs.
    """

    def __init__(self):
        self.is_running: bool = False
        self.is_paused: bool = False
        self.is_cancelled: bool = False

        self.total_count: int = 0
        self.completed_count: int = 0
        self.success_count: int = 0
        self.fallback_handled_count: int = 0
        self.failure_injected_count: int = 0
        
        self.current_prompt: str = ""
        self.current_failure_mode: str = "none"
        self.start_time: float = 0.0
        self.elapsed_seconds: float = 0.0

        self.results: List[Dict[str, Any]] = []
        self._task: Optional[asyncio.Task] = None

    def get_status(self) -> Dict[str, Any]:
        duration = (time.time() - self.start_time) if (self.is_running and self.start_time > 0) else self.elapsed_seconds
        avg_latency = (duration / self.completed_count * 1000) if self.completed_count > 0 else 0.0
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "is_cancelled": self.is_cancelled,
            "total_count": self.total_count,
            "completed_count": self.completed_count,
            "success_count": self.success_count,
            "fallback_handled_count": self.fallback_handled_count,
            "failure_injected_count": self.failure_injected_count,
            "current_prompt": self.current_prompt,
            "current_failure_mode": self.current_failure_mode,
            "elapsed_seconds": round(duration, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "results_count": len(self.results)
        }

    async def start_batch(self, services: Any, target_count: int = 100, failure_mode: str = "mixed") -> None:
        if self.is_running:
            raise RuntimeError("Batch testing is already running.")

        self.is_running = True
        self.is_paused = False
        self.is_cancelled = False
        self.total_count = min(max(1, target_count), 1200)
        self.completed_count = 0
        self.success_count = 0
        self.fallback_handled_count = 0
        self.failure_injected_count = 0
        self.results = []
        self.start_time = time.time()

        self._task = asyncio.create_task(self._run_batch_worker(services, failure_mode))

    def pause(self) -> None:
        if self.is_running:
            self.is_paused = True
            logger.info("Batch testing PAUSED.")

    def resume(self) -> None:
        if self.is_running and self.is_paused:
            self.is_paused = False
            logger.info("Batch testing RESUMED.")

    def cancel(self) -> None:
        if self.is_running:
            self.is_cancelled = True
            self.is_running = False
            if self._task and not self._task.done():
                self._task.cancel()
            logger.info("Batch testing CANCELLED.")

    async def _run_batch_worker(self, services: Any, failure_mode: str) -> None:
        logger.info("Starting automated batch test worker for %d prompts (Mode: %s)...", self.total_count, failure_mode)
        try:
            for idx in range(1, self.total_count + 1):
                while self.is_paused:
                    if self.is_cancelled:
                        break
                    await asyncio.sleep(0.5)

                if self.is_cancelled:
                    logger.info("Worker stopped due to cancellation.")
                    break

                # Pick prompt from benchmark dataset (loop with duplication for large counts up to 1200)
                prompt_text = BENCHMARK_PROMPTS[(idx - 1) % len(BENCHMARK_PROMPTS)]
                if idx > len(BENCHMARK_PROMPTS):
                    prompt_text += f" (Variation #{idx})"

                # Determine failure mode for this prompt
                if failure_mode == "mixed":
                    selected_fail = SIMULATED_FAILURES_LIST[idx % len(SIMULATED_FAILURES_LIST)]
                else:
                    selected_fail = failure_mode

                self.current_prompt = prompt_text
                self.current_failure_mode = selected_fail
                if selected_fail != "none":
                    self.failure_injected_count += 1

                # Execute turn
                t_start = time.perf_counter()
                session_id = f"batch_test_session_{idx}_{int(time.time())}"
                farmer_id = f"batch_farmer_{idx % 100}"

                req = AgentTurnRequest(
                    session_id=session_id,
                    farmer_id=farmer_id,
                    message=prompt_text
                )

                # Set temporary failure injection mode
                global_failure_service.set_global_failure_mode(selected_fail)

                try:
                    turn_resp = await services.controller.handle_turn(req)
                    t_duration = round((time.perf_counter() - t_start) * 1000, 2)
                    
                    is_fallback = "fallback" in (turn_resp.message or "").lower() or selected_fail != "none"
                    if is_fallback:
                        self.fallback_handled_count += 1
                    else:
                        self.success_count += 1

                    result_item = {
                        "test_id": idx,
                        "session_id": session_id,
                        "prompt": prompt_text,
                        "simulated_failure": selected_fail,
                        "status": turn_resp.status,
                        "duration_ms": t_duration,
                        "response_message": turn_resp.message,
                        "profile": turn_resp.profile.model_dump(mode="json") if turn_resp.profile else {},
                        "missing_fields": turn_resp.missing_fields,
                        "trace": [item.model_dump(mode="json") for item in turn_resp.trace] if turn_resp.trace else []
                    }
                    self.results.append(result_item)
                except Exception as exc:
                    t_duration = round((time.perf_counter() - t_start) * 1000, 2)
                    self.fallback_handled_count += 1
                    result_item = {
                        "test_id": idx,
                        "session_id": session_id,
                        "prompt": prompt_text,
                        "simulated_failure": selected_fail,
                        "status": "error_handled",
                        "duration_ms": t_duration,
                        "response_message": f"Handled exception: {str(exc)}",
                        "profile": {},
                        "missing_fields": [],
                        "trace": []
                    }
                    self.results.append(result_item)
                finally:
                    global_failure_service.set_global_failure_mode(None)

                self.completed_count = idx
                await asyncio.sleep(0.05)  # Yield control to event loop

            self.elapsed_seconds = round(time.time() - self.start_time, 1)
            logger.info("Batch testing completed successfully. %d items processed.", self.completed_count)
        except asyncio.CancelledError:
            logger.info("Batch testing task cancelled.")
        except Exception as err:
            logger.error("Error in batch test worker: %s", str(err), exc_info=True)
        finally:
            self.is_running = False
            self.is_paused = False


global_batch_tester = BatchTestingManager()
