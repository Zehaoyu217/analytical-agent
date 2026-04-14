from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_TIERS = frozenset({"strict", "advisory", "observatory"})
VALID_PROVIDERS = frozenset({"anthropic", "ollama", "openrouter"})
VALID_MODES = frozenset({"config", "auto"})


@dataclass(frozen=True, slots=True)
class ModelProfile:
    name: str
    provider: str
    model_id: str
    tier: str
    thinking_budget: int | None = None
    host: str | None = None
    keep_alive: str | None = None
    num_ctx: int | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuardrailConfig:
    mode: str
    retry_on_gate_block: str | None


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    mode: str
    models: dict[str, ModelProfile]
    roles: dict[str, str]
    warmup: tuple[str, ...]
    guardrails: GuardrailConfig


def _parse_model(name: str, raw: dict[str, Any]) -> ModelProfile:
    provider = str(raw.get("provider", "")).strip()
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"model '{name}': provider '{provider}' not in {sorted(VALID_PROVIDERS)}")
    tier = str(raw.get("tier", "")).strip()
    if tier not in VALID_TIERS:
        raise ValueError(f"model '{name}': tier '{tier}' not in {sorted(VALID_TIERS)}")
    return ModelProfile(
        name=name,
        provider=provider,
        model_id=str(raw["model_id"]),
        tier=tier,
        thinking_budget=raw.get("thinking_budget"),
        host=raw.get("host"),
        keep_alive=raw.get("keep_alive"),
        num_ctx=raw.get("num_ctx"),
        options=dict(raw.get("options") or {}),
    )


def load_config(path: str | Path) -> HarnessConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    mode = str(raw.get("mode", "config"))
    if mode not in VALID_MODES:
        raise ValueError(f"mode '{mode}' not in {sorted(VALID_MODES)}")

    models_raw = raw.get("models") or {}
    models = {name: _parse_model(name, data) for name, data in models_raw.items()}

    roles_raw = raw.get("roles") or {}
    roles: dict[str, str] = {}
    for role, target in roles_raw.items():
        if target not in models:
            raise ValueError(
                f"role '{role}' points at '{target}' which is not declared in models."
            )
        roles[str(role)] = str(target)

    warmup_raw = raw.get("warmup") or []
    for entry in warmup_raw:
        if entry not in models:
            raise ValueError(f"warmup entry '{entry}' not declared in models.")
    warmup = tuple(str(e) for e in warmup_raw)

    guard_raw = raw.get("guardrails") or {}
    guardrails = GuardrailConfig(
        mode=str(guard_raw.get("mode", "per_tier")),
        retry_on_gate_block=guard_raw.get("retry_on_gate_block"),
    )

    return HarnessConfig(
        mode=mode,
        models=models,
        roles=roles,
        warmup=warmup,
        guardrails=guardrails,
    )
