"""Pydantic models and schedule parsing for the cron scheduler (H4)."""
from __future__ import annotations

import re
import time
from uuid import uuid4

from pydantic import BaseModel, Field

# ── Natural-language schedule aliases ────────────────────────────────────────

NATURAL_SCHEDULES: dict[str, str] = {
    "hourly":         "0 * * * *",
    "daily":          "0 9 * * *",
    "weekly":         "0 9 * * 1",
    "every 3 hours":  "0 */3 * * *",
    "every 6 hours":  "0 */6 * * *",
    "every morning":  "0 8 * * *",
    "every evening":  "0 18 * * *",
}

# Pattern: "every N hours" or "every N minutes"
_EVERY_N_PATTERN = re.compile(
    r"every\s+(\d+)\s+(hour|hours|minute|minutes)", re.I
)

# Rough validation for a 5-field cron expression
_CRON_FIELDS = re.compile(
    r"^(\S+\s+){4}\S+$"
)


def parse_schedule(raw: str) -> str:
    """Return a valid 5-field cron expression from natural language or passthrough.

    Resolution order:
    1. Exact match in ``NATURAL_SCHEDULES``
    2. Regex pattern "every N hours/minutes"
    3. Passthrough if *raw* looks like a 5-field cron expression
    4. ``ValueError`` otherwise
    """
    stripped = raw.strip().lower()

    # 1. Exact alias lookup
    if stripped in NATURAL_SCHEDULES:
        return NATURAL_SCHEDULES[stripped]

    # 2. "every N hours / every N minutes"
    m = _EVERY_N_PATTERN.match(stripped)
    if m:
        n = int(m.group(1))
        unit = m.group(2).rstrip("s")  # "hour" or "minute"
        if unit == "hour":
            return f"0 */{n} * * *"
        else:  # minute
            return f"*/{n} * * * *"

    # 3. Raw cron passthrough
    if _CRON_FIELDS.match(raw.strip()):
        return raw.strip()

    raise ValueError(
        f"Unrecognised schedule {raw!r}. "
        "Use a 5-field cron expression or one of: "
        + ", ".join(sorted(NATURAL_SCHEDULES))
    )


# ── Pydantic models ───────────────────────────────────────────────────────────

class CronJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    schedule: str            # 5-field cron expression (already parsed)
    prompt: str
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)
    last_run_at: float | None = None
    next_run_at: float | None = None
    last_session_id: str | None = None


class CronJobCreate(BaseModel):
    """Input model — accepts cron expression or natural language."""
    schedule: str   # resolved via parse_schedule()
    prompt: str

    def to_job(self) -> CronJob:
        return CronJob(
            schedule=parse_schedule(self.schedule),
            prompt=self.prompt,
        )


class CronJobResult(BaseModel):
    session_id: str
    outcome: str
    ok: bool
