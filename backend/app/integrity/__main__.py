"""Integrity engine CLI: python -m backend.app.integrity."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .config import load_config
from .engine import IntegrityEngine
from .report import write_report
from .schema import GraphSnapshot
from .snapshots import prune_older_than, write_snapshot

KNOWN_PLUGINS = ("graph_extension", "graph_lint", "doc_audit", "config_registry", "hooks_check", "autofix")  # noqa: E501


def _build_engine(
    repo_root: Path,
    only: str | None,
    skip_augment: bool,
    check_only: bool = False,
    apply: bool = False,
) -> IntegrityEngine:
    cfg = load_config(repo_root)
    engine = IntegrityEngine(repo_root)
    enabled = cfg.plugins
    if only is not None and only not in KNOWN_PLUGINS:
        raise SystemExit(f"unknown plugin: {only!r} (known: {', '.join(KNOWN_PLUGINS)})")

    want_extension = (only is None or only == "graph_extension") and not skip_augment
    if want_extension and enabled.get("graph_extension", {}).get("enabled", True):
        from .plugins.graph_extension.plugin import GraphExtensionPlugin
        engine.register(GraphExtensionPlugin())

    lint_cfg_enabled = enabled.get("graph_lint", {}).get("enabled", True)
    want_lint = (only is None or only == "graph_lint") and lint_cfg_enabled
    if want_lint:
        from .plugins.graph_lint.plugin import GraphLintPlugin
        plugin = GraphLintPlugin(config=enabled.get("graph_lint", {}))
        if not want_extension:
            from dataclasses import replace
            plugin = replace(plugin, depends_on=())
        engine.register(plugin)

    audit_cfg_enabled = enabled.get("doc_audit", {}).get("enabled", True)
    want_audit = (only is None or only == "doc_audit") and audit_cfg_enabled
    if want_audit:
        from .plugins.doc_audit.plugin import DocAuditPlugin
        audit_plugin = DocAuditPlugin(config=enabled.get("doc_audit", {}))
        if not want_extension:
            from dataclasses import replace
            audit_plugin = replace(audit_plugin, depends_on=())
        engine.register(audit_plugin)

    cr_cfg_enabled = enabled.get("config_registry", {}).get("enabled", True)
    want_cr = (only is None or only == "config_registry") and cr_cfg_enabled
    if want_cr:
        from .plugins.config_registry.plugin import ConfigRegistryPlugin
        cr_plugin = ConfigRegistryPlugin(
            config=enabled.get("config_registry", {}),
            check_only=check_only,
        )
        engine.register(cr_plugin)

    hc_cfg_enabled = enabled.get("hooks_check", {}).get("enabled", True)
    want_hc = (only is None or only == "hooks_check") and hc_cfg_enabled
    if want_hc:
        from .plugins.hooks_check.plugin import HooksCheckPlugin
        hc_plugin = HooksCheckPlugin(config=enabled.get("hooks_check", {}))
        if only == "hooks_check":
            from dataclasses import replace
            hc_plugin = replace(hc_plugin, depends_on=())
        engine.register(hc_plugin)

    af_cfg_enabled = enabled.get("autofix", {}).get("enabled", True)
    want_af = (only is None or only == "autofix") and af_cfg_enabled
    if want_af:
        from .plugins.autofix.plugin import AutofixPlugin
        af_plugin = AutofixPlugin(
            config=enabled.get("autofix", {}),
            apply=apply,
        )
        if only == "autofix":
            from dataclasses import replace
            af_plugin = replace(af_plugin, depends_on=())
        engine.register(af_plugin)

    return engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.integrity")
    parser.add_argument("--plugin", default=None, help="Run only the named plugin")
    parser.add_argument(
        "--no-augment", action="store_true", help="Skip Plugin A's graph augmentation"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="config_registry: dry-run, fail if config/manifest.yaml would change",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="autofix: enable apply mode (requires autofix.apply: true in config too)",
    )
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    today = date.today()

    engine = _build_engine(
        repo_root, args.plugin, args.no_augment,
        check_only=args.check, apply=args.apply,
    )
    results = engine.run()

    report_paths = write_report(
        repo_root, results, today=today, retention_days=args.retention_days,
    )

    merged = GraphSnapshot.load(repo_root)
    write_snapshot(repo_root, {"nodes": merged.nodes, "links": merged.links}, today=today)
    prune_older_than(repo_root, days=args.retention_days, today=today)

    print(f"Wrote {report_paths.report_md.relative_to(repo_root)}", file=sys.stderr)
    print(f"Wrote {report_paths.latest_md.relative_to(repo_root)}", file=sys.stderr)

    # --check: exit non-zero if any config.check_drift issue surfaced.
    if args.check:
        for r in results:
            for i in r.issues:
                if i.rule == "config.check_drift":
                    return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
