from __future__ import annotations

from datetime import UTC, datetime

from slugify import slugify

from second_brain.config import Config
from second_brain.research.schema import (
    CenterKind,
    ExperimentFrontmatter,
    ProjectFrontmatter,
    SynthesisFrontmatter,
    center_dir_for_kind,
    dump_center_document,
    load_center_document,
)


def record_project(
    cfg: Config,
    *,
    title: str,
    question: str = "",
    objective: str = "",
    keywords: list[str] | None = None,
    paper_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
    project_id: str | None = None,
    active: bool = True,
) -> ProjectFrontmatter:
    pid = project_id or f"project_{slugify(title, lowercase=True, max_length=64) or 'project'}"
    meta = ProjectFrontmatter(
        id=pid,
        title=title,
        status="published",
        summary=question or objective,
        aliases=[],
        tags=["project"],
        confidence=1.0,
        project_ids=[],
        paper_ids=paper_ids or [],
        experiment_ids=[],
        synthesis_ids=[],
        claim_ids=claim_ids or [],
        source_ids=[],
        updated_at=datetime.now(tz=UTC),
        question=question,
        objective=objective,
        keywords=keywords or [],
        active=active,
    )
    body = "\n".join(
        [
            f"# {title}",
            "",
            "## Question",
            "",
            question or "_Add the active modeling question._",
            "",
            "## Objective",
            "",
            objective or "_Add project objective._",
            "",
            "## Notes",
            "",
            "",
        ]
    )
    _write_center_doc(cfg, CenterKind.PROJECT, meta, body)
    return meta


def record_experiment(
    cfg: Config,
    *,
    title: str,
    project_ids: list[str] | None = None,
    paper_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
    hypothesis: str = "",
    result_summary: str = "",
    decision: str = "",
    run_id: str = "",
    metric_summary: dict[str, float | int | str] | None = None,
    experiment_id: str | None = None,
) -> ExperimentFrontmatter:
    eid = experiment_id or f"exp_{slugify(title, lowercase=True, max_length=64) or 'experiment'}"
    meta = ExperimentFrontmatter(
        id=eid,
        title=title,
        status="published",
        summary=result_summary or hypothesis,
        aliases=[],
        tags=["experiment"],
        confidence=0.85,
        project_ids=project_ids or [],
        paper_ids=paper_ids or [],
        experiment_ids=[],
        synthesis_ids=[],
        claim_ids=claim_ids or [],
        source_ids=[],
        updated_at=datetime.now(tz=UTC),
        run_id=run_id,
        hypothesis=hypothesis,
        result_summary=result_summary,
        decision=decision,
        metric_summary=metric_summary or {},
    )
    metrics = "\n".join(f"- `{k}`: {v}" for k, v in (metric_summary or {}).items()) or "- none recorded"
    body = "\n".join(
        [
            f"# {title}",
            "",
            "## Hypothesis",
            "",
            hypothesis or "_Add the tested hypothesis._",
            "",
            "## Result",
            "",
            result_summary or "_Add the observed result._",
            "",
            "## Metrics",
            "",
            metrics,
            "",
            "## Decision",
            "",
            decision or "_Add the decision taken after this run._",
            "",
        ]
    )
    _write_center_doc(cfg, CenterKind.EXPERIMENT, meta, body)
    return meta


def record_synthesis(
    cfg: Config,
    *,
    title: str,
    project_ids: list[str] | None = None,
    paper_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
    experiment_ids: list[str] | None = None,
    question: str = "",
    scope: str = "",
    decision_state: str = "",
    summary: str = "",
    synthesis_id: str | None = None,
) -> SynthesisFrontmatter:
    sid = synthesis_id or f"syn_{slugify(title, lowercase=True, max_length=64) or 'synthesis'}"
    meta = SynthesisFrontmatter(
        id=sid,
        title=title,
        status="published",
        summary=summary or question,
        aliases=[],
        tags=["synthesis"],
        confidence=0.9,
        project_ids=project_ids or [],
        paper_ids=paper_ids or [],
        experiment_ids=experiment_ids or [],
        synthesis_ids=[],
        claim_ids=claim_ids or [],
        source_ids=[],
        updated_at=datetime.now(tz=UTC),
        question=question,
        scope=scope,
        decision_state=decision_state,
    )
    body = "\n".join(
        [
            f"# {title}",
            "",
            "## Question",
            "",
            question or "_Add the synthesis question._",
            "",
            "## Summary",
            "",
            summary or "_Add the current synthesis._",
            "",
            "## Decision State",
            "",
            decision_state or "_No decision recorded._",
            "",
        ]
    )
    _write_center_doc(cfg, CenterKind.SYNTHESIS, meta, body)
    return meta


def _write_center_doc(cfg: Config, kind: CenterKind, meta, body: str) -> None:
    root = center_dir_for_kind(cfg, kind)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{meta.id}.md"
    if path.exists():
        existing_meta, existing_body = load_center_document(path)
        merged_meta = meta.model_copy(
            update={
                "aliases": list(existing_meta.aliases),
                "tags": sorted(set(existing_meta.tags) | set(meta.tags)),
            }
        )
        dump_center_document(path, merged_meta, body or existing_body)
        return
    dump_center_document(path, meta, body)
