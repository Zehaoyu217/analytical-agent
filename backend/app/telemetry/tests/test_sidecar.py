"""Tests for :mod:`app.telemetry.sidecar`."""
from __future__ import annotations

import json
from pathlib import Path

from app.telemetry.sidecar import write_meta


def test_write_meta_writes_sorted_pretty_json(tmp_path: Path) -> None:
    target = tmp_path / "2026-04-18.meta.json"
    record = {
        "timestamp": "2026-04-18T00:00:00Z",
        "actor": "digest.build",
        "duration_ms": 42,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "outcome": "ok",
        "detail": {"entries": 3, "emitted": True},
    }
    write_meta(target, record)

    assert target.exists()
    text = target.read_text()
    # Pretty-printed + sorted → deterministic for diffs.
    parsed = json.loads(text)
    assert parsed == record
    # First key alphabetically is "actor"
    first_non_brace = text.split("\n", 2)[1].strip()
    assert first_non_brace.startswith('"actor"')


def test_write_meta_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "x.json"
    write_meta(target, {"outcome": "ok"})
    assert target.exists()
