from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.context_api import router as context_router
from app.api.health import router as health_router
from app.api.sop_api import router as sop_router
from app.api.trace_api import router as trace_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Analytical Agent",
        version="0.1.0",
        description="Full-stack analytical platform for MLE, data scientists, and quants",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(context_router)
    app.include_router(sop_router)
    app.include_router(trace_router)

    return app
