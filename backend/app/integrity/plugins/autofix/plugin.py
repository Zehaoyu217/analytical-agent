"""AutofixPlugin — gate ζ orchestration.

Mirrors HooksCheckPlugin/ConfigRegistryPlugin layering: per-class try/except,
writes integrity-out/{date}/autofix.json, soft depends_on=("graph_lint",
"doc_audit", "config_registry") so it can run standalone via
`--plugin autofix` (uses dataclasses.replace(depends_on=())).

Two-gate apply mode: `apply` field (CLI flag) AND config["apply"] (yaml gate)
must both be True for the dispatcher to run. Either off → dry-run.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ...issue import IntegrityIssue
from ...protocol import ScanContext, ScanResult
from .circuit_breaker import disabled_classes, load_state
from .diff import Diff
from .fixers import get_registry
from .loader import read_today
from .pr_dispatcher import DispatcherConfig, PRResult, dispatch_class
from .safety import check_apply_preflight, check_upstream

DEFAULT_FIX_CLASSES = (
    "claude_md_link",
    "doc_link_renamed",
    "manifest_regen",
    "dead_directive_cleanup",
    "health_dashboard_refresh",
)


@dataclass
class AutofixPlugin:
    name: str = "autofix"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ("graph_lint", "doc_audit", "config_registry")
    paths: tuple[str, ...] = (
        "config/integrity.yaml",
        "config/autofix_state.yaml",
    )
    config: dict[str, Any] = field(default_factory=dict)
    today: date = field(default_factory=date.today)
    apply: bool = False  # CLI flag

    def scan(self, ctx: ScanContext) -> ScanResult:
        repo = ctx.repo_root
        all_issues: list[IntegrityIssue] = []
        failures: list[str] = []

        config_apply = bool(self.config.get("apply", False))
        effective_apply = self.apply and config_apply

        artifacts = read_today(repo / "integrity-out", self.today)

        upstream_verdict = check_upstream(artifacts)
        if not upstream_verdict.ok:
            all_issues.append(IntegrityIssue(
                rule=upstream_verdict.rule,
                severity=upstream_verdict.severity or "INFO",
                node_id="<upstream>",
                location="integrity-out",
                message=upstream_verdict.message,
                evidence={"failures": dict(artifacts.failures)},
            ))
            return self._finish(
                repo, all_issues, fix_classes_run=[],
                fix_classes_skipped=dict(artifacts.failures),
                diffs_by_class={}, pr_results={},
                effective_apply=effective_apply, failures=failures,
            )

        state = load_state(repo / "config" / "autofix_state.yaml")
        cb_cfg = self.config.get("circuit_breaker", {})
        max_human_edits = int(cb_cfg.get("max_human_edits", 2))
        cb_disabled = disabled_classes(state, max_human_edits=max_human_edits)

        fc_cfg = self.config.get("fix_classes", {}) or {}
        configured_classes = list(DEFAULT_FIX_CLASSES)
        registry = get_registry()
        diffs_by_class: dict[str, list[Diff]] = {}
        fix_classes_run: list[str] = []
        fix_classes_skipped: dict[str, str] = {}

        for fix_class in configured_classes:
            class_cfg = fc_cfg.get(fix_class, {}) or {}
            if class_cfg.get("enabled", True) is False:
                fix_classes_skipped[fix_class] = "disabled_in_config"
                all_issues.append(IntegrityIssue(
                    rule="autofix.skipped_disabled",
                    severity="INFO",
                    node_id=fix_class,
                    location=f"autofix/{fix_class}",
                    message=f"{fix_class} disabled in config",
                    evidence={"class": fix_class, "reason": "config"},
                ))
                continue
            if fix_class in cb_disabled:
                fix_classes_skipped[fix_class] = "disabled_circuit_breaker"
                all_issues.append(IntegrityIssue(
                    rule="autofix.class_disabled",
                    severity="ERROR",
                    node_id=fix_class,
                    location=f"autofix/{fix_class}",
                    message=(
                        f"{fix_class} disabled by circuit breaker "
                        f"(>{max_human_edits} human-edited PRs in window)"
                    ),
                    evidence={
                        "class": fix_class,
                        "human_edited": state.classes[fix_class].human_edited,
                    },
                ))
                continue

            propose = registry[fix_class]
            try:
                diffs = propose(artifacts, repo, dict(class_cfg))
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{fix_class}: {type(exc).__name__}: {exc}")
                all_issues.append(IntegrityIssue(
                    rule="autofix.fixer_failed",
                    severity="ERROR",
                    node_id=fix_class,
                    location=f"autofix/{fix_class}",
                    message=f"{type(exc).__name__}: {exc}",
                    evidence={"class": fix_class},
                ))
                fix_classes_skipped[fix_class] = "fixer_exception"
                continue

            non_noop = [d for d in diffs if not d.is_noop()]
            if not non_noop:
                all_issues.append(IntegrityIssue(
                    rule="autofix.skipped_noop",
                    severity="INFO",
                    node_id=fix_class,
                    location=f"autofix/{fix_class}",
                    message=f"{fix_class} produced no real diffs",
                    evidence={"class": fix_class},
                ))
                fix_classes_skipped[fix_class] = "noop"
                continue

            diffs_by_class[fix_class] = non_noop
            fix_classes_run.append(fix_class)
            all_issues.append(IntegrityIssue(
                rule="autofix.proposed",
                severity="INFO",
                node_id=fix_class,
                location=f"autofix/{fix_class}",
                message=f"{fix_class}: {len(non_noop)} diff(s) proposed",
                evidence={"class": fix_class, "diff_count": len(non_noop)},
            ))

        pr_results: dict[str, PRResult] = {}
        if effective_apply and diffs_by_class:
            dcfg = DispatcherConfig(
                repo_root=repo,
                branch_prefix=str(self.config.get(
                    "branch_prefix", "integrity/autofix")),
                commit_author=str(self.config.get(
                    "commit_author", "Integrity Autofix <integrity@local>")),
                gh_executable=str(self.config.get("gh_executable", "gh")),
                subprocess_timeout_seconds=int(self.config.get(
                    "dispatcher_subprocess_timeout_seconds", 60)),
                today=self.today,
                dry_run=False,
            )
            apply_verdict = check_apply_preflight(repo, dcfg.gh_executable)
            if not apply_verdict.ok:
                all_issues.append(IntegrityIssue(
                    rule=apply_verdict.rule,
                    severity=apply_verdict.severity or "ERROR",
                    node_id="<apply-preflight>",
                    location=repo.as_posix(),
                    message=apply_verdict.message,
                ))
            else:
                for fix_class, diffs in diffs_by_class.items():
                    try:
                        pr_results[fix_class] = dispatch_class(
                            fix_class, diffs, dcfg,
                        )
                    except Exception as exc:  # noqa: BLE001
                        failures.append(
                            f"dispatch:{fix_class}: {type(exc).__name__}: {exc}"
                        )
                        all_issues.append(IntegrityIssue(
                            rule="apply.git_failure",
                            severity="ERROR",
                            node_id=fix_class,
                            location=f"autofix/{fix_class}",
                            message=f"{type(exc).__name__}: {exc}",
                        ))

        return self._finish(
            repo, all_issues,
            fix_classes_run=fix_classes_run,
            fix_classes_skipped=fix_classes_skipped,
            diffs_by_class=diffs_by_class,
            pr_results=pr_results,
            effective_apply=effective_apply,
            failures=failures,
        )

    def _finish(
        self,
        repo: Path,
        all_issues: list[IntegrityIssue],
        *,
        fix_classes_run: list[str],
        fix_classes_skipped: dict[str, str],
        diffs_by_class: dict[str, list[Diff]],
        pr_results: dict[str, PRResult],
        effective_apply: bool,
        failures: list[str],
    ) -> ScanResult:
        run_dir = repo / "integrity-out" / self.today.isoformat()
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact = run_dir / "autofix.json"

        diffs_payload: dict[str, list[dict[str, Any]]] = {}
        for fix_class in DEFAULT_FIX_CLASSES:
            diffs_payload[fix_class] = [
                {
                    "path": str(d.path),
                    "rationale": d.rationale,
                    "is_noop": d.is_noop(),
                    "source_issues": [
                        {
                            "plugin": r.plugin,
                            "rule": r.rule,
                            "message": r.message,
                            "evidence": r.evidence,
                        } for r in d.source_issues
                    ],
                    "diff_preview": d.new_content[:240],
                }
                for d in diffs_by_class.get(fix_class, [])
            ]

        pr_payload = {
            fc: {
                "action": pr.action,
                "branch": pr.branch,
                "pr_number": pr.pr_number,
                "pr_url": pr.pr_url,
                "diff_count": pr.diff_count,
                "error_rule": pr.error_rule,
                "error_message": pr.error_message,
            }
            for fc, pr in pr_results.items()
        }

        payload = {
            "plugin": self.name,
            "version": self.version,
            "date": self.today.isoformat(),
            "mode": "apply" if effective_apply else "dry-run",
            "fix_classes_run": fix_classes_run,
            "fix_classes_skipped": fix_classes_skipped,
            "diffs_by_class": diffs_payload,
            "pr_results": pr_payload,
            "issues": [asdict(i) for i in all_issues],
            "failures": failures,
        }
        artifact.write_text(json.dumps(payload, indent=2, sort_keys=True))

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            issues=all_issues,
            artifacts=[artifact],
            failures=failures,
        )
