import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.chat_api import router as chat_router
from app.api.config_api import router as config_router
from app.api.context_api import router as context_router
from app.api.conversations_api import router as conversations_router
from app.api.data_status_api import router as data_status_router
from app.api.datasets_api import router as datasets_router
from app.api.files_api import router as files_router
from app.api.health import router as health_router
from app.api.hooks_api import router as hooks_router
from app.api.mcp_sampling_api import router as mcp_sampling_router
from app.api.models_api import router as models_router
from app.api.prompts_api import router as prompts_router
from app.api.sb_api import router as sb_router
from app.api.sb_gardener import router as sb_gardener_router
from app.api.sb_pipeline import router as sb_pipeline_router
from app.api.scheduler_api import router as scheduler_router
from app.api.session_search_api import router as session_search_router
from app.api.settings_api import router as settings_router
from app.api.skills_api import router as skills_router
from app.api.skills_telemetry_api import router as skills_telemetry_router
from app.api.slash_api import router as slash_router
from app.api.sop_api import router as sop_router
from app.api.todos_api import router as todos_router
from app.api.trace_api import router as trace_router
from app.api.uploads_api import router as uploads_router
from app.api.wiki_api import router as wiki_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the cron engine on startup and shut it down gracefully on exit."""
    from app.harness.wiring import get_cron_engine  # noqa: PLC0415

    engine = get_cron_engine()
    engine.start()
    try:
        yield
    finally:
        engine.stop()


def create_app() -> FastAPI:
    from app.data.db_init import initialize_db
    initialize_db()

    app = FastAPI(
        title="Analytical Agent",
        version="0.1.0",
        description="Full-stack analytical platform for MLE, data scientists, and quants",
        lifespan=lifespan,
    )

    _cors_origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _override = os.environ.get("INTEGRITY_HEALTH_DIR")
    if _override:
        _health_dir = Path(_override)
    else:
        _health_dir = Path(__file__).resolve().parents[2] / "docs" / "health"
    if _health_dir.is_dir():
        app.mount("/static/health", StaticFiles(directory=str(_health_dir)), name="health-static")

    try:
        from prometheus_fastapi_instrumentator import Instrumentator  # noqa: PLC0415

        from app.metrics import active_sessions_gauge  # noqa: PLC0415, F401

        Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except ImportError:
        pass  # prometheus-fastapi-instrumentator not installed — metrics endpoint disabled

    app.include_router(health_router)
    app.include_router(context_router)
    app.include_router(sop_router)
    app.include_router(trace_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(uploads_router)
    app.include_router(settings_router)
    app.include_router(models_router)
    app.include_router(files_router)
    app.include_router(prompts_router)
    app.include_router(skills_router)
    app.include_router(slash_router)
    app.include_router(datasets_router)
    app.include_router(data_status_router)
    app.include_router(todos_router)
    app.include_router(hooks_router)
    app.include_router(session_search_router)
    app.include_router(scheduler_router)
    app.include_router(mcp_sampling_router)
    app.include_router(config_router)
    app.include_router(sb_router)
    app.include_router(sb_pipeline_router)
    app.include_router(sb_gardener_router)
    app.include_router(skills_telemetry_router)
    app.include_router(wiki_router)

    return app
