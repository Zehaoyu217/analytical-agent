"""Habit-learning detector.

Parses log.md USER_OVERRIDE entries within a rolling window, groups them by
``(op, proposed_value)``, and emits a ``HabitProposal`` for any group whose
count meets a threshold. Proposals are rendered as markdown under
``cfg.proposals_dir``.

Log line format (§10.4)::

    - 2026-04-17T14:25:03 [USER_OVERRIDE] ingest.taxonomy src_foo → papers/ml/transformers
      prior: papers/ml
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config

_LINE_RE = re.compile(
    r"^- (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r" \[USER_OVERRIDE\] (?P<op>\S+) (?P<subject>\S+) → (?P<value>.+)$"
)
_PRIOR_RE = re.compile(r"^\s+prior:\s*(?P<prior>.+)$")


@dataclass(frozen=True)
class HabitProposal:
    """A single habit proposal aggregated from repeated USER_OVERRIDE entries."""

    op: str
    proposed_value: str
    prior_value: str | None
    count: int
    sample_subjects: list[str] = field(default_factory=list)


def detect_overrides(
    cfg: Config, *, window_days: int, threshold: int
) -> list[HabitProposal]:
    """Scan ``cfg.log_path`` for USER_OVERRIDE entries and return proposals.

    Only entries within the rolling ``window_days`` participate. Groups with
    fewer than ``threshold`` entries are omitted.
    """
    log_path = cfg.log_path
    if not log_path.exists():
        return []
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    # group key -> list of (subject, prior_or_none)
    groups: dict[tuple[str, str], list[tuple[str, str | None]]] = defaultdict(list)
    last_key: tuple[str, str] | None = None  # (op, value) for prior-line attachment

    for line in log_path.read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if m:
            ts = datetime.fromisoformat(m["ts"]).replace(tzinfo=UTC)
            if ts < cutoff:
                last_key = None
                continue
            op = m["op"]
            subject = m["subject"]
            value = m["value"].strip()
            groups[(op, value)].append((subject, None))
            last_key = (op, value)
            continue
        pm = _PRIOR_RE.match(line)
        if pm and last_key is not None:
            # attach prior to the most recent entry in its group
            tail_subject, _ = groups[last_key][-1]
            groups[last_key][-1] = (tail_subject, pm["prior"].strip())

    proposals: list[HabitProposal] = []
    for (op, value), entries in groups.items():
        if len(entries) < threshold:
            continue
        priors = Counter(p for _subj, p in entries if p is not None)
        prior = priors.most_common(1)[0][0] if priors else None
        proposals.append(
            HabitProposal(
                op=op,
                proposed_value=value,
                prior_value=prior,
                count=len(entries),
                sample_subjects=[subj for subj, _ in entries[:5]],
            )
        )
    return sorted(proposals, key=lambda p: (p.op, p.proposed_value))


def write_proposal(proposal: HabitProposal, cfg: Config) -> Path:
    """Render ``proposal`` as markdown under ``cfg.proposals_dir`` and return the path."""
    cfg.proposals_dir.mkdir(parents=True, exist_ok=True)
    fname = (
        f"habits-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        f"-{_slug(proposal.op)}-{_slug(proposal.proposed_value)}.md"
    )
    path = cfg.proposals_dir / fname
    path.write_text(_render(proposal), encoding="utf-8")
    return path


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "x"


def _render(p: HabitProposal) -> str:
    samples = "\n".join(f"  - `{s}`" for s in p.sample_subjects)
    prior = p.prior_value or "(unset)"
    return (
        f"# Habit proposal: {p.op}\n\n"
        f"Observed {p.count} user overrides in the rolling window.\n\n"
        f"- **Operation:** `{p.op}`\n"
        f"- **Prior value:** `{prior}`\n"
        f"- **Proposed value:** `{p.proposed_value}`\n\n"
        f"## Sample subjects\n{samples}\n\n"
        f"## Apply\n\n"
        f"```bash\nsb habits apply {p.op} {p.proposed_value}\n```\n\n"
        f"Reject with `--reject` to silence this proposal for 30 days.\n"
    )
