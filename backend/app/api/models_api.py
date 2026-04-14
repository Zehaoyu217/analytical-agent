"""REST endpoint for listing available models grouped by provider.

GET /api/models — returns OpenRouter free large models (static, available only
when OPENROUTER_API_KEY is set) and Ollama models fetched live from the local
daemon.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_config

router = APIRouter(prefix="/api/models", tags=["models"])
logger = logging.getLogger(__name__)

# The two free ~120B models on OpenRouter (as of 2026-04).
_OPENROUTER_FREE_MODELS = [
    {
        "id": "meta-llama/llama-4-scout:free",
        "label": "Llama 4 Scout",
        "description": "109B · Free",
    },
    {
        "id": "meta-llama/llama-4-maverick:free",
        "label": "Llama 4 Maverick",
        "description": "400B MoE · Free",
    },
]


class ModelEntry(BaseModel):
    id: str
    label: str
    description: str


class ModelGroup(BaseModel):
    provider: str
    label: str
    models: list[ModelEntry]
    available: bool = True
    note: str = ""


class ModelsResponse(BaseModel):
    groups: list[ModelGroup]


def _fetch_ollama_models(base_url: str) -> list[ModelEntry]:
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        if resp.status_code != 200:
            return []
        out: list[ModelEntry] = []
        for m in resp.json().get("models") or []:
            name = str(m.get("name", ""))
            if not name:
                continue
            size = str((m.get("details") or {}).get("parameter_size") or "")
            desc = f"Local · {size}" if size else "Local"
            out.append(ModelEntry(id=name, label=name, description=desc))
        return out
    except Exception as exc:
        logger.debug("ollama unavailable: %s", exc)
        return []


@router.get("")
def list_models() -> ModelsResponse:
    config = get_config()
    has_openrouter_key = bool(config.openrouter_api_key)
    ollama_models = _fetch_ollama_models(config.ollama_base_url)

    groups: list[ModelGroup] = [
        ModelGroup(
            provider="openrouter",
            label="OpenRouter (Free)",
            models=[ModelEntry(**m) for m in _OPENROUTER_FREE_MODELS],
            available=has_openrouter_key,
            note="" if has_openrouter_key else "Set OPENROUTER_API_KEY to enable",
        ),
    ]
    if ollama_models:
        groups.append(
            ModelGroup(
                provider="ollama",
                label="Ollama (Local)",
                models=ollama_models,
                available=True,
            )
        )
    return ModelsResponse(groups=groups)
