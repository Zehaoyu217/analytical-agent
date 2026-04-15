"""GET /api/skills/manifest — expose the skill catalog to the frontend."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.skills.registry import SkillRegistry

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _skills_root() -> Path:
    return Path(os.environ.get("SKILLS_ROOT", "app/skills"))


def _compute_level(name: str, registry: SkillRegistry) -> int:
    """Return the depth of the skill node in the registry tree (1 = root)."""
    node = registry.get_skill(name)
    return node.depth if node is not None else 1


def _read_source_files(skill_dir: Path) -> list[dict[str, str]]:
    """Read all .py and .md files from the skill directory, excluding __pycache__ and .pyc."""
    source_files: list[dict[str, str]] = []

    # Always include SKILL.md first if it exists
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        source_files.append({
            "path": "SKILL.md",
            "content": skill_md.read_text(encoding="utf-8"),
        })

    # Walk all .py and .md files (excluding SKILL.md already added)
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        # Exclude __pycache__ directories and .pyc files
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        # Exclude SKILL.md (already added)
        if path == skill_md:
            continue
        if path.suffix not in {".py", ".md"}:
            continue
        relative = path.relative_to(skill_dir)
        try:
            source_files.append({
                "path": str(relative),
                "content": path.read_text(encoding="utf-8"),
            })
        except (OSError, UnicodeDecodeError):
            source_files.append({
                "path": str(relative),
                "content": "(unreadable)",
            })

    return source_files


@router.get("/manifest")
def get_manifest() -> dict[str, object]:
    """Return all discovered skills grouped by level."""
    registry = SkillRegistry(_skills_root())
    registry.discover()
    skills = [
        {
            "name": s.metadata.name,
            "version": s.metadata.version,
            "description": s.metadata.description,
            "level": s.depth,
            "requires": s.metadata.dependencies_requires,
            "used_by": s.metadata.dependencies_used_by,
        }
        for name in registry.list_skills()
        if (s := registry.get_skill(name)) is not None
    ]
    return {"skills": skills}


@router.get("/{skill_name}/detail")
def get_skill_detail(skill_name: str) -> dict[str, object]:
    """Return detailed information for a single skill."""
    skills_root = _skills_root()
    registry = SkillRegistry(skills_root)
    registry.discover()

    skill = registry.get_skill(skill_name)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    # Locate the skill directory on disk.
    # For nested skills, package_path points to the pkg/ subdirectory — its
    # parent is the skill directory. Fall back to recursive SKILL.md search.
    if skill.package_path is not None and skill.package_path.parent.exists():
        skill_dir = skill.package_path.parent
    else:
        skill_dir = skills_root / skill_name
        if not skill_dir.exists():
            for skill_md_candidate in skills_root.rglob("SKILL.md"):
                if skill_md_candidate.parent.name == skill_name:
                    skill_dir = skill_md_candidate.parent
                    break

    # Build reverse dependency list (skills that require this one)
    all_names = registry.list_skills()
    required_by: list[str] = [
        other_name
        for other_name in all_names
        if other_name != skill_name
        and (other_skill := registry.get_skill(other_name)) is not None
        and skill_name in other_skill.metadata.dependencies_requires
    ]

    # Read full SKILL.md content
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_content = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""

    # Extract description from first paragraph of SKILL.md body (after frontmatter)
    description = skill.metadata.description
    if not description and skill.instructions:
        # Use first non-empty line of body as description
        for line in skill.instructions.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped
                break

    source_files = _read_source_files(skill_dir) if skill_dir.exists() else []

    return {
        "name": skill_name,
        "level": skill.depth,
        "version": skill.metadata.version,
        "description": description,
        "requires": skill.metadata.dependencies_requires,
        "required_by": required_by,
        "skill_md": skill_md_content,
        "source_files": source_files,
    }
