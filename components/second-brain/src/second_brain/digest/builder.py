"""DigestBuilder — orchestrates the 5 passes, rewrites ids, filters skips.

The Builder is pure orchestration: it does not write any files. The caller
(e.g. the CLI or ``sb maintain --digest``) writes the returned
``BuildResult.markdown`` and ``actions_jsonl`` to disk.

Pass ordering is fixed and deterministic:

    1. reconciliation  (r)
    2. wiki_bridge     (w)
    3. taxonomy_drift  (t)
    4. stale_review    (s)
    5. edge_audit      (e)

Within each pass, entries are sorted by a primary key (claim id / target id /
taxonomy / wiki path / src_id) so ids are stable across runs. The Builder then
rewrites empty ``DigestEntry.id`` values to ``<prefix><NN>`` with zero-padded
counters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from second_brain.config import Config
from second_brain.digest.passes.base import Pass
from second_brain.digest.passes.edge_audit import EdgeAuditPass
from second_brain.digest.passes.reconciliation import ReconciliationPass
from second_brain.digest.passes.stale_review import StaleReviewPass
from second_brain.digest.passes.taxonomy_drift import TaxonomyDriftPass
from second_brain.digest.passes.wiki_bridge import WikiBridgePass
from second_brain.digest.pending import read_pending, truncate_pending
from second_brain.digest.schema import DigestEntry
from second_brain.digest.skip import SkipRegistry
from second_brain.digest.writer import render_actions_jsonl, render_markdown
from second_brain.habits import Habits

# Ordered (habits_key, factory) — habits_key matches DigestHabits.passes.
_DEFAULT_PASS_SPECS: tuple[tuple[str, type[Pass]], ...] = (
    ("reconciliation", ReconciliationPass),
    ("wiki_bridge", WikiBridgePass),
    ("taxonomy_drift", TaxonomyDriftPass),
    ("stale_review", StaleReviewPass),
    ("edge_audit", EdgeAuditPass),
)


def _entry_sort_key(entry: DigestEntry) -> tuple[str, str]:
    action = entry.action
    for key in ("claim_id", "left_id", "src_id", "target_id", "root", "wiki_path", "taxonomy"):
        v = action.get(key)
        if isinstance(v, str) and v:
            return (v, entry.line)
    cids = action.get("claim_ids")
    if isinstance(cids, list) and cids and isinstance(cids[0], str):
        return (cids[0], entry.line)
    return ("", entry.line)


@dataclass(frozen=True)
class BuildResult:
    entries: list[DigestEntry] = field(default_factory=list)
    actions_jsonl: str = ""
    markdown: str = ""


class DigestBuilder:
    """Runs enabled passes and assembles a deterministic, skip-filtered digest."""

    def __init__(
        self,
        cfg: Config,
        habits: Habits,
        *,
        client: Any | None = None,
        passes: list[Pass] | None = None,
    ) -> None:
        self.cfg = cfg
        self.habits = habits
        self.client = client
        self._passes = passes if passes is not None else self._default_passes()

    def _default_passes(self) -> list[Pass]:
        enabled = self.habits.digest.passes
        out: list[Pass] = []
        for key, factory in _DEFAULT_PASS_SPECS:
            if enabled.get(key, False):
                out.append(factory())
        return out

    def build(self, today: date) -> BuildResult:
        dh = self.habits.digest

        # Collect per-pass entries, rewrite ids, respecting disable flag
        # (only applies when default passes are used; custom lists bypass).
        collected: list[DigestEntry] = []
        skips = SkipRegistry(self.cfg)
        for pas in self._passes:
            # Honour habits for string-matched prefixes when using defaults.
            habits_key = _habits_key_for(pas.prefix)
            if habits_key and not dh.passes.get(habits_key, True):
                continue
            raw = list(pas.run(self.cfg, self.client))
            raw.sort(key=_entry_sort_key)
            rewritten: list[DigestEntry] = []
            counter = 1
            for entry in raw:
                if skips.is_skipped(entry, today=today):
                    continue
                rewritten.append(
                    DigestEntry(
                        id=f"{pas.prefix}{counter:02d}",
                        section=entry.section,
                        line=entry.line,
                        action=entry.action,
                    )
                )
                counter += 1
            collected.extend(rewritten)

        # Merge externally-proposed entries (e.g. from the agent bridge's
        # sb_digest_propose tool). Read non-destructively so we can abort the
        # build below without dropping proposals, then truncate pending.jsonl
        # only on successful emit.
        proposals = read_pending(self.cfg)
        collected = collected + proposals

        if len(collected) < dh.min_entries_to_emit:
            # Bail before truncating: proposals stay in pending.jsonl and roll
            # into the next build instead of being silently dropped.
            return BuildResult(entries=[], actions_jsonl="", markdown="")

        markdown = render_markdown(today, collected)
        jsonl = render_actions_jsonl(collected)
        truncate_pending(self.cfg)
        return BuildResult(entries=collected, actions_jsonl=jsonl, markdown=markdown)


_PREFIX_TO_HABITS_KEY = {
    "r": "reconciliation",
    "w": "wiki_bridge",
    "t": "taxonomy_drift",
    "s": "stale_review",
    "e": "edge_audit",
}


def _habits_key_for(prefix: str) -> str | None:
    return _PREFIX_TO_HABITS_KEY.get(prefix)
