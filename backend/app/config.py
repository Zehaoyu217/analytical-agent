from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parents[1]  # backend/
_REPO_ROOT = _THIS_FILE.parents[2]     # repo root
_REPO_CONFIG_DIR = _BACKEND_ROOT / "config"
_REPO_BRANDING_YAML = _REPO_CONFIG_DIR / "branding.yaml"


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables.

    Runtime data paths are controlled by ``CCAGENT_HOME`` (default ``~/.ccagent``).
    See ``app.core.home`` for the full path-helper API. The fields below that
    reference paths (sandbox_state_root, duckdb_path, wiki_root) are convenience
    overrides; in production prefer setting ``CCAGENT_HOME`` and relying on the
    derived defaults in ``wiring.py``.
    """

    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Model
    default_model: str = "openai/gpt-oss-120b:free"
    openrouter_api_key: str = ""

    # llm_wiki sidecar integration. When the user installs llm_wiki
    # (https://github.com/nashsu/llm_wiki) and points its project at this
    # directory, our Knowledge-page file tree and retrieval layer both see
    # the entities/, concepts/, sources/ markdown it emits. The desktop app
    # owns the extraction (two-stage analyze→generate prompts); we just
    # read the vault. Blank = feature disabled.
    llm_wiki_dir: str = ""

    # Sandbox
    sandbox_timeout_seconds: int = 30
    sandbox_max_memory_mb: int = 2048
    sandbox_state_root: str = "./data/sandbox_sessions"

    # DuckDB
    duckdb_path: str = "./data/duckdb/eval.db"

    # Wiki
    wiki_root: str = "../knowledge/wiki"
    wiki_auto_write: bool = True

    # Context window
    context_max_tokens: int = 32768
    context_compaction_threshold: float = 0.80

    model_config = {"env_prefix": "", "env_file": "../.env", "extra": "ignore"}


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()


# ── Branding ──────────────────────────────────────────────────────────────────


class BrandingConfig(BaseModel):
    """UI and agent branding configuration loaded from a YAML file."""

    agent_name: str = "Analytical Agent"
    agent_persona: str = ""
    ui_title: str = "Analytical Agent"
    ui_accent_color: str = "#e0733a"
    ui_spinner_phrases: list[str] = [
        "Thinking...",
        "Analysing...",
        "Running tools...",
        "Crunching numbers...",
    ]


def _parse_branding_yaml(path: Path) -> dict[str, Any]:
    """Read *path* and return its parsed YAML as a dict (empty dict on error)."""
    try:
        import yaml  # noqa: PLC0415
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:  # noqa: BLE001
        logger.warning("Could not parse branding YAML at %s", path)
        return {}


def load_branding() -> BrandingConfig:
    """Load BrandingConfig with 3-tier resolution.

    1. ``$CCAGENT_HOME/config/branding.yaml`` — operator override
    2. Repo-default ``backend/config/branding.yaml``
    3. Hardcoded defaults (BrandingConfig field defaults)
    """
    # Tier 1: CCAGENT_HOME override
    home = os.environ.get("CCAGENT_HOME")
    if home:
        home_path = Path(home) / "config" / "branding.yaml"
        if home_path.exists():
            raw = _parse_branding_yaml(home_path)
            if raw:
                return _build_from_raw(raw)

    # Tier 2: repo default
    if _REPO_BRANDING_YAML.exists():
        raw = _parse_branding_yaml(_REPO_BRANDING_YAML)
        if raw:
            return _build_from_raw(raw)

    # Tier 3: hardcoded defaults
    return BrandingConfig()


def _build_from_raw(raw: dict[str, Any]) -> BrandingConfig:
    agent = raw.get("agent", {}) or {}
    ui = raw.get("ui", {}) or {}
    kwargs: dict[str, Any] = {}
    if "name" in agent:
        kwargs["agent_name"] = agent["name"]
    if "persona" in agent:
        kwargs["agent_persona"] = agent["persona"]
    if "title" in ui:
        kwargs["ui_title"] = ui["title"]
    if "accent_color" in ui:
        kwargs["ui_accent_color"] = ui["accent_color"]
    if "spinner_phrases" in ui:
        kwargs["ui_spinner_phrases"] = ui["spinner_phrases"]
    return BrandingConfig(**kwargs)


# ── Second Brain integration ────────────────────────────────────────────────
import os as _os  # noqa: E402 — grouped with helpers below intentionally
from pathlib import Path as _Path  # noqa: E402


def _resolve_sb_home() -> _Path:
    raw = _os.environ.get("SECOND_BRAIN_HOME")
    return _Path(raw).expanduser() if raw else _Path.home() / "second-brain"


SECOND_BRAIN_HOME: _Path = _resolve_sb_home()
SECOND_BRAIN_ENABLED: bool = (
    SECOND_BRAIN_HOME.exists() and (SECOND_BRAIN_HOME / ".sb").exists()
)
