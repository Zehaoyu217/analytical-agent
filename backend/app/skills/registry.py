from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

import yaml

from app.skills.base import SkillMetadata, SkillNode

_log = logging.getLogger(__name__)


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
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        _log.warning(
            "SKILL.md frontmatter YAML parse failed — skill will be skipped. "
            "Check for unquoted brackets in description (e.g. use '\"[Reference] ...\"'). "
            "Error: %s",
            exc,
        )
        return {}, text
    if not isinstance(parsed, dict):
        return {}, body
    return parsed, body


# Directories inside a skill dir that are never child skills.
_SKIP_DIRS = frozenset({"pkg", "tests", "evals", "__pycache__", ".git"})


class SkillRegistry:
    """Discovers and loads skills from a nested directory tree.

    Parent-child relationships are encoded purely by filesystem nesting:
    a directory with a SKILL.md that contains other directories with
    SKILL.md files is a hub skill. Depth is computed from position in
    the tree (Level 1 = root, Level 2 = one nesting, etc.).

    Two structures are maintained simultaneously:
    - _roots: list of Level-1 SkillNodes (for catalog generation)
    - _index: flat dict[name → SkillNode] (for permissive direct access)
    """

    def __init__(self, skills_root: Path) -> None:
        self._root = skills_root
        self._roots: list[SkillNode] = []
        self._index: dict[str, SkillNode] = {}

    def discover(self) -> None:
        """Walk the skills directory recursively and build the tree."""
        self._roots.clear()
        self._index.clear()
        if not self._root.exists():
            return
        for skill_dir in sorted(self._root.iterdir()):
            if skill_dir.is_dir() and skill_dir.name not in _SKIP_DIRS:
                self._discover_recursive(skill_dir, parent=None, depth=1)

    def _discover_recursive(
        self, dir: Path, parent: SkillNode | None, depth: int  # noqa: A002 — internal helper
    ) -> None:
        skill_md = dir / "SKILL.md"
        if not skill_md.exists():
            return

        fm, body = _split_frontmatter(skill_md.read_text())
        name = fm.get("name")
        if not name:
            return

        skill_yaml = dir / "skill.yaml"
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
            dependencies_requires=deps.get("requires", []),
            dependencies_used_by=deps.get("used_by", []),
            dependencies_packages=deps.get("packages", []),
            error_templates=errors,
        )

        pkg_path = dir / "pkg"
        node = SkillNode(
            metadata=metadata,
            instructions=body,
            package_path=pkg_path if pkg_path.exists() else None,
            depth=depth,
            parent=parent,
            skill_path=dir,
        )

        if name in self._index:
            _log.warning(
                "Skill name collision: '%s' at %s shadows earlier entry — check for duplicate name: fields",  # noqa: E501
                name,
                dir,
            )
        self._index[name] = node
        if parent is None:
            self._roots.append(node)
        else:
            parent.children.append(node)

        for subdir in sorted(dir.iterdir()):
            if subdir.is_dir() and subdir.name not in _SKIP_DIRS:
                self._discover_recursive(subdir, parent=node, depth=depth + 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def list_top_level(self) -> list[SkillNode]:
        """Return Level-1 (root) skills only — used to build the system prompt catalog."""
        return list(self._roots)

    def get_skill(self, name: str) -> SkillNode | None:
        """Flat lookup by name — works for any skill at any depth."""
        return self._index.get(name)

    def get_children(self, name: str) -> list[SkillNode]:
        """Return direct children of a skill. Empty list for leaf skills."""
        node = self._index.get(name)
        return list(node.children) if node else []

    def get_breadcrumb(self, name: str) -> list[str]:
        """Return path from root to skill: ['statistical_analysis', 'correlation']."""
        node = self._index.get(name)
        if node is None:
            return []
        parts: list[str] = []
        current: SkillNode | None = node
        while current is not None:
            parts.append(current.metadata.name)
            current = current.parent
        return list(reversed(parts))

    def generate_bootstrap_imports(self) -> list[str]:
        """Auto-generate Python import lines for all importable skills.

        Two layouts are supported:

        1. **pkg/ layout** (charting, reporting, etc.): skill has a ``pkg/``
           subdirectory with ``__init__.py``. Import is
           ``from app.skills.X.pkg import *``.

        2. **Direct layout** (statistical_analysis sub-skills): code lives
           directly in the skill directory with ``__init__.py`` defining
           ``__all__``. Import is ``from app.skills.X import *``.

        Hub skills (those with children but no Python exports of their own)
        are skipped.
        """
        backend_root = self._root.parent.parent  # backend/app/skills -> backend/
        lines: list[str] = []
        for node in self._iter_all():
            name = node.metadata.name

            # --- Layout 1: explicit pkg/ subdirectory ---
            if node.package_path is not None:
                pkg = node.package_path
                # Skip empty pkg/ directories
                if not any(f for f in pkg.iterdir() if not f.name.startswith("_") or f.name == "__init__.py"):  # noqa: E501
                    continue
                try:
                    rel = pkg.relative_to(backend_root)
                except ValueError:
                    continue
                module_path = ".".join(rel.parts)
                lines.append(f"from {module_path} import *  # {name}")
                continue

            # --- Layout 2: skill dir is itself a Python package ---
            if node.skill_path is None:
                continue
            init_py = node.skill_path / "__init__.py"
            if not init_py.exists():
                continue
            init_text = init_py.read_text()
            # Only import skill dirs that explicitly declare __all__ — hub dirs
            # (like statistical_analysis/) have no exports and should be skipped.
            if "__all__" not in init_text:
                continue
            try:
                rel = node.skill_path.relative_to(backend_root)
            except ValueError:
                continue
            module_path = ".".join(rel.parts)
            lines.append(f"from {module_path} import *  # {name}")

        return lines

    def _iter_all(self) -> list[SkillNode]:
        """BFS over all nodes in the tree."""
        result: list[SkillNode] = []
        queue: deque[SkillNode] = deque(self._roots)
        while queue:
            node = queue.popleft()
            result.append(node)
            queue.extend(node.children)
        return result

    # ── Backward-compat shims (used by manifest.py) ───────────────────────────

    def list_skills(self) -> list[str]:
        """Return all skill names at all depths. Used by manifest.py."""
        return list(self._index.keys())

    def get_instructions(self, name: str) -> str | None:
        node = self._index.get(name)
        return node.instructions if node else None

    def get_dependency_graph(self) -> dict[str, list[str]]:
        return {
            name: node.metadata.dependencies_requires
            for name, node in self._index.items()
        }
