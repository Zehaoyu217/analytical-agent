"""REST endpoint for listing available models grouped by provider.

GET /api/models — returns models available based on configured API keys:
  - Ollama: fetched live from local daemon, filtered to tool-capable models only
  - OpenRouter: shown if OPENROUTER_API_KEY is set (free models that support tools)
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_config

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

# Ollama model families known to support native tool calling.
# Used as fallback when /api/show doesn't report capabilities (older Ollama versions).
_KNOWN_TOOL_CAPABLE_PREFIXES = (
    "qwen", "gemma", "llama3", "mistral", "command-r", "phi3", "phi4",
    "deepseek-v3", "hermes", "nous-hermes", "nexusraven",
)


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


def _has_tool_capability(base_url: str, model_name: str) -> bool:
    """Return True if the Ollama model supports native tool calling.

    Checks /api/show capabilities first; falls back to known-capable prefix
    list so models aren't excluded when Ollama is older or the request times out.
    """
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/api/show",
            json={"name": model_name},
            timeout=5.0,
        )
        resp.raise_for_status()
        capabilities = resp.json().get("capabilities", [])
        if capabilities:
            return "tools" in capabilities
        # Older Ollama: no capabilities field — fall through to prefix check
    except Exception:
        logger.debug("Ollama capability check failed for %s", model_name, exc_info=True)

    name_lower = model_name.lower()
    return any(name_lower.startswith(p) for p in _KNOWN_TOOL_CAPABLE_PREFIXES)


def _fetch_ollama_models(base_url: str) -> list[ModelEntry]:
    """Fetch installed Ollama models, keeping only tool-capable ones."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        if resp.status_code != 200:
            return []
        out: list[ModelEntry] = []
        for m in resp.json().get("models") or []:
            name = str(m.get("name", ""))
            if not name:
                continue
            if not _has_tool_capability(base_url, name):
                logger.debug("ollama: skipping %s (no tool capability)", name)
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

    # Prefer env vars; fall back to config fields so .env files work either way.
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY") or config.openrouter_api_key)

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

    # Ollama local models (tool-capable only)
    ollama_models = _fetch_ollama_models(config.ollama_base_url)
    groups.append(
        ModelGroup(
            provider="ollama",
            label="Ollama (Local)",
            models=ollama_models,
            available=True,
            note="" if ollama_models else "No tool-capable models installed",
        )
    )

    return ModelsResponse(groups=groups)
