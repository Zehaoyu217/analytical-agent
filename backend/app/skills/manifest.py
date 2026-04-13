from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from app.skills.registry import SkillRegistry


@dataclass(frozen=True)
class ManifestIssue:
    """A detected breaking change or inconsistency."""

    skill: str
    severity: str  # "breaking", "warning", "info"
    message: str
    affected: list[str]


class SkillManifest:
    """Tracks skill dependency graph and detects breaking changes."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def check(self) -> list[ManifestIssue]:
        """Check for dependency issues. Returns list of issues found."""
        issues: list[ManifestIssue] = []
        graph = self._registry.get_dependency_graph()
        all_skills = set(self._registry.list_skills())

        for skill_name, requires in graph.items():
            for dep in requires:
                if dep not in all_skills:
                    issues.append(
                        ManifestIssue(
                            skill=skill_name,
                            severity="breaking",
                            message=f"Required skill '{dep}' not found",
                            affected=[skill_name],
                        )
                    )
        return issues


def _main() -> int:
    skills_root = Path(__file__).resolve().parent
    registry = SkillRegistry(skills_root)
    registry.discover()
    manifest = SkillManifest(registry)
    skills = sorted(registry.list_skills())
    print(f"Discovered {len(skills)} skills: {', '.join(skills) or '(none)'}")
    issues = manifest.check()
    if not issues:
        print("OK: no manifest issues.")
        return 0
    breaking = [i for i in issues if i.severity == "breaking"]
    for issue in issues:
        print(f"[{issue.severity}] {issue.skill}: {issue.message}")
    return 1 if breaking else 0


if __name__ == "__main__":
    sys.exit(_main())
