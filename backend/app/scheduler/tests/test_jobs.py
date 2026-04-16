"""Unit tests for CronJob models and parse_schedule (H4.T2)."""
from __future__ import annotations

import pytest

from app.scheduler.jobs import CronJob, CronJobCreate, CronJobResult, parse_schedule


# ── parse_schedule ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("hourly",          "0 * * * *"),
    ("daily",           "0 9 * * *"),
    ("weekly",          "0 9 * * 1"),
    ("every 3 hours",   "0 */3 * * *"),
    ("every 6 hours",   "0 */6 * * *"),
    ("every morning",   "0 8 * * *"),
    ("every evening",   "0 18 * * *"),
])
def test_parse_schedule_natural_aliases(raw: str, expected: str):
    assert parse_schedule(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("every 4 hours",   "0 */4 * * *"),
    ("every 15 minutes","*/15 * * * *"),
    ("every 2 hours",   "0 */2 * * *"),
    ("every 30 minutes","*/30 * * * *"),
])
def test_parse_schedule_every_n_pattern(raw: str, expected: str):
    assert parse_schedule(raw) == expected


@pytest.mark.parametrize("raw", [
    "30 6 * * *",
    "0 9 * * 1",
    "*/5 * * * *",
])
def test_parse_schedule_raw_cron_passthrough(raw: str):
    assert parse_schedule(raw) == raw


def test_parse_schedule_invalid_raises():
    with pytest.raises(ValueError, match="Unrecognised schedule"):
        parse_schedule("run it sometime")


def test_parse_schedule_case_insensitive():
    assert parse_schedule("DAILY") == "0 9 * * *"
    assert parse_schedule("Hourly") == "0 * * * *"


# ── CronJobCreate.to_job ───────────────────────────────────────────────────────

def test_cron_job_create_to_job_parses_schedule():
    create = CronJobCreate(schedule="daily", prompt="Run daily report")
    job = create.to_job()
    assert isinstance(job, CronJob)
    assert job.schedule == "0 9 * * *"
    assert job.prompt == "Run daily report"
    assert job.enabled is True


def test_cron_job_has_uuid_id_by_default():
    job = CronJob(schedule="0 * * * *", prompt="test")
    assert len(job.id) == 36  # UUID4 length with hyphens


# ── CronJobResult ──────────────────────────────────────────────────────────────

def test_cron_job_result_fields():
    result = CronJobResult(session_id="s-123", outcome="done", ok=True)
    assert result.session_id == "s-123"
    assert result.ok is True
