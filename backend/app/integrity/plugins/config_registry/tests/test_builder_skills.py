"""Tests for SkillsBuilder."""
from __future__ import annotations

from pathlib import Path

from backend.app.integrity.plugins.config_registry.builders.skills import (
    SkillEntry,
    SkillsBuilder,
)


def test_builds_three_entries(tiny_repo: Path) -> None:
    builder = SkillsBuilder(skills_root=tiny_repo / "backend/app/skills")
    entries, failures = builder.build()
    ids = [e.id for e in entries]
    assert ids == ["alpha", "beta", "beta.sub_skill"]
    assert failures == []


def test_skill_entry_fields(tiny_repo: Path) -> None:
    builder = SkillsBuilder(skills_root=tiny_repo / "backend/app/skills")
    entries, _ = builder.build()
    by_id = {e.id: e for e in entries}

    alpha = by_id["alpha"]
    assert alpha.path == "backend/app/skills/alpha/SKILL.md"
    assert alpha.yaml_path == "backend/app/skills/alpha/skill.yaml"
    assert alpha.version == "1.0.0"
    assert alpha.description == "Alpha skill."
    assert alpha.parent is None
    assert alpha.children == []
    assert len(alpha.sha_skill_md) == 40
    assert len(alpha.sha_skill_yaml or "") == 40


def test_parent_and_children_relationships(tiny_repo: Path) -> None:
    builder = SkillsBuilder(skills_root=tiny_repo / "backend/app/skills")
    entries, _ = builder.build()
    by_id = {e.id: e for e in entries}

    assert by_id["beta"].parent is None
    assert by_id["beta"].children == ["beta.sub_skill"]
    assert by_id["beta.sub_skill"].parent == "beta"
    assert by_id["beta.sub_skill"].children == []


def test_skill_without_skill_yaml(tiny_repo: Path, tmp_path: Path) -> None:
    """A skill without skill.yaml has yaml_path/sha_skill_yaml as None."""
    target = tiny_repo / "backend/app/skills/alpha/skill.yaml"
    target.unlink()
    builder = SkillsBuilder(skills_root=tiny_repo / "backend/app/skills")
    entries, failures = builder.build()
    by_id = {e.id: e for e in entries}
    assert by_id["alpha"].yaml_path is None
    assert by_id["alpha"].sha_skill_yaml is None
    assert failures == []


def test_empty_skills_root(tmp_path: Path) -> None:
    empty = tmp_path / "skills"
    empty.mkdir()
    builder = SkillsBuilder(skills_root=empty)
    entries, failures = builder.build()
    assert entries == []
    assert failures == []
