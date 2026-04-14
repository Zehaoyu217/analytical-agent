"""GET /api/skills/manifest — expose the skill catalog to the frontend."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

from app.skills.registry import SkillRegistry

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _skills_root() -> Path:
    return Path(os.environ.get("SKILLS_ROOT", "app/skills"))


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
            "level": s.metadata.level,
            "requires": s.metadata.dependencies_requires,
            "used_by": s.metadata.dependencies_used_by,
        }
        for name in registry.list_skills()
        if (s := registry.get_skill(name)) is not None
    ]
    return {"skills": skills}
