from __future__ import annotations

import dataclasses
import time
import uuid
from threading import RLock
from typing import Any

from app.harness.research.types import ResearchResult

_DEFAULT_TTL = 1800  # 30 minutes


def _result_to_dict(r: ResearchResult) -> dict[str, Any]:
    return dataclasses.asdict(r)


class JobRegistry:
    """Thread-safe in-memory store for async research jobs."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL) -> None:
        self._ttl = ttl_seconds
        self._lock = RLock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def create(self, query: str, sources: list[str], estimated_seconds: int) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "started_at": time.monotonic(),
                "query": query,
                "sources": sources,
                "estimated_seconds": estimated_seconds,
                "result": None,
                "error": None,
                "partial": {},   # module_name -> serialized findings
                "progress": {},  # module_name -> "done"
            }
        return job_id

    def complete(self, job_id: str, result: ResearchResult) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "done"
                self._jobs[job_id]["result"] = _result_to_dict(result)
                self._jobs[job_id]["completed_at"] = time.monotonic()

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = error
                self._jobs[job_id]["completed_at"] = time.monotonic()

    def update_partial(self, job_id: str, module: str, findings: Any) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["partial"][module] = findings
                self._jobs[job_id]["progress"][module] = "done"

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {"status": "not_found"}
            # TTL check: only expire completed/failed jobs
            if job["status"] in ("done", "failed"):
                completed_at = job.get("completed_at", job["started_at"])
                if time.monotonic() - completed_at > self._ttl:
                    del self._jobs[job_id]
                    return {"status": "not_found"}
            elapsed = int(time.monotonic() - job["started_at"])
            return {
                "status": job["status"],
                "elapsed_seconds": elapsed,
                "estimated_seconds": job["estimated_seconds"],
                "progress": dict(job["progress"]),
                "partial_result": dict(job["partial"]),
                "result": job.get("result"),
                "error": job.get("error"),
            }
