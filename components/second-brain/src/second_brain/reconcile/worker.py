from __future__ import annotations

from dataclasses import dataclass

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.habits import Habits
from second_brain.log import EventKind, append_event
from second_brain.reconcile.client import ReconcileRequest, ReconcilerClient
from second_brain.reconcile.finder import find_open_debates
from second_brain.reconcile.writer import write_resolution


@dataclass(frozen=True)
class ReconcileReport:
    resolved: int
    proposed: int
    skipped: int


def _claim_body(path: str) -> str:
    from pathlib import Path
    _meta, body = load_document(Path(path))
    return body


def run_reconcile(
    cfg: Config,
    habits: Habits,
    *,
    client: ReconcilerClient,
    limit: int,
    dry_run: bool = False,
) -> ReconcileReport:
    debates = find_open_debates(cfg, habits)
    if limit <= 0:
        return ReconcileReport(resolved=0, proposed=0, skipped=len(debates))

    resolved = 0
    proposed = 0
    skipped = 0
    for debate in debates[:limit]:
        try:
            req = ReconcileRequest(
                claim_a_id=debate.left_id,
                claim_b_id=debate.right_id,
                claim_a_body=_claim_body(debate.left_path),
                claim_b_body=_claim_body(debate.right_path),
                supports_a="",  # v1: supports bodies deferred; see spec §16.
                supports_b="",
            )
            resp = client.reconcile(req)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            append_event(
                kind=EventKind.ERROR, op="reconcile.call_failed",
                subject=f"{debate.left_id}__vs__{debate.right_id}",
                value=str(exc), home=cfg.home,
            )
            continue

        if dry_run:
            proposed += 1
            append_event(
                kind=EventKind.SUGGEST, op="reconcile.proposed",
                subject=f"{debate.left_id}__vs__{debate.right_id}",
                value=resp.primary_claim_id,
                reason={"applies_where": resp.applies_where},
                home=cfg.home,
            )
            continue

        rel = write_resolution(cfg, debate, resp)
        resolved += 1
        append_event(
            kind=EventKind.AUTO if habits.autonomy.for_op("reconciliation.resolution") == "auto"
            else EventKind.USER_OVERRIDE,
            op="reconcile.resolved",
            subject=f"{debate.left_id}__vs__{debate.right_id}",
            value=rel,
            reason={"applies_where": resp.applies_where, "primary": resp.primary_claim_id},
            home=cfg.home,
        )

    return ReconcileReport(resolved=resolved, proposed=proposed, skipped=skipped)
