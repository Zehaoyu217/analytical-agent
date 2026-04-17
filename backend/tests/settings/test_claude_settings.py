"""Tests for .claude/settings.json hook wiring (Second Brain bridge)."""
from __future__ import annotations

import json
from pathlib import Path

# Repo layout: backend/tests/settings/ → repo root is parents[3]
ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"


def test_settings_file_exists():
    assert SETTINGS.exists(), f"{SETTINGS} missing"


def test_user_prompt_submit_has_sb_inject_hook():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    ups = data.get("hooks", {}).get("UserPromptSubmit", [])
    cmds = []
    for entry in ups:
        # Two common shapes: {command: "..."} OR {hooks: [{command: "..."}, ...]}
        if "command" in entry:
            cmds.append(entry.get("command", ""))
        for sub in entry.get("hooks", []):
            cmds.append(sub.get("command", ""))
    assert any(
        "sb inject" in c and "--prompt-stdin" in c for c in cmds
    ), f"no sb inject hook in UserPromptSubmit: {cmds}"


def test_post_tool_use_has_sb_reindex_matcher():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    ptu = data.get("hooks", {}).get("PostToolUse", [])
    hits = [
        h
        for h in ptu
        if "sb_ingest" in (h.get("matcher") or "")
        or "sb_promote_claim" in (h.get("matcher") or "")
    ]
    assert hits, f"no sb reindex hook in PostToolUse: {ptu}"
    cmds: list[str] = []
    for h in hits:
        if "command" in h:
            cmds.append(h.get("command", ""))
        for sub in h.get("hooks", []):
            cmds.append(sub.get("command", ""))
    assert any("sb reindex" in c for c in cmds), f"no sb reindex command: {cmds}"
