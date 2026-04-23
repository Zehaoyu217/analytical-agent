from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.harness.research.modules.papers import PapersModule, _RawPaper, _estimate_tokens, _recency_query


def test_estimate_tokens():
    assert _estimate_tokens("hello world") == 2   # len=11, 11//4=2


def test_recency_query_detected():
    assert _recency_query("recent calibration methods 2025") is True
    assert _recency_query("state of the art transformer") is True
    assert _recency_query("Platt 1999 calibration") is False


def test_run_returns_empty_on_all_failures():
    module = PapersModule()
    with patch.object(module, "_search_hf_papers", return_value=[]):
        with patch.object(module, "_search_semantic_scholar", return_value=[]):
            with patch.object(module, "_search_arxiv", return_value=[]):
                result = module.run("calibration", budget_tokens=10_000)
    assert result.papers == ()
    assert result.crawl_depth == 0


def test_run_uses_hf_papers_for_recent_query():
    module = PapersModule()
    mock_paper = _RawPaper(
        title="Recent Calibration",
        arxiv_id="2501.99999",
        year=2025,
        citation_count=5,
        abstract="Great paper about calibration",
        source="hf_papers",
    )
    with patch.object(module, "_search_hf_papers", return_value=[mock_paper]) as mock_hf:
        with patch.object(module, "_search_semantic_scholar", return_value=[]):
            with patch.object(module, "_citation_graph", return_value=[]):
                result = module.run("recent calibration 2025", budget_tokens=50_000)
    mock_hf.assert_called_once()
    assert len(result.papers) >= 1


def test_run_respects_tiny_budget():
    module = PapersModule()
    result = module.run("test", budget_tokens=100)
    assert result.papers == ()


def test_s2_rate_limit_falls_back_to_arxiv():
    module = PapersModule()
    with patch.object(module, "_search_hf_papers", return_value=[]):
        with patch.object(module, "_search_semantic_scholar", side_effect=Exception("429")):
            with patch.object(module, "_search_arxiv", return_value=[]) as mock_arxiv:
                result = module.run("calibration sigmoid", budget_tokens=50_000)
    mock_arxiv.assert_called_once()
