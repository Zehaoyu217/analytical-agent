"""Tests for the circuit breaker — auto-disable classes after N human-edited PRs."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from app.integrity.plugins.autofix.circuit_breaker import (
    AutofixState,
    ClassState,
    PRRecord,
    disabled_classes,
    load_state,
    record_pr_outcome,
    save_state,
)


def test_load_missing_returns_empty_state(tmp_path: Path) -> None:
    state = load_state(tmp_path / "absent.yaml")
    assert state.window_days == 30
    assert state.classes == {}


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    state = AutofixState(
        generated_at="2026-04-17T03:00:00Z",
        generator_version="1.0.0",
        window_days=30,
        classes={
            "claude_md_link": ClassState(
                merged_clean=2,
                human_edited=0,
                pr_history=(
                    PRRecord(pr=142, merged_at="2026-03-25", action="clean"),
                ),
            ),
        },
    )
    save_state(p, state)
    loaded = load_state(p)
    assert loaded.classes["claude_md_link"].merged_clean == 2
    assert loaded.classes["claude_md_link"].pr_history[0].pr == 142


def test_disabled_classes_returns_classes_above_threshold() -> None:
    state = AutofixState(
        generated_at="2026-04-17T03:00:00Z",
        generator_version="1.0.0",
        window_days=30,
        classes={
            "claude_md_link": ClassState(merged_clean=3, human_edited=0, pr_history=()),
            "doc_link_renamed": ClassState(merged_clean=0, human_edited=3, pr_history=()),
            "manifest_regen": ClassState(merged_clean=0, human_edited=2, pr_history=()),
        },
    )
    disabled = disabled_classes(state, max_human_edits=2)
    assert disabled == {"doc_link_renamed"}


def test_record_pr_outcome_accumulates(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    state = load_state(p)
    state = record_pr_outcome(
        state,
        fix_class="claude_md_link",
        pr=10,
        merged_at="2026-04-01",
        action="clean",
        today=date(2026, 4, 17),
    )
    state = record_pr_outcome(
        state,
        fix_class="claude_md_link",
        pr=11,
        merged_at="2026-04-02",
        action="human_edited",
        today=date(2026, 4, 17),
    )
    assert state.classes["claude_md_link"].merged_clean == 1
    assert state.classes["claude_md_link"].human_edited == 1
    assert len(state.classes["claude_md_link"].pr_history) == 2


def test_window_pruning_drops_old_history() -> None:
    """PR history older than window_days is pruned at record time."""
    state = AutofixState(
        generated_at="",
        generator_version="1.0.0",
        window_days=30,
        classes={
            "claude_md_link": ClassState(
                merged_clean=5,
                human_edited=0,
                pr_history=(
                    PRRecord(pr=1, merged_at="2025-01-01", action="clean"),
                ),
            ),
        },
    )
    state = record_pr_outcome(
        state,
        fix_class="claude_md_link",
        pr=99,
        merged_at="2026-04-17",
        action="clean",
        today=date(2026, 4, 17),
    )
    assert len(state.classes["claude_md_link"].pr_history) == 1
    assert state.classes["claude_md_link"].pr_history[0].pr == 99
    assert state.classes["claude_md_link"].merged_clean == 1
    assert state.classes["claude_md_link"].human_edited == 0


def test_load_state_rejects_unknown_action(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump({
        "window_days": 30,
        "classes": {
            "claude_md_link": {
                "merged_clean": 1,
                "human_edited": 0,
                "pr_history": [{"pr": 1, "merged_at": "2026-04-01", "action": "weird"}],
            }
        }
    }))
    with pytest.raises(ValueError, match="action"):
        load_state(p)
