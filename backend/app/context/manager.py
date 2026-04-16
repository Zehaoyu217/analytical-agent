from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextLayer:
    """A named layer in the context window."""

    name: str
    tokens: int
    compactable: bool
    items: list[dict[str, Any]]


class ContextManager:
    """Tracks context window composition across layers.

    Provides live snapshots for the devtools Context Inspector tab
    and records compaction history for the timeline chart.
    """

    def __init__(
        self,
        max_tokens: int = 200_000,
        compaction_threshold: float = 0.80,
    ) -> None:
        self._max_tokens = max_tokens
        self._compaction_threshold = compaction_threshold
        self._layers: list[ContextLayer] = []
        self._compaction_history: list[dict[str, Any]] = []
        self._turn: int = 0

    @property
    def total_tokens(self) -> int:
        return sum(layer.tokens for layer in self._layers)

    @property
    def utilization(self) -> float:
        if self._max_tokens == 0:
            return 0.0
        return self.total_tokens / self._max_tokens

    @property
    def compaction_needed(self) -> bool:
        return self.utilization >= self._compaction_threshold

    @property
    def compaction_history(self) -> list[dict[str, Any]]:
        return list(self._compaction_history)

    def add_layer(self, layer: ContextLayer) -> None:
        existing = [i for i, lyr in enumerate(self._layers) if lyr.name == layer.name]
        if existing:
            self._layers[existing[0]] = layer
        else:
            self._layers.append(layer)

    def remove_layer(self, name: str) -> None:
        self._layers = [lyr for lyr in self._layers if lyr.name != name]

    def snapshot(self) -> dict[str, Any]:
        """Return current context state for the devtools inspector."""
        return {
            "total_tokens": self.total_tokens,
            "max_tokens": self._max_tokens,
            "utilization": round(self.utilization, 4),
            "compaction_needed": self.compaction_needed,
            "layers": [
                {
                    "name": layer.name,
                    "tokens": layer.tokens,
                    "compactable": layer.compactable,
                    "items": layer.items,
                }
                for layer in self._layers
            ],
            "compaction_history": self._compaction_history,
        }

    def record_compaction(
        self,
        tokens_before: int,
        tokens_after: int,
        removed: list[dict[str, Any]],
        survived: list[str],
    ) -> None:
        entry: dict[str, Any] = {
            "id": len(self._compaction_history) + 1,
            "timestamp": datetime.now(UTC).isoformat(),
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_freed": tokens_before - tokens_after,
            "trigger_utilization": round(tokens_before / self._max_tokens, 4),
            "removed": removed,
            "survived": survived,
        }
        self._compaction_history.append(entry)
        try:
            from app.trace.publishers import publish_compaction
            dropped_names = [r.get("name", "") for r in removed if isinstance(r, dict)]
            publish_compaction(
                turn=self._current_turn(),
                before_token_count=tokens_before,
                after_token_count=tokens_after,
                dropped_layers=[str(n) for n in dropped_names],
                kept_layers=survived,
            )
        except Exception:
            logger.warning("publish_compaction raised", exc_info=True)

    def set_turn(self, turn: int) -> None:
        self._turn = turn

    def _current_turn(self) -> int:
        return self._turn


# ── Per-session registry ──────────────────────────────────────────────────────

class _SessionRegistry:
    """Thread-safe registry mapping session_id → ContextManager."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, ContextManager] = {}

    def get_or_create(self, session_id: str) -> ContextManager:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = ContextManager()
            return self._sessions[session_id]

    def get(self, session_id: str) -> ContextManager | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


# Singleton registry — imported by context_api and chat_api.
session_registry = _SessionRegistry()
