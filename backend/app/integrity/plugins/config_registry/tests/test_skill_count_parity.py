"""Acceptance-gate proof: SkillsBuilder == SkillRegistry._index parity.

Runs against the *real* backend/app/skills/ directory (not a fixture).
This is the structural guarantee for gate δ #2.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.integrity.plugins.config_registry.builders.skills import (
    SkillsBuilder,
)

REPO_ROOT = Path(__file__).resolve().parents[6]
SKILLS_ROOT = REPO_ROOT / "backend" / "app" / "skills"


@pytest.mark.skipif(not SKILLS_ROOT.exists(), reason="real skills tree not present")
def test_builder_count_matches_registry() -> None:
    from app.skills.registry import SkillRegistry

    registry = SkillRegistry(SKILLS_ROOT)
    registry.discover()
    builder = SkillsBuilder(skills_root=SKILLS_ROOT, repo_root=REPO_ROOT)
    entries, failures = builder.build()
    assert failures == [], f"builder failures: {failures}"
    assert len(entries) == len(registry._index), (
        f"manifest skills: {len(entries)} != registry._index: "
        f"{len(registry._index)}\n"
        f"missing in builder: {set(registry._index) - {e.id for e in entries}}\n"
        f"extra in builder:   {set(e.id for e in entries) - set(registry._index)}"
    )


@pytest.mark.skipif(not SKILLS_ROOT.exists(), reason="real skills tree not present")
def test_builder_ids_match_registry_keys() -> None:
    """SkillEntry.registry_key (from SKILL.md frontmatter ``name``) is the
    same value SkillRegistry uses to populate ``_index``. The set of
    non-null registry_keys must equal the registry's key set exactly —
    no leaf-name workaround, no normalization, just identity.
    """
    from app.skills.registry import SkillRegistry

    registry = SkillRegistry(SKILLS_ROOT)
    registry.discover()
    builder = SkillsBuilder(skills_root=SKILLS_ROOT, repo_root=REPO_ROOT)
    entries, _ = builder.build()
    builder_keys = {e.registry_key for e in entries if e.registry_key is not None}
    assert builder_keys == set(registry._index), (
        f"registry_key parity mismatch:\n"
        f"missing in builder: {set(registry._index) - builder_keys}\n"
        f"extra in builder:   {builder_keys - set(registry._index)}"
    )
