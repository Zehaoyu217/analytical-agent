"""REST endpoints for user and system settings.

Two layers live here:

**User settings** (``data/settings.json``)
    A small, frontend-driven blob: theme preference, default model,
    send-on-enter. Accessed via ``GET``/``PUT /api/settings``. Unchanged.

**System config aggregator** (``GET /api/settings/config``)
    A read-first snapshot of every tunable that lives on the server side —
    app settings (host/port/CORS/...), ``config/models.yaml``, Second Brain
    ``habits.yaml``, known env keys (secrets masked), and the list of
    writable prompt files. Drives the tabbed Settings page. Writes are
    split into per-group ``PATCH`` endpoints so the UI can update one
    section at a time without clobbering the others.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.storage.json_store import JsonStoreError, read_json, write_json_atomic

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── user settings (unchanged) ───────────────────────────────────────────────


class UserSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    theme: Literal["light", "dark", "system"] = "system"
    # OpenRouter-routed default. MLX ids start with "mlx/" and the
    # chat_api dispatcher routes correctly either way.
    model: str = "openai/gpt-oss-120b:free"
    send_on_enter: bool = True


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data"))


def _settings_path() -> Path:
    return _data_dir() / "settings.json"


@router.get("")
def get_settings() -> UserSettings:
    path = _settings_path()
    try:
        return read_json(path, UserSettings, default=UserSettings())
    except JsonStoreError as exc:
        raise HTTPException(status_code=500, detail="failed to load settings") from exc


@router.put("")
def put_settings(payload: UserSettings) -> UserSettings:
    write_json_atomic(_settings_path(), payload)
    return payload


# ── system config aggregator ────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent
_MODELS_YAML_PATH = _REPO_ROOT / "config" / "models.yaml"
_PROMPTS_DIR = _REPO_ROOT / "prompts"

# Env keys the UI cares about. Values for any key whose name matches
# _SECRET_KEY_RE are masked in the response (only the last 4 chars kept).
# Edit here when a new tunable lands — we intentionally don't dump the whole
# environment (too noisy, and leaks unrelated system vars).
_ENV_KEYS: tuple[str, ...] = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_FALLBACK_MODELS",
    "RESEARCH_LLM_MODEL",
    "MCP_SAMPLER_MODEL",
    "CRON_WORKER_MODEL",
    "BATCH_WORKER_MODEL",
    "SECOND_BRAIN_HOME",
    "SECOND_BRAIN_ENABLED",
    "SB_DIGEST_HOOK_ENABLED",
    "CCAGENT_HOME",
    "WIKI_ROOT",
    "LLM_WIKI_DIR",
    "DATA_DIR",
    "CORS_ORIGINS",
    "CCAGENT_PROMPT_PATH",
)
_SECRET_KEY_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)$", re.IGNORECASE)


def _mask(value: str) -> str:
    if len(value) <= 6:
        return "•" * len(value)
    return f"{'•' * 8}{value[-4:]}"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=500, detail=f"malformed YAML at {path}: {exc}",
        ) from exc


def _write_yaml_atomic(path: Path, data: dict[str, Any]) -> None:
    """Serialize *data* to *path* atomically (tmp + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # ``sort_keys=False`` preserves operator-facing field order; default
    # flow style keeps the file greppable and hand-editable.
    tmp.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    """Recursive dict merge — src wins on leaves, nested dicts are merged."""
    out = dict(dst)
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass(frozen=True)
class _PromptFile:
    name: str
    path: str
    size: int
    modified: float


def _list_prompts() -> list[_PromptFile]:
    if not _PROMPTS_DIR.is_dir():
        return []
    out: list[_PromptFile] = []
    for p in sorted(_PROMPTS_DIR.glob("*.md")):
        stat = p.stat()
        out.append(
            _PromptFile(
                name=p.name,
                path=str(p.relative_to(_REPO_ROOT)),
                size=stat.st_size,
                modified=stat.st_mtime,
            )
        )
    return out


def _habits_path() -> Path | None:
    """Resolve the Second Brain habits.yaml. None when SB is disabled."""
    try:
        from app import config as _c  # noqa: PLC0415
    except ImportError:
        return None
    if not getattr(_c, "SECOND_BRAIN_ENABLED", False):
        return None
    return _c.SECOND_BRAIN_HOME / ".sb" / "habits.yaml"


@router.get("/config")
def get_full_config() -> dict[str, Any]:
    """Return every server-side tunable grouped by tab.

    Intentionally read-first: editing goes through the per-group PATCH
    endpoints below (``/config/models``, ``/config/habits``) so a bad write
    on one tab doesn't corrupt another.
    """
    from app.config import get_config, load_branding  # noqa: PLC0415

    app_cfg = get_config()
    branding = load_branding()

    env_entries: list[dict[str, Any]] = []
    for key in _ENV_KEYS:
        raw = os.environ.get(key)
        set_ = raw is not None
        display = (
            _mask(raw) if set_ and _SECRET_KEY_RE.search(key) else raw or ""
        )
        env_entries.append(
            {
                "key": key,
                "value": display,
                "set": set_,
                "secret": bool(_SECRET_KEY_RE.search(key)),
            }
        )

    habits_path = _habits_path()
    habits = _read_yaml(habits_path) if habits_path else {}

    return {
        "app": {
            "environment": app_cfg.environment,
            "host": app_cfg.host,
            "port": app_cfg.port,
            "debug": app_cfg.debug,
            "default_model": app_cfg.default_model,
            "openrouter_api_key_set": bool(app_cfg.openrouter_api_key),
            "sandbox_timeout_seconds": app_cfg.sandbox_timeout_seconds,
            "sandbox_max_memory_mb": app_cfg.sandbox_max_memory_mb,
            "context_max_tokens": app_cfg.context_max_tokens,
            "context_compaction_threshold": app_cfg.context_compaction_threshold,
            # Restart-required fields — the UI greys these.
            "_readonly": [
                "environment", "host", "port",
                "context_max_tokens", "context_compaction_threshold",
            ],
        },
        "branding": {
            "agent_name": branding.agent_name,
            "agent_persona": branding.agent_persona,
            "ui_title": branding.ui_title,
            "ui_accent_color": branding.ui_accent_color,
            "_readonly": ["agent_name", "ui_title", "ui_accent_color"],
        },
        "models_yaml": {
            "path": str(_MODELS_YAML_PATH.relative_to(_REPO_ROOT)),
            "exists": _MODELS_YAML_PATH.exists(),
            "editable": _MODELS_YAML_PATH.exists(),
            "content": _read_yaml(_MODELS_YAML_PATH),
        },
        "habits_yaml": {
            "path": str(habits_path.relative_to(Path.home()))
            if habits_path
            else None,
            "exists": bool(habits_path and habits_path.exists()),
            "editable": bool(habits_path and habits_path.exists()),
            "content": habits,
            "enabled": habits_path is not None,
        },
        "env": env_entries,
        "prompts": [
            {
                "name": p.name,
                "path": p.path,
                "size": p.size,
                "modified": p.modified,
            }
            for p in _list_prompts()
        ],
    }


# ── YAML PATCH endpoints ────────────────────────────────────────────────────


class ConfigPatch(BaseModel):
    """Partial deep-merge payload for ``/config/models`` and ``/config/habits``.

    Clients PATCH only the keys they're changing. Nested dicts merge;
    non-dict leaves are replaced outright.
    """

    model_config = ConfigDict(frozen=True, extra="allow")


@router.patch("/config/models")
def patch_models_yaml(payload: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge *payload* into ``config/models.yaml`` and re-validate.

    Re-validation runs the existing ``load_config`` so a bad merge (unknown
    provider, dangling role target, etc.) rejects before the write lands.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")
    current = _read_yaml(_MODELS_YAML_PATH)
    merged = _deep_merge(current, payload)

    # Validate before writing so a broken merge never hits disk.
    try:
        tmp = _MODELS_YAML_PATH.with_suffix(".validate.yaml")
        tmp.write_text(
            yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        from app.harness.config import load_config  # noqa: PLC0415
        load_config(tmp)
        tmp.unlink()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"validation failed: {exc}",
        ) from exc

    _write_yaml_atomic(_MODELS_YAML_PATH, merged)
    return {"ok": True, "content": merged}


@router.patch("/config/habits")
def patch_habits_yaml(payload: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge *payload* into the Second Brain habits.yaml."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")
    habits_path = _habits_path()
    if habits_path is None:
        raise HTTPException(
            status_code=404, detail="Second Brain disabled or home missing",
        )
    current = _read_yaml(habits_path)
    merged = _deep_merge(current, payload)
    _write_yaml_atomic(habits_path, merged)
    return {"ok": True, "content": merged}


@router.get("/prompts/{name}")
def get_prompt(name: str) -> dict[str, Any]:
    """Return the contents of ``prompts/{name}`` — read-only for now."""
    # Guard against traversal.
    safe = (_PROMPTS_DIR / name).resolve()
    try:
        safe.relative_to(_PROMPTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid prompt name") from exc
    if not safe.exists() or not safe.is_file():
        raise HTTPException(status_code=404, detail="prompt not found")
    return {
        "name": name,
        "content": safe.read_text(encoding="utf-8"),
        "size": safe.stat().st_size,
    }
