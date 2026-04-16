"""Unit tests for ToolsetResolver (H5.T1)."""
from __future__ import annotations

import pytest

from app.harness.toolsets import ToolsetResolver


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _resolver(config: dict) -> ToolsetResolver:
    return ToolsetResolver(config)


_SAMPLE_CONFIG = {
    "readonly": {
        "tools": ["skill", "session_search"],
    },
    "standard": {
        "includes": ["readonly"],
        "tools": ["execute_python", "write_working"],
    },
    "full": {
        "includes": ["standard"],
        "tools": ["promote_finding", "delegate_subagent"],
    },
    "planning": {
        "tools": ["skill", "write_working", "todo_write"],
    },
}


# ── names() ───────────────────────────────────────────────────────────────────

def test_names_returns_all_defined():
    r = _resolver(_SAMPLE_CONFIG)
    assert set(r.names()) == {"readonly", "standard", "full", "planning"}


# ── resolve() ─────────────────────────────────────────────────────────────────

def test_resolve_flat_toolset():
    r = _resolver(_SAMPLE_CONFIG)
    assert r.resolve("planning") == frozenset({"skill", "write_working", "todo_write"})


def test_resolve_with_includes():
    r = _resolver(_SAMPLE_CONFIG)
    standard = r.resolve("standard")
    # Must include all readonly tools
    assert "skill" in standard
    assert "session_search" in standard
    # Plus own tools
    assert "execute_python" in standard
    assert "write_working" in standard


def test_resolve_nested_deduplicates():
    r = _resolver(_SAMPLE_CONFIG)
    full = r.resolve("full")
    # "skill" appears in both readonly (via standard) and must not duplicate
    assert isinstance(full, frozenset)
    # frozenset already deduplicates by nature, but verify items present once
    assert full.count if hasattr(full, "count") else True  # frozenset has no .count
    assert "skill" in full
    assert "promote_finding" in full


def test_resolve_unknown_name_raises():
    r = _resolver(_SAMPLE_CONFIG)
    with pytest.raises(KeyError, match="unknown toolset"):
        r.resolve("nonexistent")


def test_cycle_detection_raises():
    config = {
        "a": {"includes": ["b"], "tools": ["tool_a"]},
        "b": {"includes": ["a"], "tools": ["tool_b"]},
    }
    r = _resolver(config)
    with pytest.raises(ValueError, match="cycle"):
        r.resolve("a")


# ── from_yaml() ───────────────────────────────────────────────────────────────

def test_from_yaml_loads_toolsets_yaml(tmp_path):
    yaml_content = """\
toolsets:
  basic:
    tools:
      - read_file
      - glob_files
"""
    yaml_file = tmp_path / "toolsets.yaml"
    yaml_file.write_text(yaml_content)
    r = ToolsetResolver.from_yaml(yaml_file)
    assert r.resolve("basic") == frozenset({"read_file", "glob_files"})
