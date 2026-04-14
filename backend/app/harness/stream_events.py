"""SSE event types for AgentLoop streaming.

Each event serialises to an SSE frame:

    event: <type>
    data: {"type": "<type>", ...payload fields...}

"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamEvent:
    """A single streaming event emitted during an agent run."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        """Serialise as a complete SSE frame (event + data + blank line)."""
        data = json.dumps({"type": self.type, **self.payload})
        return f"event: {self.type}\ndata: {data}\n\n"


def sse_line(event_type: str, payload: dict[str, Any]) -> str:
    """Build an SSE frame string without constructing a full StreamEvent."""
    return StreamEvent(type=event_type, payload=payload).to_sse()
