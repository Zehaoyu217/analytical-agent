from __future__ import annotations

import importlib.util
import os
from typing import Literal

import httpx

Provider = Literal["ollama", "openrouter", "anthropic", "mlx"]


def ollama_base_url(override: str | None = None) -> str:
    return (override or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")


def ollama_num_ctx(default: int = 8192) -> int:
    raw = os.environ.get("SECOND_BRAIN_OLLAMA_NUM_CTX")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def ollama_model_name(model: str) -> str:
    return model.split("/", 1)[1] if model.startswith("ollama/") else model


def mlx_model_name(model: str) -> str:
    return model.split("/", 1)[1] if model.startswith("mlx/") else model


def anthropic_model_name(model: str) -> str:
    return model.split("/", 1)[1] if model.startswith("anthropic/") else model


def is_ollama_model(model: str) -> bool:
    return model.startswith("ollama/") or "/" not in model


def is_mlx_model(model: str) -> bool:
    return model.startswith("mlx/")


def is_anthropic_model(model: str) -> bool:
    return model.startswith("anthropic/") or model.startswith("claude-")


def resolve_provider(
    model: str,
    *,
    openrouter_key: str | None,
    anthropic_key: str | None,
) -> Provider:
    if model.startswith("claude-"):
        if anthropic_key:
            return "anthropic"
        raise RuntimeError(f"ANTHROPIC_API_KEY not set for model {model}")
    if model.startswith("anthropic/"):
        if openrouter_key:
            return "openrouter"
        if anthropic_key:
            return "anthropic"
        raise RuntimeError(
            f"no provider configured for {model}; set OPENROUTER_API_KEY or ANTHROPIC_API_KEY"
        )
    if is_mlx_model(model):
        return "mlx"
    if is_ollama_model(model):
        return "ollama"
    if "/" in model:
        if openrouter_key:
            return "openrouter"
        raise RuntimeError(f"OPENROUTER_API_KEY not set for model {model}")
    return "ollama"


def model_readiness(
    model: str,
    *,
    openrouter_key: str | None,
    anthropic_key: str | None,
    ollama_host: str | None = None,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 2.0,
) -> tuple[bool, str]:
    try:
        provider = resolve_provider(
            model,
            openrouter_key=openrouter_key,
            anthropic_key=anthropic_key,
        )
    except RuntimeError as exc:
        return False, str(exc)

    if provider == "mlx":
        if importlib.util.find_spec("mlx_lm") is None:
            return False, "mlx-lm is not installed"
        return True, "mlx"

    if provider != "ollama":
        return True, provider

    bare_model = ollama_model_name(model)
    url = f"{ollama_base_url(ollama_host)}/api/tags"
    client_kwargs: dict[str, object] = {"timeout": timeout}
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        return False, f"ollama unavailable: {exc}"
    if resp.status_code >= 400:
        return False, f"ollama HTTP {resp.status_code}"
    try:
        body = resp.json()
    except ValueError as exc:
        return False, f"ollama returned non-JSON tags payload: {exc}"
    names = {str(item.get('name', '')) for item in body.get("models") or []}
    if bare_model not in names:
        return False, f"Ollama model {bare_model} is not installed"
    return True, "ollama"
