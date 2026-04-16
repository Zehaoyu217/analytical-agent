"""Async job runner for cron-triggered agent sessions (H4)."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.scheduler.engine import AgentFactory
    from app.scheduler.jobs import CronJob, CronJobResult
    from app.storage.session_db import SessionDB


async def run_job(
    job: CronJob,
    session_db: SessionDB,
    agent_factory: AgentFactory,
) -> CronJobResult:
    """Run a single cron job and store the result as a session.

    1. Creates a session in ``sessions.db`` with ``source="cron"``.
    2. Builds a fresh AgentLoop via *agent_factory*.
    3. Runs the loop with *job.prompt* as the user message.
    4. Finalizes the session (outcome, step_count, tokens).
    5. Updates the cron_jobs row (last_run_at, last_session_id).
    6. Returns a :class:`CronJobResult`.
    """
    from app.scheduler.jobs import CronJobResult  # noqa: PLC0415

    session_id = str(uuid.uuid4())
    session_db.create_session(
        id=session_id,
        model=None,
        goal=job.prompt[:300],
        source="cron",
    )

    ok = False
    outcome = ""
    step_count = 0
    input_tokens = 0
    output_tokens = 0

    try:
        loop = agent_factory.build_loop(session_id=session_id)

        # build_loop returns an AgentLoop-like; call run() synchronously since
        # cron jobs run in the background scheduler thread pool.
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: loop.run(
                client=agent_factory.build_client(),  # type: ignore[union-attr]
                system=agent_factory.build_system(),  # type: ignore[union-attr]
                user_message=job.prompt,
                dataset_loaded=False,
            ),
        )
        outcome = result.final_text or ""
        step_count = result.steps
        ok = True
    except Exception:  # noqa: BLE001
        import logging  # noqa: PLC0415
        logging.getLogger(__name__).exception(
            "Cron job %s failed for session %s", job.id, session_id
        )

    session_db.finalize_session(
        id=session_id,
        outcome=outcome[:500] if outcome else None,
        step_count=step_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    session_db.update_cron_job(
        job.id,
        last_run_at=time.time(),
        last_session_id=session_id,
    )

    return CronJobResult(session_id=session_id, outcome=outcome, ok=ok)
