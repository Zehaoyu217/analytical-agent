from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from second_brain.gardener.audit import append, audit_path, mark_accepted, tail


@dataclass
class FakeCfg:
    sb_dir: Path


def _make_cfg(tmp_path: Path) -> FakeCfg:
    return FakeCfg(sb_dir=tmp_path)


def test_audit_path_shape(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    p = audit_path(cfg)
    assert p == tmp_path / ".state" / "gardener.log.jsonl"


def test_append_creates_file_and_writes_line(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    append(cfg, {"pass": "extract", "line": "gx-1", "accepted": None})
    path = audit_path(cfg)
    assert path.exists()
    raw = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 1
    row = json.loads(raw[0])
    assert row["pass"] == "extract"
    assert row["line"] == "gx-1"


def test_tail_returns_last_n_and_filter(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    append(cfg, {"pass": "extract", "line": "a"})
    append(cfg, {"pass": "dedupe", "line": "b"})
    append(cfg, {"pass": "extract", "line": "c"})

    assert [r["line"] for r in tail(cfg, n=2)] == ["b", "c"]
    assert [r["line"] for r in tail(cfg, filter_pass="extract")] == ["a", "c"]


def test_tail_missing_file_returns_empty(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    assert tail(cfg) == []


def test_mark_accepted_flips_matching_rows(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    append(cfg, {"pass": "extract", "line": "gx-1", "accepted": None})
    append(cfg, {"pass": "extract", "line": "gx-2", "accepted": None})
    append(cfg, {"pass": "extract", "line": "gx-1", "accepted": None})  # duplicate line id

    updated = mark_accepted(cfg, match_line="gx-1", accepted=True)
    assert updated == 2

    rows = tail(cfg)
    by_line = [(r["line"], r["accepted"]) for r in rows]
    assert ("gx-1", True) in by_line
    assert ("gx-2", None) in by_line


def test_mark_accepted_skips_already_decided(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    append(cfg, {"pass": "extract", "line": "gx-1", "accepted": True})
    updated = mark_accepted(cfg, match_line="gx-1", accepted=False)
    # Already decided, not re-flipped
    assert updated == 0
    assert tail(cfg)[0]["accepted"] is True


@pytest.mark.parametrize("rows_in", [0, 5, 50])
def test_tail_respects_n(tmp_path: Path, rows_in: int) -> None:
    cfg = _make_cfg(tmp_path)
    for i in range(rows_in):
        append(cfg, {"pass": "extract", "line": f"gx-{i}"})
    assert len(tail(cfg, n=10)) == min(10, rows_in)
