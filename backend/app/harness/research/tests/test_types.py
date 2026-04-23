from __future__ import annotations

from app.harness.research.types import (
    CodeExample,
    CodeResult,
    PaperFinding,
    PapersResult,
    ResearchResult,
    RoutePlan,
    WebPage,
    WebResult,
)


def test_paper_finding_defaults():
    pf = PaperFinding(title="Test", key_finding="finding", source="arxiv")
    assert pf.arxiv_id is None
    assert pf.year is None
    assert pf.citation_count is None
    assert pf.section_excerpts == ()


def test_paper_finding_frozen():
    import dataclasses
    pf = PaperFinding(title="Test", key_finding="finding", source="arxiv")
    try:
        pf.title = "mutated"  # type: ignore[misc]
        raise AssertionError("should have raised FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_papers_result_defaults():
    pr = PapersResult()
    assert pr.papers == ()
    assert pr.crawl_depth == 0


def test_papers_result_instance_isolation():
    a = PapersResult()
    b = PapersResult()
    # tuples are immutable — no shared state possible
    assert a.papers is not b.papers or a.papers == ()


def test_research_result_budget_warning_default():
    rr = ResearchResult(
        summary="test",
        papers=(),
        code_examples=(),
        web_refs=(),
        follow_up_questions=(),
        modules_ran=("papers",),
        total_ms=100,
        budget_tokens_used=150_000,
    )
    assert rr.budget_warning is None


def test_route_plan_structure():
    plan = RoutePlan(
        modules=("papers", "code"),
        sub_queries={"papers": "q1", "code": "q2"},
        budgets={"papers": 90_000, "code": 60_000},
        parallel_ok=True,
        rationale="independent queries",
    )
    assert plan.budgets["papers"] == 90_000
    assert plan.parallel_ok is True


def test_budget_warning_set():
    rr = ResearchResult(
        summary="test",
        papers=(),
        code_examples=(),
        web_refs=(),
        follow_up_questions=(),
        modules_ran=("papers",),
        total_ms=100,
        budget_tokens_used=1_000_000,
        budget_warning="Hard cap applied.",
    )
    assert rr.budget_warning == "Hard cap applied."


def test_code_example_defaults():
    ex = CodeExample(
        url="https://github.com/org/repo/blob/main/train.py",
        repo="org/repo",
        file_path="train.py",
        snippet="import sklearn",
        relevance="Uses sklearn calibration",
    )
    assert ex.stars is None


def test_code_result_defaults():
    cr = CodeResult()
    assert cr.examples == ()


def test_web_page_construction():
    pg = WebPage(url="https://example.com", title="Example", summary="A summary")
    assert pg.url == "https://example.com"
    assert pg.summary == "A summary"


def test_web_result_defaults():
    wr = WebResult()
    assert wr.pages == ()
