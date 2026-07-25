from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.dependencies import Services, get_services
from app.services.batch_tester import global_batch_tester, BENCHMARK_PROMPTS
from app.services.failure_injection import global_failure_service

testing_router = APIRouter(prefix="/v1/testing", tags=["automated-testing"])


class StartBatchRequest(BaseModel):
    target_count: int = 100
    failure_mode: str = "mixed"  # 'none', 'mixed', 'weather_failure', 'geocode_failure', 'rag_failure', 'rate_limit_failure', 'finance_discrepancy'


class ControlBatchRequest(BaseModel):
    action: str  # 'pause', 'resume', 'cancel'


class SetFailureModeRequest(BaseModel):
    failure_mode: Optional[str] = None


@testing_router.get("/prompts")
def get_benchmark_prompts() -> dict[str, Any]:
    return {"count": len(BENCHMARK_PROMPTS), "prompts": BENCHMARK_PROMPTS}


@testing_router.post("/start-batch")
async def start_batch(req: StartBatchRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    try:
        await global_batch_tester.start_batch(services, req.target_count, req.failure_mode)
        return {"status": "started", "target_count": req.target_count, "failure_mode": req.failure_mode}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@testing_router.post("/control")
def control_batch(req: ControlBatchRequest) -> dict[str, Any]:
    act = req.action.lower()
    if act == "pause":
        global_batch_tester.pause()
    elif act == "resume":
        global_batch_tester.resume()
    elif act == "cancel":
        global_batch_tester.cancel()
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'pause', 'resume', or 'cancel'.")
    return {"status": "ok", "action": act, "batch_status": global_batch_tester.get_status()}


@testing_router.get("/status")
def get_batch_status() -> dict[str, Any]:
    status = global_batch_tester.get_status()
    status["results"] = global_batch_tester.results[-50:]  # Return latest 50 for live table UI
    return status


@testing_router.post("/set-failure-mode")
def set_failure_mode(req: SetFailureModeRequest) -> dict[str, Any]:
    global_failure_service.set_global_failure_mode(req.failure_mode)
    return {"status": "ok", "active_failure_mode": global_failure_service.get_active_failure_mode()}


@testing_router.get("/export-json")
def export_batch_json() -> Response:
    """Exports full execution JSON containing complete prompts, traces, thinking, and outputs for all batch tests."""
    data = {
        "export_timestamp": Response.headers if hasattr(Response, "headers") else "now",
        "summary": global_batch_tester.get_status(),
        "all_test_results": global_batch_tester.results
    }
    content = JSONResponse(content=data).body
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=agrisense_batch_test_results.json"}
    )
