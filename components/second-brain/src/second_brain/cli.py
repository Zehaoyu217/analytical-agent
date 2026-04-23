from __future__ import annotations

from io import StringIO
from pathlib import Path

import click
from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.habits.loader import habits_path, load_habits, save_habits, validate_habits_file
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest
from second_brain.llm.providers import model_readiness
from second_brain.reindex import reindex as run_reindex
from second_brain.research.compiler import compile_center
from second_brain.research.obsidian import export_obsidian_view
from second_brain.research.writeback import record_experiment, record_project, record_synthesis


@click.group()
@click.version_option(package_name="second-brain")
def cli() -> None:
    """Second Brain — personal knowledge base (v0.1 foundation)."""


def _has_live_provider(*models: str) -> bool:
    import os

    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    for model in models:
        ok, _ = model_readiness(
            model,
            openrouter_key=openrouter_key,
            anthropic_key=anthropic_key,
        )
        if ok:
            return True
    return False


def _require_live_provider(*models: str) -> None:
    import os

    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    reasons: list[str] = []
    for model in models:
        ok, reason = model_readiness(
            model,
            openrouter_key=openrouter_key,
            anthropic_key=anthropic_key,
        )
        if ok:
            return
        reasons.append(f"{model}: {reason}")
    raise click.ClickException("no live model available:\n- " + "\n- ".join(reasons))


@cli.command(name="ingest")
@click.argument("path_or_slug", required=False)
@click.option("--retry", "retry_flag", is_flag=True,
              help="Retry a previously-failed source by slug.")
def _ingest(path_or_slug: str | None, retry_flag: bool) -> None:
    """Ingest a file/URL, or retry a failed source (`--retry <slug>`)."""
    cfg = Config.load()
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)

    if retry_flag:
        if not path_or_slug:
            raise click.UsageError("--retry requires a source slug")
        from second_brain.ingest.retry import RetryError, retry_source

        try:
            retry_source(path_or_slug, cfg=cfg)
        except RetryError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"retry ok: {path_or_slug}")
        return

    if not path_or_slug:
        raise click.UsageError("PATH_OR_SLUG required")

    path = Path(path_or_slug)
    if not path.exists():
        raise click.ClickException(f"path not found: {path_or_slug}")
    inp = IngestInput.from_path(path)
    try:
        folder = ingest(inp, cfg=cfg)
    except IngestError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"ingested {folder.root.name}")


@cli.command(name="process-inbox")
def _process_inbox() -> None:
    """Ingest every file in ~/second-brain/inbox/ (non-recursive)."""
    from second_brain.inbox.runner import InboxRunner

    cfg = Config.load()
    result = InboxRunner(cfg).run()

    if not result.ok and not result.failed:
        click.echo("inbox empty")
        return
    click.echo(f"OK: {len(result.ok)}")
    for slug in result.ok:
        click.echo(f"  + {slug}")
    if result.failed:
        click.echo(f"FAILED: {len(result.failed)}")
        for fail in result.failed:
            tag = " [quarantined]" if fail.quarantined else ""
            click.echo(f"  x {fail.path} (attempts={fail.attempts}){tag} — {fail.error}")


@cli.command(name="watch")
@click.option("--once", is_flag=True,
              help="Drain current inbox contents then exit (cron-style).")
def _watch(once: bool) -> None:
    """Watch ~/second-brain/inbox/ and ingest new drops."""
    import signal
    import time

    from second_brain.inbox.runner import InboxRunner
    from second_brain.watch.daemon import Watcher

    cfg = Config.load()

    if once:
        result = InboxRunner(cfg).run()
        click.echo(f"drained: ok={len(result.ok)} failed={len(result.failed)}")
        return

    watcher = Watcher(cfg)
    watcher.start()
    click.echo(f"watching {cfg.inbox_dir} (Ctrl-C to stop)")

    def _handle_sigint(signum, frame):  # type: ignore[no-untyped-def]
        watcher.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)
    try:
        while True:
            time.sleep(1.0)
    finally:
        watcher.stop()


@cli.command()
@click.option(
    "--with-vectors",
    "with_vectors",
    is_flag=True,
    default=False,
    help="Also populate .sb/vectors.sqlite for hybrid retrieval.",
)
def reindex(with_vectors: bool) -> None:
    """Rebuild .sb/ indexes from markdown."""
    cfg = Config.load()
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    run_reindex(cfg, with_vectors=with_vectors)
    if with_vectors:
        click.echo("reindex complete (with vectors)")
    else:
        click.echo("reindex complete")


@cli.command()
def status() -> None:
    """Show KB size + index freshness snapshot."""
    cfg = Config.load()
    sources = 0
    if cfg.sources_dir.exists():
        sources = sum(1 for _ in cfg.sources_dir.glob("*/_source.md"))
    claims = 0
    if cfg.claims_dir.exists():
        claims = sum(1 for p in cfg.claims_dir.glob("*.md") if p.parent.name != "resolutions")
    duck_exists = cfg.duckdb_path.exists()
    fts_exists = cfg.fts_path.exists()
    click.echo(f"home: {cfg.home}")
    click.echo(f"sources: {sources}")
    click.echo(f"claims: {claims}")
    click.echo(f"indexes: duckdb={'y' if duck_exists else 'n'} fts={'y' if fts_exists else 'n'}")


@cli.command(name="search")
@click.argument("query")
@click.option("--k", default=5, type=int)
@click.option("--scope", type=click.Choice(["sources", "claims", "both"]), default="both")
@click.option("--taxonomy", default=None)
@click.option("--neighbors/--no-neighbors", default=False)
@click.option("--json", "as_json", is_flag=True, default=False)
def _search(query: str, k: int, scope: str, taxonomy: str | None,
            neighbors: bool, as_json: bool) -> None:
    """Brokered search over center memory plus side evidence."""
    from second_brain.research.broker import broker_search

    cfg = Config.load()
    hits = broker_search(
        cfg,
        query=query,
        k=k,
        scope=scope,
        with_neighbors=neighbors,
    )
    if as_json:
        import json as _json
        click.echo(_json.dumps([
            {
                "id": h.id,
                "kind": h.kind,
                "title": h.title,
                "score": h.score,
                "matched_field": h.matched_field,
                "summary": h.summary,
                "section_title": h.section_title,
                "page_start": h.page_start,
                "page_end": h.page_end,
                "evidence": [
                    {
                        "id": ev.id,
                        "kind": ev.kind,
                        "score": ev.score,
                        "matched_field": ev.matched_field,
                        "source_id": ev.source_id,
                        "chunk_id": ev.chunk_id,
                        "section_title": ev.section_title,
                        "page_start": ev.page_start,
                        "page_end": ev.page_end,
                    }
                    for ev in h.evidence
                ],
            }
            for h in hits.hits
        ]))
        return
    for h in hits.hits:
        line = f"{h.score:6.3f}  {h.kind:10s}  {h.id}  {h.title}  ({h.matched_field})"
        click.echo(line)
        if h.section_title or h.page_start is not None:
            page = ""
            if h.page_start is not None:
                page = (
                    f"pp.{h.page_start}-{h.page_end}"
                    if h.page_end and h.page_end != h.page_start
                    else f"p.{h.page_start}"
                )
            detail = " · ".join(part for part in [h.section_title, page] if part)
            if detail:
                click.echo(f"         provenance -> {detail}")
        for ev in h.evidence[:2]:
            page = ""
            if ev.page_start is not None:
                page = (
                    f"pp.{ev.page_start}-{ev.page_end}"
                    if ev.page_end and ev.page_end != ev.page_start
                    else f"p.{ev.page_start}"
                )
            detail = ", ".join(
                part for part in [ev.matched_field, ev.section_title, page] if part
            )
            click.echo(f"         evidence -> {ev.id} ({ev.kind}, {detail})")


@cli.command(name="load")
@click.argument("node_id")
@click.option("--depth", default=0, type=int)
@click.option("--relations", default=None, help="comma-separated relation filter")
@click.option("--json", "as_json", is_flag=True, default=False)
def _load(node_id: str, depth: int, relations: str | None, as_json: bool) -> None:
    """Fetch a node and optionally its graph neighborhood."""
    from second_brain.load import LoadError, load_node
    cfg = Config.load()
    rels = [r.strip() for r in relations.split(",")] if relations else None
    try:
        result = load_node(cfg, node_id, depth=depth, relations=rels)
    except LoadError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        import json as _json
        click.echo(_json.dumps({
            "root": result.root, "neighbors": result.neighbors, "edges": result.edges,
        }))
        return
    click.echo(f"# {result.root['id']}")
    click.echo(f"kind: {result.root['kind']}")
    for k, v in result.root.items():
        if k in {"id", "kind"} or v is None:
            continue
        click.echo(f"{k}: {v}")
    if result.neighbors:
        click.echo(f"\nneighbors ({len(result.neighbors)}):")
        for n in result.neighbors:
            click.echo(f"  - {n['id']} ({n['kind']})")


@cli.command(name="reason")
@click.argument("start_id")
@click.option("--walk", required=True, help="edge relation to walk, e.g. 'refines'")
@click.option("--direction", type=click.Choice(["outbound", "inbound", "both"]),
              default="outbound")
@click.option("--max-depth", default=3, type=int)
@click.option("--terminator", default=None)
@click.option("--json", "as_json", is_flag=True, default=False)
def _reason(start_id: str, walk: str, direction: str, max_depth: int,
            terminator: str | None, as_json: bool) -> None:
    """Walk the graph from start_id following a typed relation."""
    from second_brain.reason import GraphPattern, sb_reason
    cfg = Config.load()
    paths = sb_reason(
        cfg, start_id=start_id,
        pattern=GraphPattern(walk=walk, direction=direction,  # type: ignore[arg-type]
                              max_depth=max_depth, terminator=terminator),
    )
    if as_json:
        import json as _json
        click.echo(_json.dumps(paths))
        return
    for path in paths:
        click.echo(" -> ".join(path))


@cli.command(name="extract")
@click.argument("source_id")
@click.option("--density", type=click.Choice(["sparse", "moderate", "dense"]),
              default=None,
              help="Override habits-derived density for this run.")
@click.option("--rubric", default=None,
              help="Override habits.extraction.claim_rubric for this run.")
@click.option("--model", default=None,
              help="Force a specific live model, e.g. mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit.")
@click.option("--small-model", default=None,
              help="Local/default model for smaller inputs. Defaults to an Apple Silicon MLX Gemma 4 E2B text model.")
@click.option("--large-model", default=None,
              help="Deeper model for larger inputs. Defaults to an Apple Silicon MLX Gemma 4 E4B text model.")
@click.option("--large-input-chars", default=None, type=int,
              help="Switch to the large model when the source body exceeds this character count.")
@click.option("--live/--fake", default=None,
              help="Force a real LLM call (--live) or fake client (--fake). "
                   "Default: fake if no live provider is available or SB_FAKE_CLAIMS is set.")
def _extract(source_id: str, density: str | None, rubric: str | None,
             model: str | None, small_model: str | None,
             large_model: str | None, large_input_chars: int | None,
             live: bool | None) -> None:
    """Extract claims from an ingested source."""
    import json as _json
    import os

    from second_brain.extract.client import (
        DEFAULT_LARGE_INPUT_CHARS,
        DEFAULT_LARGE_MODEL,
        DEFAULT_SMALL_MODEL,
        AutoExtractorClient,
        FakeExtractorClient,
    )
    from second_brain.extract.worker import extract_source
    from second_brain.frontmatter import load_document
    from second_brain.habits.density import resolve_density
    from second_brain.habits.loader import load_habits

    cfg = Config.load()
    habits = load_habits(cfg)

    # Read the source frontmatter so we can pass kind + taxonomy into the resolver.
    src_path = cfg.sources_dir / source_id / "_source.md"
    if not src_path.exists():
        raise click.ClickException(f"source not found: {source_id}")
    meta, _ = load_document(src_path)
    resolved_density = resolve_density(
        kind=str(meta.get("kind") or ""),
        taxonomy=meta.get("habit_taxonomy") or None,
        habits=habits,
        explicit=density,  # type: ignore[arg-type]
    )
    resolved_rubric = rubric if rubric is not None else habits.extraction.claim_rubric

    if os.environ.get("SB_DENSITY_PROBE"):
        click.echo(f"density={resolved_density}")

    fake_payload = os.environ.get("SB_FAKE_CLAIMS")
    resolved_small_model = small_model or DEFAULT_SMALL_MODEL
    resolved_large_model = large_model or DEFAULT_LARGE_MODEL
    resolved_large_input_chars = large_input_chars or DEFAULT_LARGE_INPUT_CHARS
    candidate_models = [m for m in [model, resolved_small_model, resolved_large_model] if m]
    if live is True:
        _require_live_provider(*candidate_models)
    use_fake = (live is False) or bool(fake_payload) or (
        live is not True and not _has_live_provider(*candidate_models)
    )
    if use_fake:
        canned = _json.loads(fake_payload) if fake_payload else []
        client = FakeExtractorClient(canned=canned)
    else:
        client = AutoExtractorClient(
            model=model,
            small_model=resolved_small_model,
            large_model=resolved_large_model,
            large_input_chars=resolved_large_input_chars,
        )

    claims = extract_source(cfg, source_id=source_id, client=client,
                             density=resolved_density, rubric=resolved_rubric)
    click.echo(f"extracted {len(claims)} claim(s) for {source_id}")
    for c in claims:
        click.echo(f"  - {c.id}: {c.statement}")


@cli.command(name="lint")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON instead of text.")
@click.option("--write-conflicts", is_flag=True,
              help="Write ~/second-brain/conflicts.md from the lint report.")
def _lint(as_json: bool, write_conflicts: bool) -> None:
    """Run all lint rules over ~/second-brain. Exit 0 = no errors; 1 = errors present."""
    import json as _json

    from second_brain.lint.conflicts_md import render_conflicts_md
    from second_brain.lint.runner import run_lint

    cfg = Config.load()
    report = run_lint(cfg)

    if write_conflicts:
        md = render_conflicts_md(cfg, report)
        (cfg.home / "conflicts.md").write_text(md, encoding="utf-8")

    if as_json:
        click.echo(_json.dumps(report.to_dict(), indent=2))
    else:
        if not report.issues:
            click.echo("lint: ok (no issues)")
        else:
            for i in report.issues:
                click.echo(f"[{i.severity.value.upper():7}] {i.rule:26} {i.subject_id:40} {i.message}")
            c = report.counts_by_severity
            click.echo(f"summary: {c['error']} error, {c['warning']} warning, {c['info']} info")

    if not report.ok:
        raise click.exceptions.Exit(1)


@cli.group(name="habits")
def _habits() -> None:
    """Inspect and manage habits.yaml."""


@_habits.command(name="init")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite an existing habits.yaml.")
def _habits_init(force: bool) -> None:
    cfg = Config.load()
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    path = habits_path(cfg)
    if path.exists() and not force:
        raise click.ClickException(f"{path} already exists; use --force to overwrite")
    save_habits(cfg, Habits.default())
    click.echo(f"wrote {path}")


@_habits.command(name="show")
def _habits_show() -> None:
    cfg = Config.load()
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    buf = StringIO()
    yaml.dump(load_habits(cfg).model_dump(mode="python"), buf)
    click.echo(buf.getvalue())


@_habits.command(name="validate")
def _habits_validate() -> None:
    cfg = Config.load()
    errs = validate_habits_file(habits_path(cfg))
    if not errs:
        click.echo("ok")
        return
    for e in errs:
        click.echo(e, err=True)
    raise click.ClickException("habits.yaml invalid")


@cli.group(name="analytics")
def _analytics() -> None:
    """Analytics layer commands."""


@_analytics.command(name="rebuild")
def _analytics_rebuild() -> None:
    """Rebuild .sb/analytics.duckdb from graph + filesystem."""
    from second_brain.analytics.builder import AnalyticsBuilder

    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    click.echo(f"ok: {cfg.analytics_path}")


@_habits.command(name="learn")
@click.option("--window-days", type=int, default=60,
              help="Rolling window for scanning log.md.")
@click.option("--threshold", type=int, default=3,
              help="Minimum override count to emit a proposal.")
def _habits_learn(window_days: int, threshold: int) -> None:
    """Scan log.md for repeated user overrides; emit proposal markdown."""
    from second_brain.habits.learning import detect_overrides, write_proposal

    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=window_days, threshold=threshold)
    if not proposals:
        click.echo("no proposals")
        return
    click.echo(f"{len(proposals)} proposal(s):")
    for p in proposals:
        path = write_proposal(p, cfg)
        click.echo(
            f"  - {path.relative_to(cfg.home)}  "
            f"({p.op} -> {p.proposed_value}, n={p.count})"
        )


@cli.command(name="inject")
@click.option("--prompt", default=None, help="Prompt text.")
@click.option("--prompt-stdin", "prompt_stdin", is_flag=True, default=False,
              help="Read the prompt from stdin (preferred for hook usage).")
@click.option("--k", default=None, type=int,
              help="Override habits.injection.k for this call.")
@click.option("--max-tokens", default=None, type=int,
              help="Override habits.injection.max_tokens for this call.")
@click.option("--scope", default=None,
              type=click.Choice(["claims", "sources", "both"]),
              help="Override retrieval scope (default: claims).")
@click.option("--json", "as_json", is_flag=True, default=False)
def _inject(prompt: str | None, prompt_stdin: bool,
            k: int | None, max_tokens: int | None,
            scope: str | None, as_json: bool) -> None:
    """Emit a BM25 prefix block for the prompt (UserPromptSubmit hook payload)."""
    import json as _json
    import sys

    from second_brain.habits.loader import load_habits
    from second_brain.inject.runner import build_injection

    if prompt_stdin:
        prompt_value = sys.stdin.read()
    elif prompt is not None:
        prompt_value = prompt
    else:
        raise click.ClickException("either --prompt or --prompt-stdin is required")

    cfg = Config.load()
    if not cfg.fts_path.exists():
        # Graceful: no index yet → no injection, exit 0.
        if as_json:
            click.echo(_json.dumps({"block": "", "hit_ids": [], "skipped_reason": "no_index"}))
        return

    habits = load_habits(cfg)
    # Per-call overrides land as an Habits patch so skip_patterns / enabled still apply.
    patches: dict[str, object] = {}
    if k is not None or max_tokens is not None:
        inj = habits.injection
        inj_patch: dict[str, object] = {}
        if k is not None:
            inj_patch["k"] = k
        if max_tokens is not None:
            inj_patch["max_tokens"] = max_tokens
        patches["injection"] = inj.model_copy(update=inj_patch)
    if patches:
        habits = habits.model_copy(update=patches)

    result = build_injection(cfg, habits, prompt_value.strip())

    if as_json:
        click.echo(_json.dumps({
            "block": result.block,
            "hit_ids": result.hit_ids,
            "skipped_reason": result.skipped_reason,
        }))
        return

    if result.block:
        click.echo(result.block)


@cli.command(name="compile-center")
def _compile_center() -> None:
    """Compile paper cards from current sources and claims."""
    cfg = Config.load()
    report = compile_center(cfg)
    click.echo(
        f"compile-center: created={report.created} updated={report.updated} unchanged={report.unchanged}"
    )


@cli.command(name="record-project")
@click.argument("title")
@click.option("--question", default="")
@click.option("--objective", default="")
@click.option("--keyword", "keywords", multiple=True)
@click.option("--paper-id", "paper_ids", multiple=True)
@click.option("--claim-id", "claim_ids", multiple=True)
@click.option("--project-id", default=None)
@click.option("--inactive", is_flag=True, default=False)
def _record_project(
    title: str,
    question: str,
    objective: str,
    keywords: tuple[str, ...],
    paper_ids: tuple[str, ...],
    claim_ids: tuple[str, ...],
    project_id: str | None,
    inactive: bool,
) -> None:
    cfg = Config.load()
    project = record_project(
        cfg,
        title=title,
        question=question,
        objective=objective,
        keywords=list(keywords),
        paper_ids=list(paper_ids),
        claim_ids=list(claim_ids),
        project_id=project_id,
        active=not inactive,
    )
    click.echo(project.id)


@cli.command(name="record-experiment")
@click.argument("title")
@click.option("--project-id", "project_ids", multiple=True)
@click.option("--paper-id", "paper_ids", multiple=True)
@click.option("--claim-id", "claim_ids", multiple=True)
@click.option("--hypothesis", default="")
@click.option("--result", "result_summary", default="")
@click.option("--decision", default="")
@click.option("--run-id", default="")
def _record_experiment(
    title: str,
    project_ids: tuple[str, ...],
    paper_ids: tuple[str, ...],
    claim_ids: tuple[str, ...],
    hypothesis: str,
    result_summary: str,
    decision: str,
    run_id: str,
) -> None:
    cfg = Config.load()
    experiment = record_experiment(
        cfg,
        title=title,
        project_ids=list(project_ids),
        paper_ids=list(paper_ids),
        claim_ids=list(claim_ids),
        hypothesis=hypothesis,
        result_summary=result_summary,
        decision=decision,
        run_id=run_id,
    )
    click.echo(experiment.id)


@cli.command(name="record-synthesis")
@click.argument("title")
@click.option("--project-id", "project_ids", multiple=True)
@click.option("--paper-id", "paper_ids", multiple=True)
@click.option("--claim-id", "claim_ids", multiple=True)
@click.option("--experiment-id", "experiment_ids", multiple=True)
@click.option("--question", default="")
@click.option("--scope", default="")
@click.option("--decision-state", default="")
@click.option("--summary", default="")
def _record_synthesis(
    title: str,
    project_ids: tuple[str, ...],
    paper_ids: tuple[str, ...],
    claim_ids: tuple[str, ...],
    experiment_ids: tuple[str, ...],
    question: str,
    scope: str,
    decision_state: str,
    summary: str,
) -> None:
    cfg = Config.load()
    synthesis = record_synthesis(
        cfg,
        title=title,
        project_ids=list(project_ids),
        paper_ids=list(paper_ids),
        claim_ids=list(claim_ids),
        experiment_ids=list(experiment_ids),
        question=question,
        scope=scope,
        decision_state=decision_state,
        summary=summary,
    )
    click.echo(synthesis.id)


@cli.command(name="export-obsidian")
def _export_obsidian() -> None:
    """Export a graph-friendly Obsidian projection of center memory."""
    cfg = Config.load()
    target = export_obsidian_view(cfg)
    click.echo(str(target))


@cli.command(name="reconcile")
@click.option("--limit", default=10, type=int,
              help="Max debates to process this run.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Propose without writing resolutions.")
@click.option("--model", default=None,
              help="Force a specific live model, e.g. mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit.")
@click.option("--small-model", default=None,
              help="Local/default model for smaller contradiction packets.")
@click.option("--large-model", default=None,
              help="Remote/deep model for larger contradiction packets.")
@click.option("--large-input-chars", default=None, type=int,
              help="Switch to the large model when the reconciliation packet exceeds this character count.")
@click.option("--live/--fake", default=None,
              help="Force a real LLM call (--live) or fake client (--fake). "
                   "Default: fake if no live provider is available or SB_FAKE_RESOLUTION is set.")
def _reconcile(
    limit: int,
    dry_run: bool,
    model: str | None,
    small_model: str | None,
    large_model: str | None,
    large_input_chars: int | None,
    live: bool | None,
) -> None:
    """Resolve open contradictions with a live LLM or the fake client."""
    import json as _json
    import os

    from second_brain.habits.loader import load_habits
    from second_brain.reconcile.client import (
        DEFAULT_LARGE_INPUT_CHARS,
        DEFAULT_LARGE_MODEL,
        DEFAULT_SMALL_MODEL,
        AutoReconcilerClient,
        FakeReconcilerClient,
    )
    from second_brain.reconcile.worker import run_reconcile

    cfg = Config.load()
    habits = load_habits(cfg)

    fake_payload = os.environ.get("SB_FAKE_RESOLUTION")
    resolved_small_model = small_model or DEFAULT_SMALL_MODEL
    resolved_large_model = large_model or DEFAULT_LARGE_MODEL
    resolved_large_input_chars = large_input_chars or DEFAULT_LARGE_INPUT_CHARS
    candidate_models = [m for m in [model, resolved_small_model, resolved_large_model] if m]
    if live is True:
        _require_live_provider(*candidate_models)
    use_fake = (live is False) or bool(fake_payload) or (
        live is not True and not _has_live_provider(*candidate_models)
    )
    if use_fake:
        canned = _json.loads(fake_payload) if fake_payload else {
            "resolution_md": "(fake-canned) scope difference",
            "applies_where": "scope",
            "primary_claim_id": "clm_unknown",
        }
        client = FakeReconcilerClient(canned=canned)
    else:
        client = AutoReconcilerClient(
            model=model,
            small_model=resolved_small_model,
            large_model=resolved_large_model,
            large_input_chars=resolved_large_input_chars,
        )

    report = run_reconcile(cfg, habits, client=client, limit=limit, dry_run=dry_run)
    click.echo(
        f"resolved={report.resolved} proposed={report.proposed} skipped={report.skipped}"
    )


@cli.command(name="maintain")
@click.option("--json", "as_json", is_flag=True, help="Emit report as JSON on stdout.")
@click.option("--digest", "with_digest", is_flag=True, help="Also build today's digest after maintenance.")
def _maintain(as_json: bool, with_digest: bool) -> None:
    """Run nightly maintenance: lint, contradiction scan, compact, stale-abstract detect."""
    import dataclasses
    import json as _json

    from second_brain.maintain.runner import MaintainRunner

    cfg = Config.load()
    report = MaintainRunner(cfg).run(build_digest=with_digest)

    if as_json:
        click.echo(_json.dumps(dataclasses.asdict(report), indent=2))
        return

    click.echo("== sb maintain ==")
    click.echo(f"lint: {dict(report.lint_counts)}")
    click.echo(f"open contradictions: {report.open_contradictions}")
    click.echo(f"stale abstracts: {len(report.stale_abstracts)}")
    click.echo(
        f"compact fts: {report.fts_bytes_before}B -> {report.fts_bytes_after}B"
    )
    click.echo(
        f"compact duckdb: {report.duck_bytes_before}B -> {report.duck_bytes_after}B"
    )
    if with_digest:
        if report.digest_path:
            click.echo(f"digest: {report.digest_entries} entries -> {report.digest_path}")
        else:
            click.echo("digest: none emitted")


@cli.command(name="stats")
@click.option("--json", "as_json", is_flag=True, help="Emit stats + health as JSON.")
def _stats(as_json: bool) -> None:
    """KB metrics + 0-100 health score."""
    import dataclasses
    import json as _json

    from second_brain.stats.collector import collect_stats
    from second_brain.stats.health import compute_health

    cfg = Config.load()
    stats = collect_stats(cfg)
    health = compute_health(stats)

    if as_json:
        click.echo(
            _json.dumps(
                {
                    "stats": dataclasses.asdict(stats),
                    "health": dataclasses.asdict(health),
                },
                indent=2,
            )
        )
        return

    click.echo("== sb stats ==")
    click.echo(f"sources: {stats.source_count}")
    click.echo(f"claims:  {stats.claim_count}")
    click.echo(f"inbox pending: {stats.inbox_pending}")
    click.echo(f"zero-claim sources: {stats.zero_claim_sources}")
    click.echo(f"orphan claims: {stats.orphan_claims}")
    click.echo(
        f"contradictions: open={stats.open_contradictions} "
        f"resolved={stats.resolved_contradictions}"
    )
    click.echo(f"health: {health.score}/100  {dict(health.breakdown)}")


@cli.group(name="eval", invoke_without_command=True)
@click.option(
    "--suite",
    type=click.Choice(["retrieval", "graph", "ingest", "corpus"]),
    default=None,
    help="Run a single suite (omit to run all).",
)
@click.option(
    "--fixtures-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False,
    default=None,
    help="Directory containing per-suite fixture sub-dirs.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit reports as JSON.")
@click.option(
    "--mode",
    type=click.Choice(["bm25", "hybrid", "compare"]),
    default="bm25",
    help="Retrieval mode for the retrieval suite (bm25 | hybrid | compare).",
)
@click.pass_context
def _eval(
    ctx: click.Context,
    suite: str | None,
    fixtures_dir: Path | None,
    as_json: bool,
    mode: str,
) -> None:
    """Run eval suites against seed fixtures."""
    # When a subcommand (e.g. `sb eval digest`) is used, stash flags for it and
    # return so Click dispatches to the subcommand callback.
    if ctx.invoked_subcommand is not None:
        ctx.obj = {"as_json": as_json}
        return
    if fixtures_dir is None:
        raise click.UsageError("--fixtures-dir is required when no subcommand is given")
    import dataclasses
    import json as _json

    from second_brain.eval.runner import EvalRunner
    from second_brain.eval.suites.corpus import CorpusSuite
    from second_brain.eval.suites.graph import GraphSuite
    from second_brain.eval.suites.ingest import IngestSuite
    from second_brain.eval.suites.retrieval import RetrievalSuite

    cfg = Config.load()
    suites = {
        "retrieval": RetrievalSuite(mode=mode),  # type: ignore[arg-type]
        "graph": GraphSuite(),
        "ingest": IngestSuite(),
        "corpus": CorpusSuite(),
    }
    names = [suite] if suite else list(suites.keys())
    runner = EvalRunner(cfg, suites)

    reports = []
    for name in names:
        sub_dir = fixtures_dir / name
        if not sub_dir.exists():
            click.echo(f"skip {name}: fixtures_dir/{name} missing")
            continue
        reports.append(runner.run(name, sub_dir))

    if as_json:
        click.echo(
            _json.dumps(
                [dataclasses.asdict(r) for r in reports], indent=2, default=str
            )
        )
    else:
        for r in reports:
            mark = "PASS" if r.passed else "FAIL"
            click.echo(
                f"[{mark}] {r.suite}: {int(r.pass_rate * 100)}% "
                f"({len(r.cases)} cases)"
            )
            for c in r.cases:
                click.echo(
                    f"  {'ok' if c.passed else '--'} {c.name}: {c.details}"
                )

    if any(not r.passed for r in reports):
        raise click.ClickException("one or more suites failed")


@_eval.command(name="digest")
@click.option(
    "--pass",
    "pass_filter",
    type=click.Choice([
        "reconciliation",
        "wiki_bridge",
        "taxonomy_drift",
        "stale_review",
        "edge_audit",
    ]),
    default=None,
    help="Run a single digest pass (omit to run all five).",
)
@click.option("--json", "as_json_local", is_flag=True, help="Emit outcomes as JSON.")
@click.pass_context
def _eval_digest(ctx: click.Context, pass_filter: str | None, as_json_local: bool) -> None:
    """Run the digest per-pass golden-comparison suite."""
    import json as _json

    from second_brain.eval.suites.digest import run_digest_suite

    parent_obj = ctx.obj or {}
    as_json = as_json_local or bool(parent_obj.get("as_json"))

    outcomes = run_digest_suite(pass_filter=pass_filter)

    if as_json:
        click.echo(
            _json.dumps(
                [
                    {
                        "pass": o.pass_name,
                        "generated": o.generated,
                        "expected": o.expected,
                        "true_positives": o.true_positives,
                        "precision": round(o.precision, 4),
                        "recall": round(o.recall, 4),
                        "passed": o.passed,
                    }
                    for o in outcomes
                ],
                indent=2,
            )
        )
    else:
        click.echo("== sb eval digest ==")
        click.echo(
            f"{'pass':<18} {'gen':>4} {'exp':>4} {'tp':>4} "
            f"{'prec':>6} {'rec':>6} status"
        )
        for o in outcomes:
            mark = "PASS" if o.passed else "FAIL"
            click.echo(
                f"{o.pass_name:<18} {o.generated:>4} {o.expected:>4} "
                f"{o.true_positives:>4} {o.precision:>6.2f} {o.recall:>6.2f} {mark}"
            )
    if any(not o.passed for o in outcomes):
        raise click.ClickException("one or more digest passes failed")


@cli.command(name="init")
@click.option("--defaults", "non_interactive", is_flag=True, default=False,
              help="Skip the interactive interview; accept every default.")
@click.option("--reconfigure", is_flag=True, default=False,
              help="Regenerate habits.yaml only (preserves existing directories).")
def _init(non_interactive: bool, reconfigure: bool) -> None:
    """Interactive setup: scaffold layout + capture habits + print wiring."""
    from second_brain.init_wizard.interview import run_interview
    from second_brain.init_wizard.scaffold import create_tree
    from second_brain.init_wizard.wiring import render_wiring_instructions

    cfg = Config.load()
    create_tree(cfg)

    hpath = habits_path(cfg)
    if hpath.exists() and not reconfigure:
        raise click.ClickException(
            f"habits.yaml already exists at {hpath}. "
            "Re-run with --reconfigure to rewrite it."
        )

    answers = run_interview(interactive=not non_interactive)
    save_habits(cfg, answers.to_habits())
    click.echo(f"wrote {hpath}")

    click.echo("")
    click.echo(render_wiring_instructions(home=str(cfg.home)))


# ---- digest commands ------------------------------------------------------


@cli.group(name="digest")
def _digest() -> None:
    """Daily digest commands."""


def _parse_date(value: str | None):
    import datetime as _dt

    if value is None:
        return _dt.date.today()
    return _dt.date.fromisoformat(value)


@_digest.command(name="build")
@click.option("--date", "date_str", default=None, help="Date (YYYY-MM-DD) — defaults to today.")
def _digest_build(date_str: str | None) -> None:
    """Build today's digest and write markdown + actions.jsonl."""
    from second_brain.digest.builder import DigestBuilder
    from second_brain.habits.loader import load_habits

    cfg = Config.load()
    cfg.digests_dir.mkdir(parents=True, exist_ok=True)
    habits = load_habits(cfg)
    today = _parse_date(date_str)

    result = DigestBuilder(cfg, habits=habits).build(today=today)
    if not result.entries:
        click.echo("no digest emitted (no entries)")
        return

    md_path = cfg.digests_dir / f"{today.isoformat()}.md"
    jsonl_path = cfg.digests_dir / f"{today.isoformat()}.actions.jsonl"
    md_path.write_text(result.markdown, encoding="utf-8")
    jsonl_path.write_text(result.actions_jsonl, encoding="utf-8")
    click.echo(f"wrote {md_path} ({len(result.entries)} entries)")


@_digest.command(name="apply")
@click.argument("ids", nargs=-1)
@click.option("--all", "apply_all", is_flag=True, help="Apply all entries in the digest.")
@click.option("--date", "date_str", default=None, help="Digest date (default: today).")
def _digest_apply(ids: tuple[str, ...], apply_all: bool, date_str: str | None) -> None:
    """Apply digest entries by id, or all with --all."""
    from second_brain.digest.applier import DigestApplier

    if not apply_all and not ids:
        raise click.UsageError("provide entry ids or --all")

    cfg = Config.load()
    d = _parse_date(date_str)
    selector: list[str] | str = "all" if apply_all else list(ids)
    result = DigestApplier(cfg).apply(digest_date=d, entry_ids=selector)
    click.echo(
        f"applied={len(result.applied)} skipped={len(result.skipped)} "
        f"failed={len(result.failed)}"
    )
    for fid, err in result.failed:
        click.echo(f"  FAIL {fid}: {err}", err=True)


@_digest.command(name="skip")
@click.argument("entry_id")
@click.option("--date", "date_str", default=None, help="Digest date (default: today).")
@click.option("--ttl-days", default=None, type=int, help="Override habits.digest.skip_ttl_days.")
def _digest_skip(entry_id: str, date_str: str | None, ttl_days: int | None) -> None:
    """Record a skip signature so the entry doesn't reappear until TTL expires."""
    from second_brain.digest.skip import SkipRegistry
    from second_brain.habits.loader import load_habits

    cfg = Config.load()
    habits = load_habits(cfg)
    ttl = ttl_days if ttl_days is not None else habits.digest.skip_ttl_days
    d = _parse_date(date_str)

    reg = SkipRegistry(cfg)
    ok = reg.skip_by_id(digest_date=d, entry_id=entry_id, ttl_days=ttl)
    if not ok:
        raise click.ClickException(f"entry {entry_id} not found in digest {d.isoformat()}")
    click.echo(f"skipped {entry_id} for {ttl} days")


@_digest.command(name="read")
@click.option("--mark", "mark_date", required=True, help="Date of the digest to mark read (YYYY-MM-DD).")
def _digest_read(mark_date: str) -> None:
    """Mark a digest as read (used by the health-score digest_unread_penalty)."""
    cfg = Config.load()
    cfg.digests_dir.mkdir(parents=True, exist_ok=True)
    marks = cfg.digests_dir / ".read_marks"
    existing = marks.read_text(encoding="utf-8").splitlines() if marks.exists() else []
    if mark_date not in existing:
        existing.append(mark_date)
    marks.write_text("\n".join(sorted(set(existing))) + "\n", encoding="utf-8")
    click.echo(f"marked {mark_date} read")


@_digest.command(name="ls")
@click.option("--limit", default=10, type=int, help="Number of digests to list (newest first).")
def _digest_ls(limit: int) -> None:
    """List recent digests with entry counts."""
    cfg = Config.load()
    if not cfg.digests_dir.exists():
        click.echo("no digests")
        return
    mds = sorted(cfg.digests_dir.glob("*.md"), reverse=True)[:limit]
    if not mds:
        click.echo("no digests")
        return
    marks_file = cfg.digests_dir / ".read_marks"
    read_set = (
        set(marks_file.read_text(encoding="utf-8").splitlines()) if marks_file.exists() else set()
    )
    for md in mds:
        date_stem = md.stem
        sidecar = md.with_suffix(".actions.jsonl")
        count = 0
        if sidecar.exists():
            count = len(
                [line for line in sidecar.read_text(encoding="utf-8").splitlines() if line.strip()]
            )
        read_mark = "READ " if date_stem in read_set else "     "
        click.echo(f"{read_mark}{date_stem}  entries={count}")
