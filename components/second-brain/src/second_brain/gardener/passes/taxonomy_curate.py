"""Taxonomy curate pass — suggest new taxonomy roots from claim clusters.

Groups claims by existing taxonomy prefix, finds clusters of claims that
share a strong shared-token signal but fall under ``uncategorized`` (or
under an existing root that looks overloaded). Asks the LLM whether the
cluster deserves its own taxonomy root and emits ``add_taxonomy_root``
proposals when it does.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from second_brain.frontmatter import load_document
from second_brain.gardener.client import LLMClient, LLMError
from second_brain.gardener.cost import estimate_cost
from second_brain.gardener.protocol import (
    Budget,
    BudgetExceeded,
    PassEstimate,
    Proposal,
    Tier,
)

log = logging.getLogger(__name__)
_WORD_RE = re.compile(r"[a-z][a-z0-9]{3,}")
_CLUSTER_MIN = 4  # need at least this many claims under "uncategorized"

_SYSTEM_PROMPT = """\
You curate a personal KB taxonomy. Given a list of claim statements that are
currently uncategorized, decide whether they share a coherent topic worthy of
a new top-level taxonomy root. Return JSON:
{"create": true|false, "root": "<kebab-case-slug>", "rationale": str}
Only set create=true when the cluster is genuinely coherent.
"""


class TaxonomyCuratePass:
    name = "taxonomy_curate"
    tier: Tier = "deep"
    prefix = "gt"

    def _clusters(self, cfg: Any) -> list[list[dict[str, Any]]]:
        claims_dir: Path = cfg.claims_dir
        if not claims_dir.exists():
            return []
        uncategorized: list[dict[str, Any]] = []
        for p in sorted(claims_dir.glob("*.md")):
            try:
                fm, _body = load_document(p)
            except (ValueError, OSError):
                continue
            taxonomy = str(fm.get("taxonomy") or "uncategorized")
            prefix = taxonomy.split("/", 1)[0]
            if prefix != "uncategorized":
                continue
            statement = str(fm.get("statement") or "")
            uncategorized.append(
                {
                    "id": str(fm.get("id") or p.stem),
                    "statement": statement,
                    "tokens": set(_WORD_RE.findall(statement.lower())),
                }
            )
        if len(uncategorized) < _CLUSTER_MIN:
            return []

        # Cluster by dominant shared token (simple, greedy).
        token_counts: Counter[str] = Counter()
        for item in uncategorized:
            token_counts.update(item["tokens"])

        clusters: list[list[dict[str, Any]]] = []
        used: set[str] = set()
        for token, count in token_counts.most_common():
            if count < _CLUSTER_MIN:
                break
            bucket = [
                it for it in uncategorized
                if token in it["tokens"] and it["id"] not in used
            ]
            if len(bucket) >= _CLUSTER_MIN:
                clusters.append(bucket)
                used.update(it["id"] for it in bucket)
        return clusters

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        clusters = self._clusters(cfg)
        model = habits.gardener.models.get("deep") or habits.gardener.models.get(
            "default", ""
        )
        tokens_in = 800 * len(clusters)
        tokens_out = 80 * len(clusters)
        cost = estimate_cost(model, tokens_in, tokens_out) if model else 0.0
        return PassEstimate(tokens=tokens_in + tokens_out, cost_usd=cost)

    def run(
        self, cfg: Any, habits: Any, client: LLMClient, budget: Budget
    ) -> Iterator[Proposal]:
        existing_roots = set(habits.taxonomy.roots or [])
        for cluster in self._clusters(cfg):
            statements = "\n".join(
                f"- ({it['id']}) {it['statement']}" for it in cluster[:20]
            )
            try:
                result = client.complete(
                    _SYSTEM_PROMPT, statements, max_tokens=160, temperature=0.0
                )
            except LLMError as exc:
                log.warning("taxonomy_curate: llm failed: %s", exc)
                continue
            cost = estimate_cost(client.model, result.tokens_in, result.tokens_out)
            try:
                budget.charge(cost, tokens=result.tokens_in + result.tokens_out)
            except BudgetExceeded:
                raise
            decision = _parse_decision(result.text)
            if not decision.get("create"):
                continue
            root = str(decision.get("root") or "").strip().lower()
            root = re.sub(r"[^a-z0-9-]+", "-", root).strip("-")
            if not root or root in existing_roots:
                continue
            existing_roots.add(root)
            action = {
                "type": "add_taxonomy_root",
                "root": root,
                "rationale": decision.get("rationale", ""),
            }
            yield Proposal(
                pass_name=self.name,
                section="Gardener taxonomy_curate",
                line=f"Propose taxonomy root /{root}/ ({len(cluster)} claims)",
                action=action,
                input_refs=[it["id"] for it in cluster],
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=cost,
            )


def _parse_decision(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}
