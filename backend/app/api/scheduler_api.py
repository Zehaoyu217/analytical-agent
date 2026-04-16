"""Scheduler REST API — CRUD + trigger for cron jobs (H4).

Endpoints
---------
POST   /api/scheduler/jobs              create a new job
GET    /api/scheduler/jobs              list all jobs
GET    /api/scheduler/jobs/{job_id}     get a single job
PUT    /api/scheduler/jobs/{job_id}     enable / disable a job
DELETE /api/scheduler/jobs/{job_id}     delete a job
POST   /api/scheduler/jobs/{job_id}/run trigger a job immediately
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


# ── Input schemas ─────────────────────────────────────────────────────────────

class JobCreateBody(BaseModel):
    """Accepts a natural-language or 5-field cron schedule plus a prompt."""

    schedule: str
    prompt: str


class JobUpdateBody(BaseModel):
    """Only ``enabled`` is mutable via the update endpoint."""

    enabled: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_out(job: Any) -> dict[str, Any]:
    return {
        "id": job.id,
        "schedule": job.schedule,
        "prompt": job.prompt,
        "enabled": job.enabled,
        "created_at": job.created_at,
        "last_run_at": job.last_run_at,
        "next_run_at": job.next_run_at,
        "last_session_id": job.last_session_id,
    }


def _get_engine() -> Any:
    from app.harness.wiring import get_cron_engine  # noqa: PLC0415
    return get_cron_engine()


def _get_db() -> Any:
    from app.harness.wiring import get_session_db  # noqa: PLC0415
    return get_session_db()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/jobs", status_code=201)
def create_job(body: JobCreateBody) -> dict[str, Any]:
    """Create and schedule a new cron job."""
    from app.scheduler.jobs import CronJobCreate  # noqa: PLC0415

    try:
        job = CronJobCreate(schedule=body.schedule, prompt=body.prompt).to_job()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _get_engine().add_job(job)
    return _job_out(job)


@router.get("/jobs")
def list_jobs(enabled_only: bool = False) -> list[dict[str, Any]]:
    """List all cron jobs, newest first."""
    rows = _get_db().list_cron_jobs(enabled_only=enabled_only)
    return [_job_out(r) for r in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    """Return a single cron job by id."""
    rows = _get_db().list_cron_jobs(enabled_only=False)
    job = next((r for r in rows if r.id == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_out(job)


@router.put("/jobs/{job_id}")
def update_job(job_id: str, body: JobUpdateBody) -> dict[str, Any]:
    """Enable or disable a cron job."""
    engine = _get_engine()
    if body.enabled:
        engine.resume_job(job_id)
    else:
        engine.pause_job(job_id)
    rows = _get_db().list_cron_jobs(enabled_only=False)
    job = next((r for r in rows if r.id == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_out(job)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str) -> None:
    """Delete a cron job and unschedule it."""
    _get_engine().remove_job(job_id)


@router.post("/jobs/{job_id}/run", status_code=202)
def trigger_job(job_id: str) -> dict[str, Any]:
    """Trigger a cron job immediately, outside its normal schedule."""
    try:
        _get_engine().trigger_now(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    return {"job_id": job_id, "status": "triggered"}
