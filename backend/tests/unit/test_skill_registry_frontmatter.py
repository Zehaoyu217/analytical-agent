from __future__ import annotations

from pathlib import Path

from app.skills.registry import SkillRegistry


def _write_skill(
    root: Path,
    name: str,
    *,
    description: str = "A skill.",
    version: str = "0.1",
    has_pkg: bool = False,
) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\nversion: '{version}'\n---\n# {name}\n\nBody.\n"  # noqa: E501
    )
    (skill_dir / "skill.yaml").write_text(
        "dependencies:\n  requires: []\n  used_by: []\n  packages: []\nerrors: {}\n"
    )
    if has_pkg:
        pkg = skill_dir / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
    return skill_dir


# ── Flat discovery (backward compat) ─────────────────────────────────────────

def test_registry_discovers_flat_skill(tmp_path: Path) -> None:
    _write_skill(tmp_path, "alpha")
    registry = SkillRegistry(tmp_path)
    registry.discover()
    assert registry.get_skill("alpha") is not None


def test_registry_reads_frontmatter(tmp_path: Path) -> None:
    _write_skill(tmp_path, "demo", description="Minimal demo skill.", version="0.3")
    (tmp_path / "demo" / "skill.yaml").write_text(
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
    registry = SkillRegistry(tmp_path)
    registry.discover()

    node = registry.get_skill("demo")
    assert node is not None
    assert node.metadata.name == "demo"
    assert node.metadata.description == "Minimal demo skill."
    assert node.metadata.version == "0.3"
    assert node.metadata.dependencies_requires == ["theme_config"]
    assert node.metadata.dependencies_packages == ["pandas"]
    assert "BAD_INPUT" in node.metadata.error_templates
    assert not hasattr(node.metadata, "level")


def test_registry_body_excludes_frontmatter(tmp_path: Path) -> None:
    _write_skill(tmp_path, "demo")
    registry = SkillRegistry(tmp_path)
    registry.discover()
    node = registry.get_skill("demo")
    assert node.instructions.startswith("# demo")
    assert "---" not in node.instructions.splitlines()[0]


def test_registry_ignores_dir_without_skill_md(tmp_path: Path) -> None:
    (tmp_path / "nope").mkdir()
    registry = SkillRegistry(tmp_path)
    registry.discover()
    assert registry.list_top_level() == []


def test_registry_skips_skill_with_invalid_yaml(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "SKILL.md").write_text(
        "---\nname: broken\ndescription: bad\n  indent: wrong\n---\nbody\n"
    )
    _write_skill(tmp_path, "good")
    registry = SkillRegistry(tmp_path)
    registry.discover()
    assert registry.get_skill("broken") is None
    assert registry.get_skill("good") is not None


# ── Hierarchy ─────────────────────────────────────────────────────────────────

def _make_hierarchy(tmp_path: Path) -> SkillRegistry:
    """
    hub/
      SKILL.md
      child_a/
        SKILL.md
        grandchild/
          SKILL.md
      child_b/
        SKILL.md
    standalone/
      SKILL.md
    """
    _write_skill(tmp_path, "hub", description="Hub skill.")
    _write_skill(tmp_path / "hub", "child_a", description="Child A.")
    _write_skill(tmp_path / "hub" / "child_a", "grandchild", description="Grandchild.")
    _write_skill(tmp_path / "hub", "child_b", description="Child B.")
    _write_skill(tmp_path, "standalone", description="Standalone.")
    registry = SkillRegistry(tmp_path)
    registry.discover()
    return registry


def test_list_top_level_returns_only_roots(tmp_path: Path) -> None:
    registry = _make_hierarchy(tmp_path)
    names = [n.metadata.name for n in registry.list_top_level()]
    assert set(names) == {"hub", "standalone"}


def test_get_children_returns_direct_children(tmp_path: Path) -> None:
    registry = _make_hierarchy(tmp_path)
    children = registry.get_children("hub")
    names = {n.metadata.name for n in children}
    assert names == {"child_a", "child_b"}


def test_get_children_returns_empty_for_leaf(tmp_path: Path) -> None:
    registry = _make_hierarchy(tmp_path)
    assert registry.get_children("standalone") == []
    assert registry.get_children("child_b") == []


def test_depth_is_computed_from_nesting(tmp_path: Path) -> None:
    registry = _make_hierarchy(tmp_path)
    assert registry.get_skill("hub").depth == 1
    assert registry.get_skill("child_a").depth == 2
    assert registry.get_skill("grandchild").depth == 3
    assert registry.get_skill("standalone").depth == 1


def test_get_breadcrumb_root(tmp_path: Path) -> None:
    registry = _make_hierarchy(tmp_path)
    assert registry.get_breadcrumb("hub") == ["hub"]


def test_get_breadcrumb_nested(tmp_path: Path) -> None:
    registry = _make_hierarchy(tmp_path)
    assert registry.get_breadcrumb("grandchild") == ["hub", "child_a", "grandchild"]


def test_get_skill_permissive_access(tmp_path: Path) -> None:
    """Any skill at any depth is accessible by name directly."""
    registry = _make_hierarchy(tmp_path)
    assert registry.get_skill("grandchild") is not None
    assert registry.get_skill("child_a") is not None


def test_parent_references_set_correctly(tmp_path: Path) -> None:
    registry = _make_hierarchy(tmp_path)
    grandchild = registry.get_skill("grandchild")
    assert grandchild.parent.metadata.name == "child_a"
    assert grandchild.parent.parent.metadata.name == "hub"
    assert grandchild.parent.parent.parent is None


def test_pkg_excluded_from_discovery(tmp_path: Path) -> None:
    """pkg/ directory must never be discovered as a child skill."""
    _write_skill(tmp_path, "alpha", has_pkg=True)
    registry = SkillRegistry(tmp_path)
    registry.discover()
    alpha = registry.get_skill("alpha")
    assert alpha is not None
    assert alpha.children == []


def test_generate_bootstrap_imports_includes_pkg_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "hub")
    _write_skill(tmp_path / "hub", "leaf_with_pkg", has_pkg=True)
    _write_skill(tmp_path / "hub", "leaf_no_pkg", has_pkg=False)
    registry = SkillRegistry(tmp_path)
    registry.discover()
    imports = registry.generate_bootstrap_imports()
    combined = "\n".join(imports)
    assert "leaf_with_pkg" in combined
    assert "leaf_no_pkg" not in combined
