from __future__ import annotations

from pathlib import Path

import pytest

from app.skills.registry import SkillRegistry


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Minimal demo skill.\n"
        "level: 2\n"
        "version: '0.3'\n"
        "---\n"
        "# Demo\n\nBody text.\n"
    )
    (skill_dir / "skill.yaml").write_text(
        "dependencies:\n"
        "  requires: [theme_config]\n"
        "  used_by: []\n"
        "  packages: [pandas]\n"
        "errors:\n"
        "  BAD_INPUT:\n"
        "    message: bad input {field}\n"
        "    guidance: provide {field}\n"
        "    recovery: supply the value and rerun\n"
    )
    return tmp_path


def test_registry_reads_metadata_from_skill_md_frontmatter(skills_root: Path) -> None:
    registry = SkillRegistry(skills_root)
    registry.discover()

    loaded = registry.get_skill("demo")
    assert loaded is not None
    assert loaded.metadata.name == "demo"
    assert loaded.metadata.description == "Minimal demo skill."
    assert loaded.metadata.level == 2
    assert loaded.metadata.version == "0.3"
    assert loaded.metadata.dependencies_requires == ["theme_config"]
    assert loaded.metadata.dependencies_packages == ["pandas"]
    assert "BAD_INPUT" in loaded.metadata.error_templates


def test_registry_body_excludes_frontmatter(skills_root: Path) -> None:
    registry = SkillRegistry(skills_root)
    registry.discover()

    instructions = registry.get_instructions("demo")
    assert instructions is not None
    assert instructions.startswith("# Demo")
    assert "---" not in instructions.splitlines()[0]


def test_registry_ignores_dir_without_skill_md(tmp_path: Path) -> None:
    (tmp_path / "nope").mkdir()
    registry = SkillRegistry(tmp_path)
    registry.discover()
    assert registry.list_skills() == []
