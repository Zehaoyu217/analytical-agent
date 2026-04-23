from __future__ import annotations

import time

from app.harness.research.jobs import JobRegistry
from app.harness.research.types import ResearchResult


def _make_result() -> ResearchResult:
    return ResearchResult(
        summary="done", papers=(), code_examples=(), web_refs=(),
        follow_up_questions=(), modules_ran=("papers",),
        total_ms=50, budget_tokens_used=150_000,
    )


def test_create_and_get_running():
    reg = JobRegistry()
    job_id = reg.create(query="test", sources=["papers"], estimated_seconds=30)
    snap = reg.get(job_id)
    assert snap["status"] == "running"
    assert snap["elapsed_seconds"] >= 0
    assert snap["estimated_seconds"] == 30
    assert snap["progress"] == {}
    assert snap["partial_result"] == {}


def test_complete_job():
    reg = JobRegistry()
    job_id = reg.create(query="test", sources=["papers"], estimated_seconds=10)
    reg.complete(job_id, _make_result())
    snap = reg.get(job_id)
    assert snap["status"] == "done"
    assert snap["result"]["summary"] == "done"


def test_fail_job():
    reg = JobRegistry()
    job_id = reg.create(query="fail", sources=["code"], estimated_seconds=5)
    reg.fail(job_id, "network error")
    snap = reg.get(job_id)
    assert snap["status"] == "failed"
    assert snap["error"] == "network error"


def test_update_partial():
    reg = JobRegistry()
    job_id = reg.create(query="test", sources=["papers", "code"], estimated_seconds=20)
    reg.update_partial(job_id, "papers", [{"title": "P1"}])
    snap = reg.get(job_id)
    assert snap["progress"]["papers"] == "done"
    assert snap["partial_result"]["papers"] == [{"title": "P1"}]
    assert snap["progress"].get("code") is None


def test_not_found():
    reg = JobRegistry()
    snap = reg.get("nonexistent-id")
    assert snap["status"] == "not_found"


def test_ttl_expiry():
    reg = JobRegistry(ttl_seconds=0)
    job_id = reg.create(query="old", sources=["web"], estimated_seconds=5)
    reg.complete(job_id, _make_result())
    time.sleep(0.01)
    snap = reg.get(job_id)
    assert snap["status"] == "not_found"


def test_running_job_not_expired_by_ttl():
    reg = JobRegistry(ttl_seconds=0)
    job_id = reg.create(query="live", sources=["papers"], estimated_seconds=10)
    time.sleep(0.01)
    snap = reg.get(job_id)
    assert snap["status"] == "running"
