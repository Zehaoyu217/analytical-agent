"""Tests for manifest read/write/diff."""
from __future__ import annotations

from pathlib import Path

from app.integrity.plugins.config_registry.manifest import (
    diff_manifests,
    empty_manifest,
    read_manifest,
    write_manifest,
)


def test_empty_manifest_shape() -> None:
    m = empty_manifest()
    assert m["manifest_version"] == 1
    assert m["configs"] == []
    assert m["functions"] == []
    assert m["routes"] == []
    assert m["scripts"] == []
    assert m["skills"] == []


def test_read_missing_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "missing.yaml"
    m = read_manifest(p)
    assert m == empty_manifest()


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "manifest.yaml"
    m = empty_manifest()
    m["generated_at"] = "2026-04-17"
    m["scripts"] = [{"id": "scripts/a.sh", "path": "scripts/a.sh",
                     "interpreter": "bash", "sha": "abc123"}]
    write_manifest(p, m)
    m2 = read_manifest(p)
    assert m2["scripts"] == m["scripts"]
    assert m2["manifest_version"] == 1


def test_write_is_deterministic(tmp_path: Path) -> None:
    p1 = tmp_path / "m1.yaml"
    p2 = tmp_path / "m2.yaml"
    m = empty_manifest()
    m["generated_at"] = "2026-04-17"
    m["configs"] = [
        {"id": "Makefile", "type": "makefile", "path": "Makefile", "sha": "z"},
        {"id": "Dockerfile", "type": "dockerfile", "path": "Dockerfile", "sha": "a"},
    ]
    write_manifest(p1, m)
    write_manifest(p2, m)
    assert p1.read_bytes() == p2.read_bytes()


def test_write_sorts_entries_by_id(tmp_path: Path) -> None:
    p = tmp_path / "m.yaml"
    m = empty_manifest()
    m["generated_at"] = "2026-04-17"
    m["configs"] = [
        {"id": "z.yaml", "type": "x", "path": "z.yaml", "sha": "1"},
        {"id": "a.yaml", "type": "x", "path": "a.yaml", "sha": "2"},
    ]
    write_manifest(p, m)
    body = p.read_text()
    assert body.index("a.yaml") < body.index("z.yaml")


def test_diff_added(tmp_path: Path) -> None:
    prior = empty_manifest()
    current = empty_manifest()
    current["scripts"] = [{"id": "scripts/new.sh", "path": "scripts/new.sh",
                           "interpreter": "bash", "sha": "x"}]
    delta = diff_manifests(current, prior)
    assert delta.added["scripts"] == [current["scripts"][0]]
    assert delta.removed["scripts"] == []
    assert delta.changed["scripts"] == []


def test_diff_removed(tmp_path: Path) -> None:
    prior = empty_manifest()
    prior["scripts"] = [{"id": "scripts/old.sh", "path": "scripts/old.sh",
                         "interpreter": "bash", "sha": "x"}]
    current = empty_manifest()
    delta = diff_manifests(current, prior)
    assert delta.removed["scripts"] == [prior["scripts"][0]]
    assert delta.added["scripts"] == []


def test_diff_changed_via_sha(tmp_path: Path) -> None:
    prior = empty_manifest()
    prior["configs"] = [{"id": "Makefile", "type": "makefile",
                         "path": "Makefile", "sha": "old"}]
    current = empty_manifest()
    current["configs"] = [{"id": "Makefile", "type": "makefile",
                           "path": "Makefile", "sha": "new"}]
    delta = diff_manifests(current, prior)
    assert delta.changed["configs"] == [
        {"id": "Makefile", "prior": prior["configs"][0],
         "current": current["configs"][0]}
    ]
    assert delta.added["configs"] == []
    assert delta.removed["configs"] == []


def test_diff_ignores_generated_at(tmp_path: Path) -> None:
    prior = empty_manifest()
    prior["generated_at"] = "2026-04-15"
    current = empty_manifest()
    current["generated_at"] = "2026-04-17"
    delta = diff_manifests(current, prior)
    for key in ("configs", "functions", "routes", "scripts", "skills"):
        assert delta.added[key] == []
        assert delta.removed[key] == []
        assert delta.changed[key] == []


def test_idempotent_write_read_write(tmp_path: Path) -> None:
    p1 = tmp_path / "m1.yaml"
    p2 = tmp_path / "m2.yaml"
    m = empty_manifest()
    m["generated_at"] = "2026-04-17"
    m["configs"] = [{"id": "Makefile", "type": "makefile",
                     "path": "Makefile", "sha": "x"}]
    write_manifest(p1, m)
    re_read = read_manifest(p1)
    write_manifest(p2, re_read)
    assert p1.read_bytes() == p2.read_bytes()
