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

KNOWN_PLUGINS = ("graph_extension", "graph_lint", "doc_audit")


def _build_engine(repo_root: Path, only: str | None, skip_augment: bool) -> IntegrityEngine:
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
        # Drop depends_on when graph_extension isn't registered so the
        # engine topo-sort doesn't require a plugin that wasn't loaded.
        if not want_extension:
            from dataclasses import replace

            plugin = replace(plugin, depends_on=())
        engine.register(plugin)

    audit_cfg_enabled = enabled.get("doc_audit", {}).get("enabled", True)
    want_audit = (only is None or only == "doc_audit") and audit_cfg_enabled
    if want_audit:
        from .plugins.doc_audit.plugin import DocAuditPlugin

        audit_plugin = DocAuditPlugin(config=enabled.get("doc_audit", {}))
        # Drop depends_on when graph_extension isn't registered so the
        # engine topo-sort doesn't require an unloaded plugin.
        if not want_extension:
            from dataclasses import replace

            audit_plugin = replace(audit_plugin, depends_on=())
        engine.register(audit_plugin)

    return engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.integrity")
    parser.add_argument("--plugin", default=None, help="Run only the named plugin")
    parser.add_argument(
        "--no-augment", action="store_true", help="Skip Plugin A's graph augmentation"
    )
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    today = date.today()

    engine = _build_engine(repo_root, args.plugin, args.no_augment)
    results = engine.run()

    report_paths = write_report(repo_root, results, today=today, retention_days=args.retention_days)

    # snapshot the merged graph for tomorrow's diffs
    merged = GraphSnapshot.load(repo_root)
    write_snapshot(repo_root, {"nodes": merged.nodes, "links": merged.links}, today=today)
    prune_older_than(repo_root, days=args.retention_days, today=today)

    print(f"Wrote {report_paths.report_md.relative_to(repo_root)}", file=sys.stderr)
    print(f"Wrote {report_paths.latest_md.relative_to(repo_root)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
