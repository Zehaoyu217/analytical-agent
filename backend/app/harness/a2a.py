"""Agent-to-Agent (A2A) delegation.

A parent agent calls ``delegate_subagent(task, tools_allowed)`` to spawn a
child ``AgentLoop`` with a restricted tool set.  The child runs to completion,
its result is persisted as a JSON artifact, and the parent receives
``{artifact_id, summary, steps}`` as the tool result.

Usage (in a harness setup)::

    from app.harness.a2a import register_delegate_tool

    # Register the tool on the parent dispatcher before starting the loop.
    register_delegate_tool(
        dispatcher=parent_dispatcher,
        client=model_client,
        parent_session_id=session_id,
    )
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.harness.clients.base import ModelClient
from app.harness.dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)

_DELEGATE_TOOL_NAME = "delegate_subagent"

_SUBAGENT_SYSTEM = (
    "You are a focused analytical sub-agent completing a delegated task. "
    "Be concise and precise. Return a clear, structured summary of findings."
)


@dataclass
class SubagentResult:
    """Outcome of a delegated sub-agent run."""

    artifact_id: str
    summary: str
    steps: int
    ok: bool
    error: str = ""


class SubagentDispatcher:
    """Runs a child AgentLoop for A2A delegation.

    Instantiate once per parent session and call :meth:`dispatch` for each
    delegation request.  The child loop uses only tools whose names appear in
    *tools_allowed* and are already registered on the parent dispatcher.
    """

    def __init__(
        self,
        client: ModelClient,
        parent_dispatcher: ToolDispatcher,
        parent_session_id: str,
        artifact_dir: str | Path = "data/artifacts",
    ) -> None:
        self._client = client
        self._parent_dispatcher = parent_dispatcher
        self._parent_session_id = parent_session_id
        self._artifact_dir = Path(artifact_dir)

    def dispatch(
        self,
        task: str,
        tools_allowed: list[str],
        *,
        max_steps: int = 6,
        system: str = "",
    ) -> SubagentResult:
        """Run a sub-agent synchronously and return its result."""
        # Import here to avoid a circular import at module load time.
        from app.harness.loop import AgentLoop

        child_dispatcher = ToolDispatcher()
        for name in tools_allowed:
            handler = self._parent_dispatcher.get_handler(name)
            if handler is not None:
                child_dispatcher.register(name, handler)

        child_system = system or _SUBAGENT_SYSTEM
        loop = AgentLoop(child_dispatcher)

        try:
            outcome = loop.run(
                client=self._client,
                system=child_system,
                user_message=task,
                dataset_loaded=False,
                max_steps=max_steps,
            )
        except Exception as exc:
            logger.error("sub-agent loop failed: %s", exc, exc_info=True)
            return SubagentResult(
                artifact_id="",
                summary=f"Sub-agent error: {exc}",
                steps=0,
                ok=False,
                error=str(exc),
            )

        artifact_id = self._save_artifact(task, outcome)
        return SubagentResult(
            artifact_id=artifact_id,
            summary=outcome.final_text[:500],
            steps=outcome.steps,
            ok=True,
        )

    def _save_artifact(self, task: str, outcome: Any) -> str:
        artifact_id = f"a2a-{int(time.time() * 1000)}"
        art_dir = self._artifact_dir / self._parent_session_id
        art_dir.mkdir(parents=True, exist_ok=True)
        art_path = art_dir / f"{artifact_id}.json"
        payload: dict[str, Any] = {
            "type": "subagent_result",
            "task": task,
            "final_text": outcome.final_text,
            "steps": outcome.steps,
            "stop_reason": outcome.stop_reason,
        }
        with open(art_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return artifact_id


def register_delegate_tool(
    dispatcher: ToolDispatcher,
    client: ModelClient,
    parent_session_id: str,
    artifact_dir: str | Path = "data/artifacts",
) -> None:
    """Register the ``delegate_subagent`` tool on *dispatcher*.

    Must be called before the parent ``AgentLoop`` starts.  Calling it a
    second time with the same dispatcher raises ``ValueError`` (tool already
    registered).
    """
    subagent = SubagentDispatcher(
        client=client,
        parent_dispatcher=dispatcher,
        parent_session_id=parent_session_id,
        artifact_dir=artifact_dir,
    )

    def _handle(args: dict[str, Any]) -> dict[str, Any]:
        task: str = args.get("task", "")
        tools_allowed: list[str] = args.get("tools_allowed", [])
        if not task:
            return {"error": "task is required"}
        result = subagent.dispatch(task, tools_allowed)
        return {
            "artifact_id": result.artifact_id,
            "summary": result.summary,
            "steps": result.steps,
            "ok": result.ok,
            **({"error": result.error} if not result.ok else {}),
        }

    dispatcher.register(_DELEGATE_TOOL_NAME, _handle)
