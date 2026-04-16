"""CCAGENT_HOME — single env var controls all runtime data paths.

Resolution order for the root directory:
  1. $CCAGENT_HOME env var (explicit)
  2. ~/.ccagent (default)

All derived path helpers call ``get_ccagent_home()`` lazily, so the directory
is only created when actually needed (not at import time).
"""
from __future__ import annotations

import os
from pathlib import Path


def get_ccagent_home() -> Path:
    """Return the root data directory for this CCA instance.

    Creates the directory (and any parents) on first call if it does not exist.
    """
    raw = os.environ.get("CCAGENT_HOME", "~/.ccagent")
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


# Canonical derived paths — all callers use these, never hardcode.
def sessions_db_path() -> Path:
    """Path to the SQLite sessions database (added in H2)."""
    return get_ccagent_home() / "sessions.db"


def artifacts_db_path() -> Path:
    """Path to the SQLite artifacts database."""
    return get_ccagent_home() / "artifacts.db"


def artifacts_disk_path() -> Path:
    """Directory for large artifact blobs stored on disk."""
    return get_ccagent_home() / "artifacts"


def wiki_root_path() -> Path:
    """Root directory of the wiki (working.md, log.md, findings/, …)."""
    return get_ccagent_home() / "wiki"


def traces_path() -> Path:
    """Directory for trace YAML files (legacy; removed after H2 migration)."""
    return get_ccagent_home() / "traces"


def config_path() -> Path:
    """Directory for user-level config files (hooks.json, etc.)."""
    return get_ccagent_home() / "config"


def cron_path() -> Path:
    """Directory for cron job definitions (added in H4)."""
    return get_ccagent_home() / "cron"
