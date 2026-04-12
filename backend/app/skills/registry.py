from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.skills.base import SkillMetadata


@dataclass
class LoadedSkill:
    """A discovered and loaded skill (evals excluded)."""

    metadata: SkillMetadata
    instructions: str
    package_path: Path
    references_path: Path | None
    evals_path: None = None  # sealed from agent


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a SKILL.md file into (frontmatter_dict, body)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(
            i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        return {}, text
    raw = "".join(lines[1:end])
    body = "".join(lines[end + 1 :]).lstrip("\n")
    parsed = yaml.safe_load(raw) or {}
    return parsed, body


class SkillRegistry:
    """Discovers and loads skills from a directory tree."""

    def __init__(self, skills_root: Path) -> None:
        self._root = skills_root
        self._skills: dict[str, LoadedSkill] = {}

    def discover(self) -> None:
        self._skills.clear()
        if not self._root.exists():
            return

        for skill_dir in sorted(self._root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            fm, body = _split_frontmatter(skill_md.read_text())
            name = fm.get("name")
            if not name:
                continue

            skill_yaml = skill_dir / "skill.yaml"
            deps: dict = {}
            errors: dict = {}
            if skill_yaml.exists():
                raw = yaml.safe_load(skill_yaml.read_text()) or {}
                deps = raw.get("dependencies", {}) or {}
                errors = raw.get("errors", {}) or {}

            metadata = SkillMetadata(
                name=name,
                version=str(fm.get("version", "0.0")),
                description=fm.get("description", ""),
                level=int(fm.get("level", 1)),
                dependencies_requires=deps.get("requires", []),
                dependencies_used_by=deps.get("used_by", []),
                dependencies_packages=deps.get("packages", []),
                error_templates=errors,
            )

            pkg_path = skill_dir / "pkg"
            refs_path = skill_dir / "references"

            self._skills[metadata.name] = LoadedSkill(
                metadata=metadata,
                instructions=body,
                package_path=pkg_path,
                references_path=refs_path if refs_path.exists() else None,
            )

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def get_skill(self, name: str) -> LoadedSkill | None:
        return self._skills.get(name)

    def get_instructions(self, name: str) -> str | None:
        skill = self._skills.get(name)
        return skill.instructions if skill else None

    def get_dependency_graph(self) -> dict[str, list[str]]:
        return {
            name: skill.metadata.dependencies_requires
            for name, skill in self._skills.items()
        }
