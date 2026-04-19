"""HooksCheckPlugin — gate ε orchestration.

Mirrors ConfigRegistryPlugin verbatim: per-rule try/except, writes
``integrity-out/{date}/hooks_check.json``, soft ``depends_on=("config_registry",)``
so it can run standalone via ``--plugin hooks_check``.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ...issue import IntegrityIssue
from ...protocol import ScanContext, ScanResult
from .coverage import CoverageDoc, load_coverage
from .matching import matches
from .settings_parser import HookRecord, parse_settings

Rule = Callable[[ScanContext, dict[str, Any], date], list[IntegrityIssue]]

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _default_rules() -> dict[str, Rule]:
    from .rules import broken, missing, unused
    return {
        "hooks.missing": missing.run,
        "hooks.broken": broken.run,
        "hooks.unused": unused.run,
    }


@dataclass
class HooksCheckPlugin:
    name: str = "hooks_check"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ("config_registry",)
    paths: tuple[str, ...] = (
        ".claude/settings.json",
        "config/hooks_coverage.yaml",
    )
    config: dict[str, Any] = field(default_factory=dict)
    today: date = field(default_factory=date.today)
    rules: dict[str, Rule] | None = None

    def scan(self, ctx: ScanContext) -> ScanResult:
        all_issues: list[IntegrityIssue] = []
        rules_run: list[str] = []
        rule_failures: list[str] = []
        coverage: CoverageDoc | None = None
        hooks: list[HookRecord] = []

        coverage_rel = self.config.get("coverage_path", "config/hooks_coverage.yaml")
        settings_rel = self.config.get("settings_path", ".claude/settings.json")
        timeout = int(self.config.get("dry_run_timeout_seconds", 10))
        tolerated_cfg = list(self.config.get("tolerated", []))

        coverage_path = ctx.repo_root / coverage_rel
        settings_path = ctx.repo_root / settings_rel

        try:
            coverage = load_coverage(coverage_path)
        except FileNotFoundError:
            all_issues.append(IntegrityIssue(
                rule="hooks.coverage_missing",
                severity="ERROR",
                node_id="<coverage>",
                location=coverage_rel,
                message=f"missing {coverage_rel} — Plugin D cannot evaluate coverage",
            ))
            return self._finish(ctx, all_issues, rules_run, rule_failures,
                                coverage_summary=None)
        except ValueError as exc:
            all_issues.append(IntegrityIssue(
                rule="hooks.coverage_invalid",
                severity="ERROR",
                node_id="<coverage>",
                location=coverage_rel,
                message=str(exc),
            ))
            return self._finish(ctx, all_issues, rules_run, rule_failures,
                                coverage_summary=None)

        try:
            hooks = parse_settings(settings_path)
        except ValueError as exc:
            all_issues.append(IntegrityIssue(
                rule="hooks.settings_parse",
                severity="ERROR",
                node_id="<settings>",
                location=settings_rel,
                message=str(exc),
            ))
            return self._finish(ctx, all_issues, rules_run, rule_failures,
                                coverage_summary=None)

        if not settings_path.exists():
            all_issues.append(IntegrityIssue(
                rule="hooks.settings_missing",
                severity="INFO",
                node_id="<settings>",
                location=settings_rel,
                message=f"{settings_rel} not present — every coverage rule will report missing",
            ))

        merged_tolerated = tuple(list(coverage.tolerated) + tolerated_cfg)
        from .coverage import CoverageDoc
        coverage = CoverageDoc(rules=coverage.rules, tolerated=merged_tolerated)

        rule_cfg: dict[str, Any] = {
            "_coverage": coverage,
            "_hooks": hooks,
            "_dry_run_timeout": timeout,
            "_fixtures_dir": FIXTURES_DIR,
        }
        rules = self.rules if self.rules is not None else _default_rules()
        disabled = set(self.config.get("disabled_rules", []))

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
                    location=f"hooks_check/{rule_id}",
                    message=f"{type(exc).__name__}: {exc}",
                ))

        rules_total = len(coverage.rules)
        rules_satisfied = sum(
            1 for r in coverage.rules
            if any(matches(r, h) for h in hooks)
        )
        broken_count = sum(
            1 for i in all_issues if i.rule == "hooks.broken"
        )
        coverage_summary = {
            "rules_total": rules_total,
            "rules_satisfied": rules_satisfied,
            "hooks_total": len(hooks),
            "hooks_dry_run_green": max(0, rules_satisfied - broken_count),
        }

        return self._finish(ctx, all_issues, rules_run, rule_failures,
                            coverage_summary=coverage_summary)

    def _finish(
        self,
        ctx: ScanContext,
        all_issues: list[IntegrityIssue],
        rules_run: list[str],
        rule_failures: list[str],
        coverage_summary: dict[str, Any] | None,
    ) -> ScanResult:
        run_dir = ctx.repo_root / "integrity-out" / self.today.isoformat()
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact = run_dir / "hooks_check.json"
        payload: dict[str, Any] = {
            "plugin": self.name,
            "version": self.version,
            "date": self.today.isoformat(),
            "rules_run": rules_run,
            "failures": rule_failures,
            "issues": [asdict(i) for i in all_issues],
        }
        if coverage_summary is not None:
            payload["coverage_summary"] = coverage_summary
        artifact.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            issues=all_issues,
            artifacts=[artifact],
            failures=rule_failures,
        )
