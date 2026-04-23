"""Stale-review digest pass.

Inputs:
    - Active claims whose claim markdown file has a filesystem mtime older than
      ``STALE_DAYS`` and whose abstract is non-empty. Grouped by the taxonomy
      prefix derived from their first supporting source's ``habit_taxonomy``.

Output:
    - One ``re_abstract_batch`` entry per taxonomy prefix, batching up to
      ``BATCH_SIZE`` stale claim ids.

Pure Python — no Claude call.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from second_brain.config import Config
from second_brain.digest.passes.taxonomy_drift import _claim_taxonomy, _two_segment_prefix
from second_brain.digest.schema import DigestEntry
from second_brain.lint.snapshot import load_snapshot
from second_brain.schema.claim import ClaimStatus

STALE_DAYS = 120
BATCH_SIZE = 10


def _is_stale(path: Path, cutoff: datetime) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return mtime < cutoff


class StaleReviewPass:
    """Groups stale claims by taxonomy and proposes a batched re-abstract."""

    prefix = "s"
    section = "Stale review"

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        cutoff = datetime.now(UTC) - timedelta(days=STALE_DAYS)
        snap = load_snapshot(cfg)

        groups: dict[str, list[str]] = defaultdict(list)
        for cid, claim in snap.claims.items():
            if claim.status != ClaimStatus.ACTIVE:
                continue
            if not claim.abstract.strip():
                continue
            path = cfg.claims_dir / f"{cid}.md"
            if not _is_stale(path, cutoff):
                continue
            tax = _claim_taxonomy(cfg, cid, list(claim.supports))
            if tax is None:
                continue
            prefix = _two_segment_prefix(tax) + "/*"
            groups[prefix].append(cid)

        entries: list[DigestEntry] = []
        for prefix in sorted(groups):
            cids = sorted(groups[prefix])
            batch = cids[:BATCH_SIZE]
            if not batch:
                continue
            payload: dict[str, Any] = {
                "action": "re_abstract_batch",
                "claim_ids": batch,
                "taxonomy": prefix,
            }
            entries.append(
                DigestEntry(
                    id="",
                    section=self.section,
                    line=(
                        f"{len(batch)} claims under {prefix} untouched > {STALE_DAYS}d — "
                        "re-abstract batch?"
                    ),
                    action=payload,
                )
            )
        return entries
