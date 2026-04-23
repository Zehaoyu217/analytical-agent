from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.gardener.client import LLMResult
from second_brain.gardener.passes.extract import ExtractPass, _parse_claims_json
from second_brain.gardener.protocol import Budget, BudgetExceeded


@dataclass
class FakeClient:
    responses: list[LLMResult]
    model: str = "anthropic/claude-haiku-4-5"
    calls: list[tuple[str, str]] = field(default_factory=list)
    _idx: int = 0

    def complete(self, system: str, user: str, **_: object) -> LLMResult:
        self.calls.append((system, user))
        r = self.responses[self._idx]
        self._idx += 1
        return r


@dataclass
class _GardenerHabitsStub:
    models: dict[str, str]
    max_tokens_per_source: int = 800


@dataclass
class _HabitsStub:
    gardener: _GardenerHabitsStub


def _mk_cfg(tmp_path: Path) -> Config:
    tmp_path.mkdir(parents=True, exist_ok=True)
    sb = tmp_path / ".sb"
    sb.mkdir()
    (tmp_path / "sources").mkdir()
    (tmp_path / "claims").mkdir()
    (tmp_path / "digests").mkdir()
    return Config(home=tmp_path, sb_dir=sb)


def _write_source(cfg: Config, source_id: str, title: str, body: str) -> None:
    folder = cfg.sources_dir / source_id
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    frontmatter = (
        f"---\n"
        f"id: {source_id}\n"
        f"title: {title}\n"
        f"kind: note\n"
        f"ingested_at: '{now}'\n"
        f"content_hash: abc123\n"
        f"---\n"
    )
    (folder / "_source.md").write_text(frontmatter + body, encoding="utf-8")


def _write_claim_covering(cfg: Config, claim_id: str, source_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    fm = (
        f"---\n"
        f"id: {claim_id}\n"
        f"statement: existing claim\n"
        f"kind: empirical\n"
        f"confidence: medium\n"
        f"supports: ['{source_id}']\n"
        f"extracted_at: '{now}'\n"
        f"---\n"
        f"body\n"
    )
    (cfg.claims_dir / f"{claim_id}.md").write_text(fm, encoding="utf-8")


def _habits() -> _HabitsStub:
    return _HabitsStub(
        gardener=_GardenerHabitsStub(
            models={"cheap": "anthropic/claude-haiku-4-5"},
            max_tokens_per_source=200,
        )
    )


def _claim_json(n: int) -> str:
    return json.dumps(
        [
            {
                "statement": f"claim number {i}",
                "kind": "empirical",
                "confidence": "medium",
                "evidence": f"quote {i}",
            }
            for i in range(n)
        ]
    )


def test_extract_skips_already_covered_source(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _write_source(cfg, "src_done", "Done", "body body body")
    _write_source(cfg, "src_new", "New", "fresh material to extract from")
    _write_claim_covering(cfg, "clm_old", "src_done")

    fake = FakeClient(responses=[LLMResult(text=_claim_json(2), tokens_in=50, tokens_out=10, model="anthropic/claude-haiku-4-5")])
    budget = Budget(max_cost_usd_per_run=1.0, max_tokens_per_source=200)
    props = list(ExtractPass().run(cfg, _habits(), fake, budget))

    # Only one source processed (src_new); src_done was covered.
    assert len(fake.calls) == 1
    assert "src_new" in fake.calls[0][1]
    assert len(props) == 2
    for p in props:
        assert p.pass_name == "extract"
        assert p.input_refs == ["src_new"]
        assert p.action["type"] == "promote_claim"
        assert p.action["source_id"] == "src_new"
        assert p.action["kind"] == "empirical"
        assert p.action["confidence"] == "medium"
        assert p.tokens_in == 50
        assert p.tokens_out == 10


def test_extract_two_sources_and_budget_accumulates(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _write_source(cfg, "src_a", "A", "alpha body")
    _write_source(cfg, "src_b", "B", "beta body")

    fake = FakeClient(
        responses=[
            LLMResult(text=_claim_json(2), tokens_in=100, tokens_out=20, model="anthropic/claude-haiku-4-5"),
            LLMResult(text=_claim_json(1), tokens_in=100, tokens_out=20, model="anthropic/claude-haiku-4-5"),
        ]
    )
    budget = Budget(max_cost_usd_per_run=1.0, max_tokens_per_source=500)
    props = list(ExtractPass().run(cfg, _habits(), fake, budget))

    assert len(props) == 3
    assert budget.tokens_spent == 240
    assert budget.spent_usd > 0.0


def test_extract_budget_exceeded_halts(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _write_source(cfg, "src_a", "A", "body a")
    _write_source(cfg, "src_b", "B", "body b")

    # Haiku: 1/5 per Mtok. 1_000_000 in + 1_000_000 out = $6 per call.
    # Cap at $1 will trip on the first charge.
    fake = FakeClient(
        responses=[
            LLMResult(text=_claim_json(1), tokens_in=1_000_000, tokens_out=1_000_000, model="anthropic/claude-haiku-4-5"),
        ]
    )
    budget = Budget(max_cost_usd_per_run=1.0, max_tokens_per_source=500)

    it = ExtractPass().run(cfg, _habits(), fake, budget)
    with pytest.raises(BudgetExceeded):
        list(it)
    assert len(fake.calls) == 1  # second source never reached


def test_parse_claims_json_tolerant() -> None:
    # Fenced block.
    assert _parse_claims_json("```json\n" + _claim_json(1) + "\n```") != []
    # Invalid JSON returns [].
    assert _parse_claims_json("not json at all") == []
    # Non-list returns [].
    assert _parse_claims_json('{"a": 1}') == []
    # Entries with bad kind dropped.
    mix = json.dumps(
        [
            {"statement": "ok", "kind": "empirical", "confidence": "high"},
            {"statement": "bad kind", "kind": "science-fiction", "confidence": "high"},
            {"statement": "", "kind": "empirical", "confidence": "high"},
        ]
    )
    out = _parse_claims_json(mix)
    assert len(out) == 1
    assert out[0]["statement"] == "ok"


def test_extract_estimate_scales_with_unprocessed_sources(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _write_source(cfg, "src_1", "1", "body")
    _write_source(cfg, "src_2", "2", "body")
    _write_source(cfg, "src_3", "3", "body")

    est = ExtractPass().estimate(cfg, _habits())
    assert est.tokens > 0
    assert est.cost_usd > 0.0

    # Zero sources → zero estimate.
    cfg2 = _mk_cfg(tmp_path / "x")
    assert ExtractPass().estimate(cfg2, _habits()).tokens == 0
