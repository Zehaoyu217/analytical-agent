from dataclasses import dataclass, field
from pathlib import Path

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.index.retriever import RetrievalHit
from second_brain.inject.runner import build_injection


@dataclass
class _StubRetriever:
    hits: list[RetrievalHit] = field(default_factory=list)
    calls: list[tuple[str, int, str]] = field(default_factory=list)

    def search(self, query, k=10, scope="both", taxonomy=None,
               with_neighbors=False):
        self.calls.append((query, k, scope))
        return list(self.hits[:k])


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    return Config(home=home, sb_dir=home / ".sb")


def test_skipped_when_disabled(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default().model_copy(update={
        "injection": Habits.default().injection.model_copy(update={"enabled": False}),
    })
    retriever = _StubRetriever()
    res = build_injection(cfg, habits, prompt="anything", retriever=retriever)
    assert res.block == ""
    assert res.skipped_reason == "disabled"
    assert retriever.calls == []


def test_skipped_on_skip_pattern_match(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default()  # default skip_patterns include "^/"
    retriever = _StubRetriever(hits=[RetrievalHit(
        id="clm_x", kind="claim", score=1.0, matched_field="statement", snippet="x")])
    res = build_injection(cfg, habits, prompt="/help", retriever=retriever)
    assert res.block == ""
    assert res.skipped_reason == "skip_pattern"
    assert retriever.calls == []


def test_skipped_when_top_score_below_min(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default()
    retriever = _StubRetriever(hits=[
        RetrievalHit(id="clm_x", kind="claim", score=0.1,
                     matched_field="statement", snippet="weak"),
    ])
    res = build_injection(cfg, habits, prompt="explain transformers", retriever=retriever)
    assert res.block == ""
    assert res.skipped_reason == "below_min_score"


def test_happy_path_returns_block_and_hit_ids(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default()
    hits = [
        RetrievalHit(id="clm_a", kind="claim", score=0.9,
                     matched_field="statement", snippet="A"),
        RetrievalHit(id="clm_b", kind="claim", score=0.7,
                     matched_field="statement", snippet="B"),
    ]
    retriever = _StubRetriever(hits=hits)
    res = build_injection(cfg, habits, prompt="explain transformers",
                          retriever=retriever)
    assert res.skipped_reason is None
    assert "clm_a" in res.block
    assert res.hit_ids == ["clm_a", "clm_b"]
    # k from habits is 5 by default.
    assert retriever.calls == [("explain transformers", 5, "claims")]
