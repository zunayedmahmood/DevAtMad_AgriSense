from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import BASE_DIR, get_settings
from app.dependencies import get_services
from app.services.ingestion import build_rag


settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("agrisense")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.rag_db_path.exists():
        logger.info("RAG database missing; building it now")
        build_rag(settings, force=True)
    services = get_services()
    logger.info(
        "AgriSense ready: external_mode=%s rag_documents=%s catalog_products=%s",
        settings.external_mode,
        services.rag.stats()["documents"],
        services.catalog.stats()["products"] if getattr(services, "catalog", None) else 0,
    )
    yield


from app.api.testing_routes import testing_router

app = FastAPI(
    title="AgriSense Tier-0 Sandbox",
    version="1.0.0",
    description=(
        "Tool-calling backend for conversational farm intake, Geoapify geocoding, Open-Meteo weather, "
        "persistent hybrid RAG, crop ranking, dated season planning, financial projection, memory, and visible operational traces."
    ),
    default_response_class=JSONResponse,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(testing_router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-process-time-ms"] = f"{(time.perf_counter() - started) * 1000:.3f}"
    return response


frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import RedirectResponse

    app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    @app.get("/")
    def root(request: Request) -> Any:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/ui/")
        return {
            "service": "AgriSense Tier-0 Sandbox",
            "ui": "/ui/",
            "docs": "/docs",
            "health": "/health",
            "agent": "/v1/agent/agentic-turn",
            "tools": "/v1/tools/catalog",
            "warning": "Synthetic records are explicitly labelled, hidden by default, and blocked from recommendations.",
        }
else:
    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "service": "AgriSense Tier-0 Sandbox",
            "docs": "/docs",
            "health": "/health",
            "agent": "/v1/agent/turn",
            "tools": "/v1/tools/catalog",
            "warning": "Synthetic records are explicitly labelled, hidden by default, and blocked from recommendations.",
        }


app.include_router(router)
