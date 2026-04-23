from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import pytest

from second_brain.config import Config
from second_brain.gardener.protocol import (
    Budget,
    BudgetExceeded,
    PassEstimate,
    Proposal,
    Tier,
)
from second_brain.gardener.runner import GardenerRunner


@dataclass
class _GardenerHabitsStub:
    models: dict[str, str]
    passes: dict[str, bool]
    max_cost_usd_per_run: float = 1.0
    max_tokens_per_source: int = 500
    dry_run: bool = False
    mode: str = "proposal"


@dataclass
class _HabitsStub:
    gardener: _GardenerHabitsStub


def _mk_cfg(tmp_path: Path) -> Config:
    (tmp_path / "digests").mkdir()
    sb = tmp_path / ".sb"
    sb.mkdir()
    return Config(home=tmp_path, sb_dir=sb)


def _habits(**over: Any) -> _HabitsStub:
    passes = {"extract": True, "re_abstract": False, "semantic_link": False,
              "dedupe": False, "contradict": False, "taxonomy_curate": False,
              "wiki_summarize": False}
    passes.update(over.pop("passes", {}))
    g = _GardenerHabitsStub(
        models={"cheap": "anthropic/claude-haiku-4-5", "default": "anthropic/claude-sonnet-4-6", "deep": "anthropic/claude-opus-4-7"},
        passes=passes,
        **over,
    )
    return _HabitsStub(gardener=g)


@dataclass
class _StubPass:
    name: str
    tier: Tier = "cheap"
    prefix: str = "gx"
    proposals: list[Proposal] = field(default_factory=list)
    est: PassEstimate = field(default_factory=lambda: PassEstimate(tokens=10, cost_usd=0.001))
    raise_budget: bool = False
    ran: bool = False

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        return self.est

    def run(self, cfg: Any, habits: Any, client: Any, budget: Budget) -> Iterator[Proposal]:
        self.ran = True
        for p in self.proposals:
            budget.charge(p.cost_usd, tokens=p.tokens_in + p.tokens_out)
            yield p
        if self.raise_budget:
            raise BudgetExceeded("boom")


def _prop(pass_name: str = "extract", line: str = "claim 1") -> Proposal:
    return Proposal(
        pass_name=pass_name,
        section="Gardener extract",
        line=line,
        action={"type": "promote_claim", "source_id": "src_x", "statement": line},
        input_refs=["src_x"],
        tokens_in=50,
        tokens_out=10,
        cost_usd=0.0005,
    )


def test_runner_writes_to_pending_and_audit(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    stub = _StubPass(name="extract", proposals=[_prop(), _prop(line="claim 2")])
    runner = GardenerRunner(
        cfg, _habits(), passes=[stub], client_factory=lambda m: object()
    )

    result = runner.run()

    assert stub.ran
    assert result.passes_run == ["extract"]
    assert result.proposals_added == 2
    assert result.total_tokens == 120
    assert result.total_cost_usd == pytest.approx(0.001)
    assert result.errors == []

    pending = (cfg.digests_dir / "pending.jsonl").read_text().splitlines()
    assert len(pending) == 2
    row = json.loads(pending[0])
    assert row["action"]["type"] == "promote_claim"
    assert row["pass"] == "extract"
    assert row["origin"] == "gardener"

    audit_log = (cfg.sb_dir / ".state" / "gardener.log.jsonl").read_text().splitlines()
    assert len(audit_log) == 2
    assert json.loads(audit_log[0])["accepted"] is None


def test_dry_run_suppresses_writes(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    stub = _StubPass(name="extract", proposals=[_prop()])
    sentinel = {"called": False}

    def factory(model: str) -> Any:
        sentinel["called"] = True
        return object()

    runner = GardenerRunner(cfg, _habits(), passes=[stub], client_factory=factory)
    result = runner.run(dry_run=True)

    assert stub.ran
    assert result.proposals_added == 1
    assert sentinel["called"] is False, "client_factory should not be invoked in dry-run"
    assert not (cfg.digests_dir / "pending.jsonl").exists()
    assert not (cfg.sb_dir / ".state" / "gardener.log.jsonl").exists()


def test_disabled_passes_are_skipped(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    stub = _StubPass(name="extract", proposals=[_prop()])
    habits = _habits(passes={"extract": False})
    runner = GardenerRunner(cfg, habits, passes=[stub], client_factory=lambda m: object())

    result = runner.run()
    assert result.passes_run == []
    assert result.proposals_added == 0
    assert stub.ran is False


def test_only_filter_restricts_passes(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    a = _StubPass(name="extract", proposals=[_prop()])
    b = _StubPass(name="re_abstract", proposals=[_prop(pass_name="re_abstract")])
    habits = _habits(passes={"extract": True, "re_abstract": True})
    runner = GardenerRunner(cfg, habits, passes=[a, b], client_factory=lambda m: object())

    result = runner.run(only=["re_abstract"])
    assert result.passes_run == ["re_abstract"]
    assert a.ran is False
    assert b.ran is True


def test_budget_exceeded_halts_but_keeps_partial(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    big = Proposal(
        pass_name="extract",
        section="Gardener extract",
        line="expensive",
        action={"type": "promote_claim"},
        input_refs=["src_x"],
        tokens_in=100,
        tokens_out=10,
        cost_usd=2.0,  # exceeds default $1 cap on first charge
    )
    stub = _StubPass(name="extract", proposals=[_prop(), big, _prop(line="after")])
    runner = GardenerRunner(cfg, _habits(), passes=[stub], client_factory=lambda m: object())

    result = runner.run()
    # First proposal was cheap; second tripped the cap; third never emitted.
    assert result.proposals_added == 1
    assert result.errors and "extract" in result.errors[0]

    pending = (cfg.digests_dir / "pending.jsonl").read_text().splitlines()
    assert len(pending) == 1


def test_estimate_returns_enabled_only(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    a = _StubPass(name="extract", est=PassEstimate(tokens=100, cost_usd=0.02))
    b = _StubPass(name="re_abstract", est=PassEstimate(tokens=50, cost_usd=0.01))
    habits = _habits(passes={"extract": True, "re_abstract": False})
    runner = GardenerRunner(cfg, habits, passes=[a, b])

    est = runner.estimate()
    assert set(est.passes.keys()) == {"extract"}
    assert est.total_cost_usd == pytest.approx(0.02)
