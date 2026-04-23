"""Semantic link pass — propose claim↔wiki backlinks.

Pure-heuristic candidate generation (token-overlap Jaccard) feeding an LLM
adjudicator that decides whether a candidate link is semantically useful.
Emits ``backlink_claim_to_wiki`` proposals, which the existing applier
handles by appending a backlink line to the wiki file.
"""
from __future__ import annotations

import json
import logging
import os
import re
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

_WORD_RE = re.compile(r"[a-z0-9]{4,}")
_TOP_CANDIDATES = 3  # per claim
_MIN_JACCARD = 0.08

_SYSTEM_PROMPT = """\
You judge whether a KB claim and a wiki page are semantically related enough
to warrant a backlink. Return JSON: {"link": true|false, "reason": str}
"link" = true only when the wiki page directly supports, contradicts, or
expands on the claim.
"""


class SemanticLinkPass:
    name = "semantic_link"
    tier: Tier = "default"
    prefix = "gs"

    def _candidates(self, cfg: Any) -> list[tuple[str, str, Path, Path]]:
        wiki_dir_env = os.environ.get("SB_WIKI_DIR", "")
        wiki_dir = Path(wiki_dir_env) if wiki_dir_env else None
        if wiki_dir is None or not wiki_dir.exists():
            return []
        claims_dir: Path = cfg.claims_dir
        if not claims_dir.exists():
            return []

        wiki_pages: list[tuple[Path, set[str]]] = []
        for md in sorted(wiki_dir.rglob("*.md")):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            wiki_pages.append((md, set(_WORD_RE.findall(text.lower()))))

        out: list[tuple[str, str, Path, Path]] = []
        for cp in sorted(claims_dir.glob("*.md")):
            try:
                fm, body = load_document(cp)
            except (ValueError, OSError):
                continue
            cid = str(fm.get("id") or cp.stem)
            statement = str(fm.get("statement") or "")
            claim_tokens = set(_WORD_RE.findall((statement + " " + body).lower()))
            if not claim_tokens:
                continue
            scored: list[tuple[float, Path]] = []
            for wpath, wtoks in wiki_pages:
                if not wtoks:
                    continue
                inter = len(claim_tokens & wtoks)
                union = len(claim_tokens | wtoks)
                if union == 0:
                    continue
                j = inter / union
                if j >= _MIN_JACCARD:
                    scored.append((j, wpath))
            scored.sort(reverse=True)
            for _, wpath in scored[:_TOP_CANDIDATES]:
                out.append((cid, statement, cp, wpath))
        return out

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        candidates = self._candidates(cfg)
        model = habits.gardener.models.get("default", "")
        tokens_in = 600 * len(candidates)
        tokens_out = 40 * len(candidates)
        cost = estimate_cost(model, tokens_in, tokens_out) if model else 0.0
        return PassEstimate(tokens=tokens_in + tokens_out, cost_usd=cost)

    def run(
        self, cfg: Any, habits: Any, client: LLMClient, budget: Budget
    ) -> Iterator[Proposal]:
        for cid, statement, _cp, wpath in self._candidates(cfg):
            try:
                wiki_body = wpath.read_text(encoding="utf-8")
            except OSError:
                continue
            user = (
                f"Claim id: {cid}\nStatement: {statement}\n\n"
                f"Wiki page ({wpath.name}):\n{wiki_body[:1500]}"
            )
            try:
                result = client.complete(
                    _SYSTEM_PROMPT, user, max_tokens=128, temperature=0.0
                )
            except LLMError as exc:
                log.warning("semantic_link: llm failed for %s: %s", cid, exc)
                continue
            cost = estimate_cost(client.model, result.tokens_in, result.tokens_out)
            try:
                budget.charge(cost, tokens=result.tokens_in + result.tokens_out)
            except BudgetExceeded:
                raise
            decision = _parse_decision(result.text)
            if not decision.get("link"):
                continue
            wiki_dir_env = os.environ.get("SB_WIKI_DIR", "")
            try:
                rel = wpath.relative_to(Path(wiki_dir_env)) if wiki_dir_env else wpath
                rel_str = str(rel)
            except ValueError:
                rel_str = wpath.name
            action = {
                "type": "backlink_claim_to_wiki",
                "claim_id": cid,
                "wiki_path": rel_str,
                "reason": decision.get("reason", ""),
            }
            yield Proposal(
                pass_name=self.name,
                section="Gardener semantic_link",
                line=f"Backlink {cid} → {wpath.name}",
                action=action,
                input_refs=[cid, str(wpath)],
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
