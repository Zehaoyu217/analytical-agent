"""RealAgentAdapter — drives the real /api/chat/stream endpoint for eval runs.

Usage in eval tests:
    from tests.evals.real_agent import RealAgentAdapter

    adapter = RealAgentAdapter(base_url="http://localhost:8000", traces_dir="traces")
    trace = await adapter.run(
        prompt="Which customer segment has the highest default rate?",
        db_path="/path/to/eval.db",
    )

The adapter:
1. POSTs to /api/chat/stream with the eval prompt and db_path.
2. Streams SSE events, capturing tool calls and the final response.
3. After the stream ends, loads session data from SessionDB (preferred) or YAML.
4. Returns an AgentTrace suitable for the eval runner.

Prerequisites:
- Backend running at base_url
- eval.db seeded (make seed-eval)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.core.home import sessions_db_path
from app.evals.types import AgentTrace
from app.storage.session_db import Session, SessionDB

_DEFAULT_BASE_URL = os.environ.get("CCAGENT_EVAL_BASE_URL", "http://localhost:8000")
_DEFAULT_TRACES_DIR = os.environ.get("TRACE_DIR", "traces")


class BackendNotReachableError(RuntimeError):
    """Raised when the backend is not reachable at the configured base_url."""


class RealAgentAdapter:
    """Connects the eval framework to the running backend via /api/chat/stream.

    Args:
        base_url: Base URL of the running backend (default: http://localhost:8000).
        traces_dir: Directory where trace YAMLs are written (default: traces/).
        timeout: HTTP timeout for the full SSE stream (seconds).
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        traces_dir: str | Path = _DEFAULT_TRACES_DIR,
        timeout: float = 300.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._traces_dir = Path(traces_dir)
        self._timeout = timeout
        self._session_db: SessionDB | None = None

    async def run(self, prompt: str, db_path: str | None = None) -> AgentTrace:
        """Run the real agent against the given prompt.

        Args:
            prompt: The eval question / instruction to send.
            db_path: Unused — the backend sandbox always connects to its own
                     data/duckdb/eval.db.  Kept for interface compatibility.

        Returns:
            AgentTrace with queries, final_output, errors, and timing.
        """
        started = time.monotonic()

        errors: list[str] = []
        final_output = ""
        tool_call_previews: list[dict[str, Any]] = []
        # The backend appends a timestamp+random suffix to our session_id.
        # Capture the real id from the first turn_start so trace YAML lookup works.
        backend_session_id = ""

        # Create a conversation record so the session appears in the frontend
        # History tab (conversations are separate from the chat stream).
        title = prompt[:80] + ("…" if len(prompt) > 80 else "")
        session_id = await self._create_conversation(title)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat/stream",
                json={
                    "message": prompt,
                    "session_id": session_id,
                },
                headers={"Accept": "text/event-stream"},
            ) as resp:
                if resp.status_code != 200:
                    raise BackendNotReachableError(
                        f"Backend returned HTTP {resp.status_code} for /api/chat/stream"
                    )
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")
                    # StreamEvent.to_sse() flattens payload into the top-level
                    # dict: {"type": "...", ...payload fields...}.  There is no
                    # nested "payload" key — read directly from `event`.

                    if event_type == "turn_start" and event.get("session_id"):
                        # Capture the real session_id (backend appends timestamp suffix)
                        backend_session_id = event["session_id"]

                    elif event_type == "tool_call":
                        tool_call_previews.append({
                            "name": event.get("name", ""),
                            "input_preview": event.get("input_preview", ""),
                        })

                    elif event_type == "tool_result":
                        if event.get("status") == "error":
                            errors.append(
                                f"{event.get('name', 'tool')}: "
                                f"{event.get('preview', '')[:200]}"
                            )

                    elif event_type == "debug_step":
                        import sys as _sys
                        p = event
                        _sys.stderr.write(
                            f"[DEBUG step={p.get('step')} synth={p.get('synthesis')} "
                            f"tool_choice={p.get('tool_choice')!r} "
                            f"n_tools={p.get('n_tools')} n_msgs={p.get('n_req_msgs')} "
                            f"resp_len={p.get('resp_len')} tool_calls={p.get('resp_tool_calls')} "
                            f"stop={p.get('stop_reason')!r} "
                            f"in_tok={p.get('input_tokens')} out_tok={p.get('output_tokens')} "
                            f"ms={p.get('latency_ms')}]\n"
                        )
                        _sys.stderr.flush()

                    elif event_type == "turn_end":
                        final_output = event.get("final_text", "") or ""

        duration_ms = int((time.monotonic() - started) * 1000)

        # ── Load full trace YAML for accurate query data ──────────────────────
        # After EVAL-2 (loop.py publish_tool_call), the YAML has ToolCallEvents
        # with full tool_input. We prefer those over truncated SSE previews.
        queries = self._extract_queries_from_trace(backend_session_id)

        # Fall back to SSE previews if trace not yet written / no ToolCallEvents
        if not queries:
            queries = [
                tc["input_preview"]
                for tc in tool_call_previews
                if tc["name"] == "execute_python" and tc["input_preview"]
            ]

        # Extract intermediate artifacts from trace
        intermediate = self._extract_intermediate_from_trace(backend_session_id)

        # Token count from trace summary (0 if trace not available)
        token_count = self._extract_token_count_from_trace(backend_session_id)

        # Persist user prompt + assistant response into the conversation so the
        # frontend History tab shows content for the eval session.
        if session_id:
            await self._append_turn(session_id, "user", prompt)
            # Use final_output if the agent produced one; otherwise summarise
            # from trace queries so the conversation isn't empty.
            assistant_content = final_output
            if not assistant_content and queries:
                assistant_content = (
                    f"[Agent ran {len(queries)} queries in {duration_ms}ms]\n\n"
                    + "\n".join(f"- `{q[:120]}`" for q in queries[:5])
                )
            if assistant_content:
                await self._append_turn(session_id, "assistant", assistant_content)

        return AgentTrace(
            queries=queries,
            intermediate=intermediate,
            final_output=final_output,
            token_count=token_count,
            duration_ms=duration_ms,
            errors=errors,
        )

    # ── Conversation helpers ──────────────────────────────────────────────────

    async def _create_conversation(self, title: str) -> str:
        """Create a conversation record and return its id."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/conversations",
                json={"title": title},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def _append_turn(self, conv_id: str, role: str, content: str) -> None:
        """Append a turn to an existing conversation (best-effort)."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self._base_url}/api/conversations/{conv_id}/turns",
                    json={"role": role, "content": content},
                )
        except Exception:  # noqa: BLE001
            pass

    # ── Trace helpers (DB preferred, YAML fallback) ───────────────────────────

    def _get_session_db(self) -> SessionDB:
        """Return a SessionDB instance pointing at the shared sessions.db."""
        if self._session_db is None:
            self._session_db = SessionDB(db_path=sessions_db_path())
        return self._session_db

    def _load_session_from_db(self, session_id: str) -> Session | None:
        """Look up session + messages from SessionDB. Returns None if not found."""
        if not session_id:
            return None
        try:
            return self._get_session_db().get_session(session_id, include_messages=True)
        except Exception:  # noqa: BLE001
            return None

    def _load_trace_yaml(self, session_id: str) -> dict[str, Any] | None:
        """Legacy YAML loader — used as fallback when DB has no entry."""
        path = self._traces_dir / f"{session_id}.yaml"
        if not path.exists():
            return None
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))  # type: ignore[return-value]
        except yaml.YAMLError:
            return None

    def _extract_queries_from_trace(self, session_id: str) -> list[str]:
        # Try DB first
        session = self._load_session_from_db(session_id)
        if session is not None:
            queries: list[str] = []
            for msg in session.messages:
                if msg.role == "tool" and msg.tool_calls:
                    name = msg.tool_calls.get("name", "")
                    if name == "execute_python":
                        code = msg.tool_calls.get("input", {}).get("code", "")
                        if code:
                            queries.append(str(code))
            return queries
        # Fallback to YAML
        trace = self._load_trace_yaml(session_id)
        if trace is None:
            return []
        queries = []
        for ev in trace.get("events", []):
            if ev.get("kind") == "tool_call" and ev.get("tool_name") == "execute_python":
                code = ev.get("tool_input", {}).get("code", "")
                if code:
                    queries.append(str(code))
        return queries

    def _extract_intermediate_from_trace(self, session_id: str) -> list[Any]:
        # Try DB first
        session = self._load_session_from_db(session_id)
        if session is not None:
            intermediate: list[Any] = []
            for msg in session.messages:
                if msg.role == "tool" and msg.tool_calls:
                    name = msg.tool_calls.get("name", "")
                    output = (msg.tool_result or {}).get("output", "")
                    if output and name != "execute_python":
                        intermediate.append({
                            "tool": name,
                            "output_preview": str(output)[:200],
                        })
            return intermediate
        # Fallback to YAML
        trace = self._load_trace_yaml(session_id)
        if trace is None:
            return []
        intermediate = []
        for ev in trace.get("events", []):
            if ev.get("kind") == "tool_call":
                output = ev.get("tool_output", "")
                if output and ev.get("tool_name") != "execute_python":
                    intermediate.append({
                        "tool": ev.get("tool_name"),
                        "output_preview": str(output)[:200],
                    })
        return intermediate

    def _extract_token_count_from_trace(self, session_id: str) -> int:
        # Try DB first
        session = self._load_session_from_db(session_id)
        if session is not None:
            return session.input_tokens + session.output_tokens
        # Fallback to YAML
        trace = self._load_trace_yaml(session_id)
        if trace is None:
            return 0
        summary = trace.get("summary", {})
        return int(
            summary.get("total_input_tokens", 0)
            + summary.get("total_output_tokens", 0)
        )

    # ── Health check ──────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if the backend is reachable."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/api/health")
                return resp.status_code == 200
        except (httpx.HTTPError, OSError):
            return False
