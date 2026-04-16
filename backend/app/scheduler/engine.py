"""CronEngine — in-process APScheduler for recurring agent jobs (H4).

Wired into the FastAPI lifespan:  start() on app startup, stop() on shutdown.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from app.scheduler.jobs import CronJob
    from app.storage.session_db import SessionDB

logger = logging.getLogger(__name__)


class AgentFactory(Protocol):
    """Thin helper that builds a ready-to-run AgentLoop for a given session."""

    def build_loop(self, session_id: str) -> Any: ...
    def build_client(self) -> Any: ...
    def build_system(self) -> str: ...


class CronEngine:
    """Manages the in-process APScheduler instance.

    All job mutations (add / remove / pause / resume) are performed on the
    live scheduler; call :meth:`sync_from_db` to reconcile the full DB state.
    """

    def __init__(
        self,
        session_db: SessionDB,
        agent_factory: AgentFactory,
    ) -> None:
        self._db = session_db
        self._factory = agent_factory
        self._scheduler = BackgroundScheduler(timezone="UTC")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the scheduler and load enabled jobs from the database."""
        self.sync_from_db()
        if not self._scheduler.running:
            self._scheduler.start()
        logger.info("CronEngine started")

    def stop(self) -> None:
        """Shut the scheduler down gracefully (does not wait for running jobs)."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        logger.info("CronEngine stopped")

    # ── Sync ──────────────────────────────────────────────────────────────────

    def sync_from_db(self) -> None:
        """Remove all scheduled jobs then re-add every enabled job from the DB.

        Call after any CRUD operation on the jobs table so the live scheduler
        stays in sync with persisted state.
        """
        # Remove all existing APScheduler jobs first.
        for job in self._scheduler.get_jobs():
            self._scheduler.remove_job(job.id)

        # Re-add enabled jobs from the DB.
        rows = self._db.list_cron_jobs(enabled_only=True)
        for row in rows:
            self._schedule_one(row)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_job(self, job: CronJob) -> None:
        """Persist *job* to the DB and register it with the scheduler."""
        self._db.upsert_cron_job(job)
        if job.enabled:
            self._schedule_one(job)

    def remove_job(self, job_id: str) -> None:
        """Delete *job_id* from the DB and unschedule it."""
        self._db.delete_cron_job(job_id)
        try:
            self._scheduler.remove_job(job_id)
        except Exception:  # noqa: BLE001 — job may not be registered
            pass

    def pause_job(self, job_id: str) -> None:
        """Disable *job_id* in the DB and pause it in the scheduler."""
        self._db.update_cron_job(job_id, enabled=False)
        try:
            self._scheduler.pause_job(job_id)
        except Exception:  # noqa: BLE001
            pass

    def resume_job(self, job_id: str) -> None:
        """Enable *job_id* in the DB and resume it in the scheduler."""
        self._db.update_cron_job(job_id, enabled=True)
        try:
            self._scheduler.resume_job(job_id)
        except Exception:  # noqa: BLE001
            pass

    def trigger_now(self, job_id: str) -> None:
        """Run *job_id* immediately (outside its normal schedule)."""
        rows = self._db.list_cron_jobs(enabled_only=False)
        job = next((r for r in rows if r.id == job_id), None)
        if job is None:
            raise KeyError(f"cron job {job_id!r} not found")
        self._run_job(job)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _schedule_one(self, job: CronJob) -> None:
        """Register *job* with the APScheduler instance."""
        trigger = CronTrigger.from_crontab(job.schedule, timezone="UTC")
        try:
            self._scheduler.add_job(
                func=self._run_job,
                trigger=trigger,
                args=[job],
                id=job.id,
                replace_existing=True,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to schedule cron job %s", job.id)

    def _run_job(self, job: CronJob) -> None:
        """Execute the job synchronously in the APScheduler thread pool."""
        import asyncio  # noqa: PLC0415
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        from app.scheduler.runner import run_job  # noqa: PLC0415
        try:
            result = loop.run_until_complete(
                run_job(job, self._db, self._factory)
            )
            logger.info(
                "Cron job %s completed: session=%s ok=%s",
                job.id, result.session_id, result.ok,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Cron job %s raised an exception", job.id)
