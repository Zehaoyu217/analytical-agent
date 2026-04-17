"""ConfigRegistryPlugin — gate δ orchestration.

Mirrors GraphLintPlugin / DocAuditPlugin shape: per-rule try/except,
writes integrity-out/{date}/config_registry.json, registers depends_on=()
to run standalone or alongside Plugin A's graph_extension.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from ...issue import IntegrityIssue
from ...protocol import ScanContext, ScanResult
from .builders.configs import ConfigsBuilder
from .builders.functions import FunctionsBuilder
from .builders.routes import RoutesBuilder
from .builders.scripts import ScriptsBuilder
from .builders.skills import SkillsBuilder
from .manifest import (
    GENERATOR_VERSION,
    empty_manifest,
    read_manifest,
    write_manifest,
)
from .rules.removed import build_dep_index

Rule = Callable[[ScanContext, dict[str, Any], date], list[IntegrityIssue]]


def _default_rules() -> dict[str, Rule]:
    from .rules import added, removed, schema_drift
    return {
        "config.added": added.run,
        "config.removed": removed.run,
        "config.schema_drift": schema_drift.run,
    }


@dataclass
class ConfigRegistryPlugin:
    name: str = "config_registry"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ()
    paths: tuple[str, ...] = (
        "backend/app/skills/**/SKILL.md",
        "backend/app/skills/**/skill.yaml",
        "scripts/**/*.py",
        "scripts/**/*.sh",
        "scripts/**/*.ts",
        "scripts/**/*.js",
        "pyproject.toml",
        "package.json",
        ".claude/settings.json",
        "vite.config.*",
        "tsconfig*.json",
        "Dockerfile*",
        "Makefile",
        ".env.example",
        "config/**",
        "infra/**",
        "backend/app/api/**/*.py",
    )
    config: dict[str, Any] = field(default_factory=dict)
    today: date = field(default_factory=date.today)
    rules: dict[str, Rule] | None = None
    check_only: bool = False

    def scan(self, ctx: ScanContext) -> ScanResult:
        builder_failures: list[str] = []
        current = self.build_current(ctx, builder_failures)

        manifest_rel = self.config.get("manifest_path", "config/manifest.yaml")
        manifest_path = ctx.repo_root / manifest_rel
        prior = read_manifest(manifest_path)

        # Write current manifest unless --check
        if not self.check_only:
            write_manifest(manifest_path, current)

        rule_cfg = dict(self.config)
        rule_cfg["_current_manifest"] = current
        rule_cfg["_prior_manifest"] = prior
        rule_cfg["_dep_graph"] = build_dep_index(ctx.graph)

        rules = self.rules if self.rules is not None else _default_rules()
        disabled = set(self.config.get("disabled_rules", []))

        all_issues: list[IntegrityIssue] = []
        rules_run: list[str] = []
        rule_failures: list[str] = []

        for rule_id, fn in rules.items():
            if rule_id in disabled:
                continue
            try:
                issues = fn(ctx, rule_cfg, self.today)
                all_issues.extend(issues)
                rules_run.append(rule_id)
            except Exception as exc:  # noqa: BLE001
                rule_failures.append(f"{rule_id}: {type(exc).__name__}: {exc}")
                all_issues.append(IntegrityIssue(
                    rule=rule_id,
                    severity="ERROR",
                    node_id="<rule-failure>",
                    location=f"config_registry/{rule_id}",
                    message=f"{type(exc).__name__}: {exc}",
                ))

        # --check: fail if manifest write would have changed content.
        if self.check_only:
            import yaml
            current_yaml = yaml.safe_dump(current, sort_keys=False)
            prior_yaml = yaml.safe_dump(prior, sort_keys=False)
            if current_yaml != prior_yaml:
                all_issues.append(IntegrityIssue(
                    rule="config.check_drift",
                    severity="ERROR",
                    node_id="<manifest>",
                    location=manifest_rel,
                    message="manifest would change — run `make integrity-config` and commit",
                ))

        run_dir = ctx.repo_root / "integrity-out" / self.today.isoformat()
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact = run_dir / "config_registry.json"
        artifact.write_text(json.dumps({
            "plugin": self.name,
            "version": self.version,
            "date": self.today.isoformat(),
            "rules_run": rules_run,
            "failures": rule_failures + builder_failures,
            "issues": [asdict(i) for i in all_issues],
        }, indent=2, sort_keys=True))

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            issues=all_issues,
            artifacts=[artifact],
            failures=rule_failures + builder_failures,
        )

    def build_current(
        self, ctx: ScanContext, failures: list[str]
    ) -> dict[str, Any]:
        current = empty_manifest()
        current["generated_at"] = self.today.isoformat()
        current["generator_version"] = GENERATOR_VERSION

        # Skills
        try:
            skills, f = SkillsBuilder(
                skills_root=ctx.repo_root / self.config.get("skills_root", "backend/app/skills"),
                repo_root=ctx.repo_root,
            ).build()
            current["skills"] = [s.to_dict() for s in skills]
            failures.extend(f)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"builders.skills: {type(exc).__name__}: {exc}")

        # Scripts
        try:
            scripts, f = ScriptsBuilder(
                scripts_root=ctx.repo_root / self.config.get("scripts_root", "scripts"),
                repo_root=ctx.repo_root,
            ).build()
            current["scripts"] = [s.to_dict() for s in scripts]
            failures.extend(f)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"builders.scripts: {type(exc).__name__}: {exc}")

        # Routes
        try:
            routes, f = RoutesBuilder(graph=ctx.graph).build()
            current["routes"] = [r.to_dict() for r in routes]
            failures.extend(f)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"builders.routes: {type(exc).__name__}: {exc}")

        # Configs
        try:
            configs, f = ConfigsBuilder(
                repo_root=ctx.repo_root,
                globs=list(self.config.get("config_globs", [])),
                excluded=list(self.config.get("excluded_paths", [])),
            ).build()
            current["configs"] = [c.to_dict() for c in configs]
            failures.extend(f)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"builders.configs: {type(exc).__name__}: {exc}")

        # Functions
        try:
            funcs, f = FunctionsBuilder(
                repo_root=ctx.repo_root,
                search_globs=list(self.config.get("function_search_globs", [])),
                decorators=list(self.config.get("function_decorators", [])),
                event_handlers=list(self.config.get("function_event_handlers", [])),
            ).build()
            current["functions"] = [fn.to_dict() for fn in funcs]
            failures.extend(f)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"builders.functions: {type(exc).__name__}: {exc}")

        return current
