"""Extract pass — promote unprocessed sources into claim proposals.

For each source with no claim pointing at it, the pass truncates the source
body to ``max_tokens_per_source`` (rough char-per-token approximation) and
asks the LLM for a JSON array of claim records. Each returned record becomes
one :class:`Proposal` with action ``{type: "promote_claim", ...}``.

No files are written here — the runner is responsible for appending
proposals to ``pending.jsonl`` and the audit log.
"""
from __future__ import annotations

import json
import logging
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

# Rough heuristic — 4 chars ≈ 1 token for English prose. Good enough for
# budget estimates; the final charge uses actual usage returned by the API.
_CHARS_PER_TOKEN = 4
_VALID_KINDS = {"empirical", "theoretical", "definitional", "opinion", "prediction"}
_VALID_CONFIDENCES = {"low", "medium", "high"}

_SYSTEM_PROMPT = """\
You are a claim extractor for a personal research knowledge base.
Read the source and emit a JSON array of atomic claims. Each claim MUST be:
  - one sentence, self-contained, no pronouns referring outside itself
  - non-redundant with other claims in your output
  - faithful to the source (no invented facts)

Return ONLY a JSON array, no prose. Schema for each element:
{
  "statement": str,                      // the atomic claim
  "kind": "empirical"|"theoretical"|"definitional"|"opinion"|"prediction",
  "confidence": "low"|"medium"|"high",   // how strongly the source asserts it
  "evidence": str                        // short quote or paraphrase from the source
}

If the source is empty or uninterpretable, return [].
"""


class ExtractPass:
    name = "extract"
    tier: Tier = "cheap"
    prefix = "gx"

    def _unprocessed_sources(self, cfg: Any) -> list[tuple[str, Path]]:
        """Sources with no claim pointing at them yet."""
        sources_dir: Path = cfg.sources_dir
        claims_dir: Path = cfg.claims_dir
        if not sources_dir.exists():
            return []

        covered: set[str] = set()
        if claims_dir.exists():
            for claim_md in claims_dir.glob("*.md"):
                try:
                    meta, _ = load_document(claim_md)
                except (ValueError, OSError):
                    continue
                for ref in meta.get("supports", []) or []:
                    # refs can be 'src_xxx' or 'src_xxx#section'
                    covered.add(str(ref).split("#", 1)[0])

        out: list[tuple[str, Path]] = []
        for src_md in sorted(sources_dir.glob("*/_source.md")):
            source_id = src_md.parent.name
            if source_id in covered:
                continue
            out.append((source_id, src_md))
        return out

    def _read_body(self, path: Path, max_tokens: int) -> tuple[str, str]:
        """Return (title, truncated_body) from a source markdown file."""
        try:
            meta, body = load_document(path)
        except (ValueError, OSError) as exc:
            log.warning("extract: skip %s (%s)", path, exc)
            return ("", "")
        title = str(meta.get("title") or meta.get("id") or path.parent.name)
        max_chars = max(1, max_tokens * _CHARS_PER_TOKEN)
        if len(body) > max_chars:
            body = body[:max_chars]
        return title, body

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        model = habits.gardener.models.get("cheap", "")
        max_tokens = int(habits.gardener.max_tokens_per_source)
        todo = self._unprocessed_sources(cfg)
        # Assume each source uses up to max_tokens in + ~10% out.
        tokens_in = max_tokens * len(todo)
        tokens_out = max(0, tokens_in // 10)
        cost = estimate_cost(model, tokens_in, tokens_out) if model else 0.0
        return PassEstimate(tokens=tokens_in + tokens_out, cost_usd=cost)

    def run(
        self, cfg: Any, habits: Any, client: LLMClient, budget: Budget
    ) -> Iterator[Proposal]:
        max_tokens = int(habits.gardener.max_tokens_per_source)
        todo = self._unprocessed_sources(cfg)

        for source_id, src_path in todo:
            title, body = self._read_body(src_path, max_tokens)
            if not body.strip():
                continue

            user = f"Source id: {source_id}\nTitle: {title}\n\n---\n{body}"
            try:
                result = client.complete(
                    _SYSTEM_PROMPT, user, max_tokens=2048, temperature=0.0
                )
            except LLMError as exc:
                log.warning("extract: llm failed for %s: %s", source_id, exc)
                continue

            cost = estimate_cost(client.model, result.tokens_in, result.tokens_out)
            try:
                budget.charge(cost, tokens=result.tokens_in + result.tokens_out)
            except BudgetExceeded:
                raise

            records = _parse_claims_json(result.text)
            for rec in records:
                action = {
                    "type": "promote_claim",
                    "source_id": source_id,
                    "kind": rec["kind"],
                    "statement": rec["statement"],
                    "confidence": rec["confidence"],
                    "evidence": rec.get("evidence", ""),
                }
                yield Proposal(
                    pass_name=self.name,
                    section="Gardener extract",
                    line=rec["statement"],
                    action=action,
                    input_refs=[source_id],
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    cost_usd=cost,
                )


def _parse_claims_json(raw: str) -> list[dict[str, Any]]:
    """Tolerantly parse the LLM response into a list of valid claim records.

    Accepts either a bare JSON array or one wrapped in ```json fences. Drops
    entries that fail schema validation rather than raising.
    """
    text = raw.strip()
    if text.startswith("```"):
        # Strip fenced block (```json ... ``` or ``` ... ```).
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("extract: could not parse LLM output as JSON")
        return []
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        statement = entry.get("statement")
        kind = entry.get("kind")
        confidence = entry.get("confidence")
        if not (isinstance(statement, str) and statement.strip()):
            continue
        if kind not in _VALID_KINDS or confidence not in _VALID_CONFIDENCES:
            continue
        out.append(
            {
                "statement": statement.strip(),
                "kind": kind,
                "confidence": confidence,
                "evidence": str(entry.get("evidence", "")),
            }
        )
    return out
