from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SAMPLING_LIMIT_PER_TURN = 5


class SamplingRateLimitError(Exception):
    """Raised when a TurnState exceeds SAMPLING_LIMIT_PER_TURN sampling calls."""


@dataclass
class TurnState:
    _events: list[dict] = field(default_factory=list)
    _artifact_ids: list[str] = field(default_factory=list)
    dataset_loaded: bool = False
    scratchpad: str = ""
    sampling_calls: int = 0

    def record_tool(
        self, name: str, result_payload: Any, status: str = "ok",
    ) -> None:
        p_value = None
        correction = None
        result: dict | None = None
        if isinstance(result_payload, dict):
            result = dict(result_payload)
            p_value = result.get("p_value")
            correction = result.get("correction")
        self._events.append(
            {
                "tool": name,
                "status": status,
                "result": result,
                "p_value": p_value,
                "correction": correction,
            }
        )

    def record_artifact(self, artifact_id: str) -> None:
        if artifact_id not in self._artifact_ids:
            self._artifact_ids.append(artifact_id)

    def record_sampling_call(self) -> None:
        """Increment sampling counter, raising SamplingRateLimitError when limit exceeded."""
        if self.sampling_calls >= SAMPLING_LIMIT_PER_TURN:
            raise SamplingRateLimitError(
                f"Sampling limit of {SAMPLING_LIMIT_PER_TURN} calls per turn exceeded."
            )
        self.sampling_calls += 1

    def as_trace(self) -> list[dict]:
        return list(self._events)

    def artifact_ids(self) -> tuple[str, ...]:
        return tuple(self._artifact_ids)
