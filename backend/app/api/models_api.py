"""REST endpoint for listing available models grouped by provider.

GET /api/models — returns models available based on configured API keys:
  - OpenRouter: shown if OPENROUTER_API_KEY is set (free models that support tools)
  - MLX: shown when mlx-lm is installed; lists only locally-cached models
"""
from __future__ import annotations

import importlib.util
import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_config
from app.harness.clients.mlx_client import cached_model_ids

router = APIRouter(prefix="/api/models", tags=["models"])
logger = logging.getLogger(__name__)

# OpenRouter models (requires OPENROUTER_API_KEY).
# Only models that report "tools" in their supported_parameters are listed.
# IDs with "/" route through the OpenRouter client in chat_api.py.
_OPENROUTER_MODELS = [
    {
        "id": "openai/gpt-oss-120b:free",
        "label": "GPT-OSS 120B",
        "description": "OpenAI · 120B · Free",
    },
    {
        "id": "meta-llama/llama-3.3-70b-instruct:free",
        "label": "Llama 3.3 70B",
        "description": "Meta · 70B · Free",
    },
    {
        "id": "qwen/qwen3-coder:free",
        "label": "Qwen3 Coder",
        "description": "Qwen · Free",
    },
    {
        "id": "google/gemma-4-31b-it:free",
        "label": "Gemma 4 31B",
        "description": "Google · 31B · Free",
    },
    {
        "id": "nvidia/nemotron-3-super-120b-a12b:free",
        "label": "Nemotron 3 Super 120B",
        "description": "NVIDIA · 120B · Free",
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


# Curated human-readable labels for known MLX models.
# Lookup is by full model_id (including the "mlx/" prefix). Any id not in
# this map falls back to :func:`_humanize_mlx_id`, which strips the prefix
# and replaces hyphens with spaces.
# Gemma 4 is natively multimodal. The mlx-community / NexVeridian builds keep
# the vision tower → "Vision". The jorch "-lm" builds strip it out → "Text".
_MLX_LABEL_MAP: dict[str, str] = {
    "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit": "Gemma 4 E4B Vision",
    "mlx/NexVeridian/gemma-4-26B-A4b-it-4bit": "Gemma 4 26B A4B Vision",
    "mlx/jorch/gemma-4-e2b-it-lm-4bit": "Gemma 4 E2B Text",
    "mlx/jorch/gemma-4-e4b-it-lm-4bit": "Gemma 4 E4B Text",
    "mlx/mlx-community/Qwen3.5-9B-OptiQ-4bit": "Qwen3.5 9B",
}


def _mlx_runtime_available() -> bool:
    return importlib.util.find_spec("mlx_lm") is not None


def _humanize_mlx_id(model_id: str) -> str:
    """Best-effort label for MLX ids not in ``_MLX_LABEL_MAP``."""
    bare = model_id.removeprefix("mlx/")
    if bare.startswith("mlx-community/"):
        bare = bare.removeprefix("mlx-community/")
    return bare.replace("-", " ")


def _mlx_label(model_id: str) -> str:
    """Return the curated label for *model_id*, or fall back to the humanizer."""
    return _MLX_LABEL_MAP.get(model_id) or _humanize_mlx_id(model_id)


def _fetch_mlx_models() -> list[ModelEntry]:
    """Return only MLX models that are actually cached on-disk.

    We deliberately do not surface an aspirational "recommended" list — if a
    model isn't downloaded, picking it from a dropdown would stall on a
    multi-gigabyte fetch. Users who want new MLX models should download them
    explicitly via ``hf download`` or ``mlx_lm.generate`` first.
    """
    return [
        ModelEntry(
            id=model_id,
            label=_mlx_label(model_id),
            description="MLX local · cached",
        )
        for model_id in sorted(cached_model_ids())
    ]


@router.get("")
def list_models() -> ModelsResponse:
    config = get_config()

    # Prefer env vars; fall back to config fields so .env files work either way.
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY") or config.openrouter_api_key)
    has_mlx = _mlx_runtime_available()

    groups: list[ModelGroup] = []

    # OpenRouter (free models — GPT-OSS, Nemotron, Gemini, Llama, DeepSeek)
    groups.append(
        ModelGroup(
            provider="openrouter",
            label="OpenRouter (Free)",
            models=[ModelEntry(**m) for m in _OPENROUTER_MODELS],
            available=has_openrouter,
            note="" if has_openrouter else "Set OPENROUTER_API_KEY to enable",
        )
    )

    # MLX local models (Apple Silicon, on-demand download via Hugging Face)
    mlx_models = _fetch_mlx_models() if has_mlx else []
    groups.append(
        ModelGroup(
            provider="mlx",
            label="MLX (Local)",
            models=mlx_models,
            available=has_mlx,
            note=(
                ""
                if has_mlx
                else "Install backend[mlx] on Apple Silicon to enable local MLX models"
            ),
        )
    )

    return ModelsResponse(groups=groups)
