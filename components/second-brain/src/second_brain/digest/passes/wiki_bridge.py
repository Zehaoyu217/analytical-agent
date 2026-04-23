"""Wiki ↔ KB bridge digest pass.

Inputs:
    - Wiki findings from ``$SB_WIKI_DIR`` (e.g. the claude-code-agent wiki).
      A finding is any ``*.md`` file in the wiki directory that declares
      ``status: mature`` in its YAML frontmatter.
    - Stale KB claims whose frontmatter has not been modified in the last
      ``STALE_CLAIM_DAYS`` days (filesystem mtime).

Outputs:
    - ``promote_wiki_to_claim`` entries — one per mature wiki finding that is
      not already linked to a claim.
    - ``backlink_claim_to_wiki`` entries — one per stale claim that has a
      matching wiki finding (naive substring match on claim id in the wiki
      text).

When ``SB_WIKI_DIR`` is unset or missing, the pass returns ``[]`` so it never
crashes on a fresh KB. No Claude call — this is a pure heuristic pass.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry
from second_brain.lint.snapshot import load_snapshot
from second_brain.schema.claim import ClaimStatus

STALE_CLAIM_DAYS = 90
_WIKI_ENV = "SB_WIKI_DIR"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_STATUS_RE = re.compile(r"^status:\s*([A-Za-z_]+)\s*$", re.MULTILINE)
_TAXONOMY_RE = re.compile(r"^taxonomy:\s*([A-Za-z0-9_./\-]+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class _WikiFinding:
    path: Path
    taxonomy: str | None

    @property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8")


def _scan_wiki(wiki_dir: Path) -> list[_WikiFinding]:
    findings: list[_WikiFinding] = []
    for md in sorted(wiki_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            continue
        fm = m.group(1)
        status_match = _STATUS_RE.search(fm)
        if not status_match or status_match.group(1).lower() != "mature":
            continue
        tax_match = _TAXONOMY_RE.search(fm)
        taxonomy = tax_match.group(1) if tax_match else None
        findings.append(_WikiFinding(path=md, taxonomy=taxonomy))
    return findings


def _wiki_path_str(finding: _WikiFinding, wiki_dir: Path) -> str:
    try:
        return finding.path.relative_to(wiki_dir).as_posix()
    except ValueError:
        return finding.path.as_posix()


def _finding_mentions_claim(finding: _WikiFinding, claim_id: str) -> bool:
    return claim_id in finding.text


class WikiBridgePass:
    """Emits promote/backlink suggestions linking wiki findings to KB claims."""

    prefix = "w"
    section = "Wiki ↔ KB drift"

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        wiki_env = os.environ.get(_WIKI_ENV, "").strip()
        if not wiki_env:
            return []
        wiki_dir = Path(wiki_env).expanduser()
        if not wiki_dir.exists() or not wiki_dir.is_dir():
            return []

        findings = _scan_wiki(wiki_dir)
        snap = load_snapshot(cfg)

        entries: list[DigestEntry] = []

        # 1. Promote mature wiki findings that are not referenced by any claim.
        referenced: set[Path] = set()
        for finding in findings:
            for cid in snap.claims:
                if _finding_mentions_claim(finding, cid):
                    referenced.add(finding.path)
                    break

        for finding in findings:
            if finding.path in referenced:
                continue
            rel = _wiki_path_str(finding, wiki_dir)
            payload: dict[str, Any] = {
                "action": "promote_wiki_to_claim",
                "wiki_path": rel,
                "proposed_taxonomy": finding.taxonomy or "",
            }
            entries.append(
                DigestEntry(
                    id="",
                    section=self.section,
                    line=f"Promote wiki finding {rel} to a claim?",
                    action=payload,
                )
            )

        # 2. Backlink stale claims to any wiki finding that already names them.
        cutoff = datetime.now(UTC) - timedelta(days=STALE_CLAIM_DAYS)
        for cid, claim in sorted(snap.claims.items()):
            if claim.status != ClaimStatus.ACTIVE:
                continue
            path = cfg.claims_dir / f"{cid}.md"
            if not path.exists():
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if mtime > cutoff:
                continue
            for finding in findings:
                if not _finding_mentions_claim(finding, cid):
                    continue
                rel = _wiki_path_str(finding, wiki_dir)
                payload = {
                    "action": "backlink_claim_to_wiki",
                    "claim_id": cid,
                    "wiki_path": rel,
                }
                entries.append(
                    DigestEntry(
                        id="",
                        section=self.section,
                        line=f"Backlink {cid} to wiki {rel}?",
                        action=payload,
                    )
                )
                break  # one backlink per claim is enough per digest

        return entries
