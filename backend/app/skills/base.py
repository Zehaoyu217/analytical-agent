from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SkillError(Exception):
    """Actionable error with template-based formatting.

    Every error code maps to a template in skill.yaml with message,
    guidance, and recovery fields. Context values fill the placeholders.
    """

    def __init__(
        self,
        code: str,
        context: dict[str, Any],
        templates: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.code = code
        self.context = context
        self.templates = templates or {}
        super().__init__(self.format())

    def format(self) -> str:
        template = self.templates.get(self.code)
        if template is None:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.code}: {context_str}"
        parts: list[str] = []
        for key in ("message", "guidance", "recovery"):
            raw = template.get(key, "")
            if raw:
                try:
                    parts.append(raw.format(**self.context))
                except KeyError:
                    parts.append(raw)
        return "\n".join(parts)


@dataclass(frozen=True)
class SkillResult:
    """Return type for all skill function executions."""

    data: Any = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SkillMetadata:
    """Parsed metadata from SKILL.md frontmatter and skill.yaml.

    ``level`` has been removed — depth is computed from directory position
    by SkillRegistry and stored on SkillNode, never authored in frontmatter.
    """

    name: str
    version: str
    description: str
    dependencies_requires: list[str] = field(default_factory=list)
    dependencies_used_by: list[str] = field(default_factory=list)
    dependencies_packages: list[str] = field(default_factory=list)
    error_templates: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class SkillNode:
    """A node in the skill hierarchy tree.

    Built by SkillRegistry.discover(). Not frozen — children list is
    populated incrementally during recursive discovery.

    depth: 1 = Level 1 (root), 2 = Level 2 (sub-skill), etc.
    parent: None for Level 1 skills.
    children: empty list for leaf skills.
    package_path: path to pkg/ directory, or None if the skill has no Python package.
    """

    metadata: SkillMetadata
    instructions: str
    package_path: Path | None
    depth: int
    parent: SkillNode | None
    children: list[SkillNode] = field(default_factory=list)
