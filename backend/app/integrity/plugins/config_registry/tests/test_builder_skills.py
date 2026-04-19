"""Tests for SkillsBuilder."""
from __future__ import annotations

from pathlib import Path

from app.integrity.plugins.config_registry.builders.skills import (
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
    assert alpha.registry_key == "alpha"
    assert len(alpha.sha_skill_md) == 40
    assert len(alpha.sha_skill_yaml or "") == 40


def test_registry_key_from_frontmatter_name(tiny_repo: Path) -> None:
    """registry_key tracks the ``name:`` field in SKILL.md frontmatter —
    not the dotted filesystem id. ``beta.sub_skill`` (id) has frontmatter
    ``name: sub_skill`` (registry_key), matching SkillRegistry._index.
    """
    builder = SkillsBuilder(skills_root=tiny_repo / "backend/app/skills")
    entries, _ = builder.build()
    by_id = {e.id: e for e in entries}
    assert by_id["alpha"].registry_key == "alpha"
    assert by_id["beta"].registry_key == "beta"
    assert by_id["beta.sub_skill"].registry_key == "sub_skill"


def test_registry_key_none_when_frontmatter_missing_name(tmp_path: Path) -> None:
    """A SKILL.md without a ``name:`` field would be skipped by SkillRegistry —
    builder records the entry with registry_key=None so the parity test can
    safely exclude it.
    """
    skills = tmp_path / "skills"
    (skills / "no_name").mkdir(parents=True)
    (skills / "no_name" / "SKILL.md").write_text(
        "---\nversion: 1.0.0\ndescription: No name field.\n---\n# Body\n"
    )
    builder = SkillsBuilder(skills_root=skills, repo_root=tmp_path)
    entries, failures = builder.build()
    assert failures == []
    assert len(entries) == 1
    assert entries[0].registry_key is None


def test_to_dict_emits_registry_key(tiny_repo: Path) -> None:
    builder = SkillsBuilder(skills_root=tiny_repo / "backend/app/skills")
    entries, _ = builder.build()
    payload = entries[0].to_dict()
    assert "registry_key" in payload
    assert payload["registry_key"] == "alpha"


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
