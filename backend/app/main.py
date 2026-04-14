from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat_api import router as chat_router
from app.api.datasets_api import router as datasets_router
from app.api.context_api import router as context_router
from app.api.conversations_api import router as conversations_router
from app.api.files_api import router as files_router
from app.api.health import router as health_router
from app.api.models_api import router as models_router
from app.api.settings_api import router as settings_router
from app.api.skills_api import router as skills_router
from app.api.slash_api import router as slash_router
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
    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(settings_router)
    app.include_router(models_router)
    app.include_router(files_router)
    app.include_router(skills_router)
    app.include_router(slash_router)
    app.include_router(datasets_router)

    return app
