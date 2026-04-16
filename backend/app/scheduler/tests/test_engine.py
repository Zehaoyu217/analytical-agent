"""Unit tests for CronEngine (H4.T3)."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.scheduler.engine import CronEngine
from app.scheduler.jobs import CronJob


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_job(**kwargs) -> CronJob:
    defaults = dict(schedule="0 * * * *", prompt="test prompt", enabled=True)
    defaults.update(kwargs)
    return CronJob(**defaults)


def _make_engine() -> tuple[CronEngine, MagicMock, MagicMock]:
    """Return (engine, mock_session_db, mock_agent_factory)."""
    db = MagicMock()
    factory = MagicMock()
    engine = CronEngine(session_db=db, agent_factory=factory)
    return engine, db, factory


# ── sync_from_db ───────────────────────────────────────────────────────────────

def test_sync_from_db_schedules_enabled_jobs():
    engine, db, _ = _make_engine()
    job = _make_job(enabled=True)
    db.list_cron_jobs.return_value = [job]

    engine.sync_from_db()

    db.list_cron_jobs.assert_called_once_with(enabled_only=True)
    # Scheduler should have one job registered
    assert len(engine._scheduler.get_jobs()) == 1
    assert engine._scheduler.get_jobs()[0].id == job.id


def test_sync_from_db_clears_existing_before_reload():
    engine, db, _ = _make_engine()
    job_a = _make_job(enabled=True)
    job_b = _make_job(enabled=True)
    db.list_cron_jobs.return_value = [job_a]
    engine.sync_from_db()
    assert len(engine._scheduler.get_jobs()) == 1

    # Second sync with a different job list
    db.list_cron_jobs.return_value = [job_b]
    engine.sync_from_db()

    jobs = engine._scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == job_b.id


# ── add_job ────────────────────────────────────────────────────────────────────

def test_add_job_persists_to_db_and_schedules():
    engine, db, _ = _make_engine()
    job = _make_job(enabled=True)

    engine.add_job(job)

    db.upsert_cron_job.assert_called_once_with(job)
    assert len(engine._scheduler.get_jobs()) == 1


def test_add_job_disabled_does_not_schedule():
    engine, db, _ = _make_engine()
    job = _make_job(enabled=False)

    engine.add_job(job)

    db.upsert_cron_job.assert_called_once_with(job)
    assert len(engine._scheduler.get_jobs()) == 0


# ── remove_job ─────────────────────────────────────────────────────────────────

def test_remove_job_deletes_from_db():
    engine, db, _ = _make_engine()
    job = _make_job(enabled=True)
    engine.add_job(job)
    assert len(engine._scheduler.get_jobs()) == 1

    engine.remove_job(job.id)

    db.delete_cron_job.assert_called_once_with(job.id)
    assert len(engine._scheduler.get_jobs()) == 0


# ── pause_job / resume_job ─────────────────────────────────────────────────────

def test_pause_job_updates_db_and_pauses_scheduler():
    engine, db, _ = _make_engine()
    job = _make_job(enabled=True)
    engine.add_job(job)

    engine.pause_job(job.id)

    db.update_cron_job.assert_called_with(job.id, enabled=False)


def test_resume_job_updates_db():
    engine, db, _ = _make_engine()
    job = _make_job(enabled=True)
    engine.add_job(job)
    engine.pause_job(job.id)

    engine.resume_job(job.id)

    db.update_cron_job.assert_any_call(job.id, enabled=True)


# ── trigger_now ────────────────────────────────────────────────────────────────

def test_trigger_now_raises_key_error_for_unknown_job():
    engine, db, _ = _make_engine()
    db.list_cron_jobs.return_value = []

    with pytest.raises(KeyError):
        engine.trigger_now("nonexistent-id")
