"""Taxonomy-drift digest pass.

Pure Python heuristic — no Claude call.

Inputs:
    - Every active claim's effective taxonomy, derived from the ``habit_taxonomy``
      of the first source it supports.
    - Configured taxonomy roots from ``habits.taxonomy.roots``.

Output:
    - One ``add_taxonomy_root`` entry per taxonomy prefix that has ≥ ``CLUSTER_MIN``
      claims and does not match any configured root prefix. The suggested root is
      the 2-segment prefix (e.g. ``papers/security``) extracted from the
      offending taxonomies.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry
from second_brain.frontmatter import load_document
from second_brain.habits import Habits
from second_brain.lint.snapshot import load_snapshot
from second_brain.schema.claim import ClaimStatus

CLUSTER_MIN = 5


def _load_habits(cfg: Config) -> Habits:
    """Load habits from ``.sb/habits.yaml`` if present, else return defaults."""
    path = cfg.sb_dir / "habits.yaml"
    if not path.exists():
        return Habits.default()
    try:
        # Habits is a strict pydantic model; round-trip via a minimal YAML read.
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        raw = yaml.load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return Habits.default()
        return Habits.model_validate(raw)
    except Exception:
        return Habits.default()


def _matches_any_root(taxonomy: str, roots: list[str]) -> bool:
    """True when ``taxonomy`` falls under one of ``roots``.

    Roots are treated as prefix patterns — ``papers/ml`` matches ``papers/ml``
    and ``papers/ml/transformers`` but not ``papers/security``.
    """
    for root in roots:
        if taxonomy == root or taxonomy.startswith(root + "/"):
            return True
    return False


def _claim_taxonomy(cfg: Config, claim_id: str, claim_supports: list[str]) -> str | None:
    """Derive a claim's taxonomy from the first supporting source's habit_taxonomy."""
    for target in claim_supports:
        sid = target.split("#", 1)[0]
        if not sid.startswith("src_"):
            continue
        source_md = cfg.sources_dir / sid / "_source.md"
        if not source_md.exists():
            continue
        try:
            meta, _ = load_document(Path(source_md))
        except Exception:
            continue
        tax = meta.get("habit_taxonomy")
        if isinstance(tax, str) and tax:
            return tax
    return None


def _two_segment_prefix(taxonomy: str) -> str:
    parts = [p for p in taxonomy.split("/") if p]
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0] if parts else taxonomy


class TaxonomyDriftPass:
    """Flag emerging taxonomies that are not yet configured roots."""

    prefix = "t"
    section = "Taxonomy drift"

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        habits = _load_habits(cfg)
        roots = list(habits.taxonomy.roots)

        snap = load_snapshot(cfg)
        buckets: dict[str, list[str]] = defaultdict(list)

        for cid, claim in snap.claims.items():
            if claim.status != ClaimStatus.ACTIVE:
                continue
            tax = _claim_taxonomy(cfg, cid, list(claim.supports))
            if tax is None:
                continue
            if _matches_any_root(tax, roots):
                continue
            bucket = _two_segment_prefix(tax)
            buckets[bucket].append(cid)

        entries: list[DigestEntry] = []
        for prefix in sorted(buckets):
            cids = sorted(buckets[prefix])
            if len(cids) < CLUSTER_MIN:
                continue
            payload: dict[str, Any] = {
                "action": "add_taxonomy_root",
                "root": prefix,
                "example_claim_ids": cids[:5],
            }
            entries.append(
                DigestEntry(
                    id="",
                    section=self.section,
                    line=(
                        f"{len(cids)} claims cluster under {prefix!r} outside configured "
                        f"taxonomy roots — add as a root?"
                    ),
                    action=payload,
                )
            )
        return entries
