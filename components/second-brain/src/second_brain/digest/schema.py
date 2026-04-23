"""Digest schema — entry + shared error types.

Each pass returns `list[DigestEntry]`. `action` is a JSON-serialisable dict that
the `DigestApplier` (Batch 2) dispatches on via its `"action"` key. Payload
schemas are documented in the plan; the Builder later rewrites `id` to a stable
prefix+counter form.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class DigestPassError(RuntimeError):
    """Raised by a digest pass when an expected real/fake client is unavailable.

    Passes must never silently fall back to random or empty output when a
    required Claude call cannot be made. Raising this error surfaces the
    configuration problem explicitly.
    """


@dataclass(frozen=True)
class DigestEntry:
    """One actionable line in a daily digest.

    Fields:
        id: Stable short id like "r01". Passes may emit an empty string or a
            per-pass local counter; the Builder rewrites ids at orchestration
            time so they are globally unique within a digest.
        section: Human-readable section heading (e.g. "Reconciliation").
        line: One-line actionable sentence. Convention: ends with "?" when a
            user decision is required, otherwise with "." for informational
            summaries.
        action: JSON-serialisable replay payload. The `"action"` key names the
            handler the Applier dispatches to. Remaining keys are handler-specific.
    """

    id: str
    section: str
    line: str
    action: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
