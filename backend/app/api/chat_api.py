"""Chat endpoint with tool-enabled agent loop.

Supports a single tool: execute_python. The sandbox runs the code, captures
stdout, and extracts any Altair/Vega-Lite charts via a marker protocol.
Charts are returned as Vega-Lite JSON specs in the response.

POST /api/chat        — synchronous JSON response (backward-compatible)
POST /api/chat/stream — streaming SSE response (text/event-stream)
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import secrets
import sys
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import anthropic
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_config
from app.harness.clients.anthropic_client import AnthropicClient
from app.harness.clients.base import (
    CompletionRequest,
    Message,
    ModelClient,
    ToolSchema,
)
from app.harness.clients.ollama_client import OllamaClient
from app.harness.clients.openrouter_client import OpenRouterClient
from app.harness.config import ModelProfile
from app.harness.dispatcher import ToolDispatcher
from app.harness.loop import AgentLoop
from app.harness.sandbox import SandboxExecutor
from app.harness.sandbox_bootstrap import build_duckdb_globals
from app.harness.stream_events import sse_line
from app.trace.events import PromptSection
from app.trace.publishers import (
    TraceSession,
    publish_final_output,
    publish_llm_call,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

_MESSAGE_MAX_CHARS = 8000
_CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# ── sandbox ───────────────────────────────────────────────────────────────────

# Minimal bootstrap — only the universal analysis libraries.
_SANDBOX_BOOTSTRAP = "\n".join([
    "import sys, os",
    "import numpy as np",
    "import pandas as pd",
    "import altair as alt",
    "from datetime import datetime, date",
    "",
])

# Appended after user code: scans globals for Vega-Lite specs and emits markers.
_CHART_CAPTURE_SUFFIX = """
import json as __json_cap, sys as __sys_cap
for __vname_cap, __vobj_cap in list(globals().items()):
    if __vname_cap.startswith('_'):
        continue
    try:
        __d_cap = __vobj_cap.to_dict() if hasattr(__vobj_cap, 'to_dict') else None
        if (
            isinstance(__d_cap, dict)
            and isinstance(__d_cap.get('$schema'), str)
            and 'vega-lite' in __d_cap['$schema']
        ):
            __sys_cap.stdout.write(
                '\\n__VEGA_SPEC__' + __json_cap.dumps(__d_cap) + '__END_SPEC__\\n'
            )
            __sys_cap.stdout.flush()
    except Exception:
        pass
"""

_VEGA_MARKER_RE = re.compile(r"\n?__VEGA_SPEC__(.*?)__END_SPEC__\n?", re.DOTALL)


def _run_python(
    code: str,
    session_bootstrap: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    """Run code in sandbox. Returns (text_output, vega_specs)."""
    bootstrap = session_bootstrap or _SANDBOX_BOOTSTRAP
    executor = SandboxExecutor(
        python_executable=sys.executable,
        timeout_sec=30,
        extra_globals_script=bootstrap,
    )
    result = executor.run(code + "\n\n" + _CHART_CAPTURE_SUFFIX)

    charts: list[dict[str, Any]] = []
    for match in _VEGA_MARKER_RE.finditer(result.stdout):
        with contextlib.suppress(Exception):
            charts.append(json.loads(match.group(1).strip()))

    clean_out = _VEGA_MARKER_RE.sub("", result.stdout).strip()

    if not result.ok:
        err = result.stderr.strip()
        return (f"Error:\n{err}" if err else "Error: non-zero exit"), charts

    return clean_out or "(no output)", charts


# ── tool schema ───────────────────────────────────────────────────────────────

_EXECUTE_PYTHON = ToolSchema(
    name="execute_python",
    description=(
        "Execute Python code for data analysis and visualization. "
        "Pre-imported: numpy as np, pandas as pd, altair as alt. "
        "Assign any Altair chart to a variable (e.g. `chart = alt.Chart(...)`) "
        "— it will be auto-captured and rendered. print() output is returned."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            }
        },
        "required": ["code"],
    },
)

_WRITE_WORKING = ToolSchema(
    name="write_working",
    description=(
        "Write the full contents of the working scratchpad (working.md). "
        "Use markdown with sections: ## TODO, ## COT, ## Findings, ## Evidence. "
        "Always append — do not erase prior COT entries."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Full markdown content for working.md",
            }
        },
        "required": ["content"],
    },
)

# The two tools advertised to the LLM.  All analytical skills (correlate,
# profile, etc.) are called as Python functions inside the sandbox.
_CHAT_TOOLS = (_EXECUTE_PYTHON, _WRITE_WORKING)

_SYSTEM_PROMPT = (
    "You are a financial analytical assistant with Python execution capabilities.\n\n"
    "STRICT RULES:\n"
    "- Call execute_python AT MOST ONCE per user request. Never call it twice.\n"
    "- After the tool returns, write a brief 1-2 sentence summary. Stop there.\n\n"
    "When the user wants a chart or data analysis:\n"
    "1. Call execute_python ONCE with the complete, working code.\n"
    "2. numpy (np), pandas (pd), and altair (alt) are already imported.\n"
    "3. Assign the chart to any variable — it is auto-captured and rendered.\n"
    "4. Use your training knowledge for financial data (JPM, AAPL, MSFT, etc.).\n"
    "5. After the tool result, reply with 1-2 sentences summarising the key finding."
)

# ── model factory ─────────────────────────────────────────────────────────────


def _make_client(model_id: str, http: httpx.Client) -> ModelClient:
    """Route a model ID string to the appropriate backend client."""
    config = get_config()

    if model_id.startswith("claude-"):
        profile = ModelProfile(
            name=model_id,
            provider="anthropic",
            model_id=model_id,
            tier="advisory",
        )
        return AnthropicClient(profile, anthropic.Anthropic())  # type: ignore[return-value]

    if "/" in model_id:  # OpenRouter: "provider/model" or "provider/model:tag"
        profile = ModelProfile(
            name=model_id,
            provider="openrouter",
            model_id=model_id,
            tier="advisory",
            host="https://openrouter.ai/api/v1",
            options={"api_key": config.openrouter_api_key},
        )
        return OpenRouterClient(profile, http)  # type: ignore[return-value]

    # Ollama: "model:tag" or plain "model"
    profile = ModelProfile(
        name=model_id,
        provider="ollama",
        model_id=model_id,
        tier="advisory",
        host=config.ollama_base_url,
    )
    return OllamaClient(profile, http)  # type: ignore[return-value]


# ── agent loop ────────────────────────────────────────────────────────────────


def _agent_loop(
    model_id: str,
    message: str,
    max_steps: int = 3,
    session_bootstrap: str = "",
) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    """Run a tool-enabled agent loop. Returns (text, vega_specs, usage).

    Stops as soon as charts are produced: executes the tool, then makes one
    final text-only call for the summary. This prevents looping models from
    generating duplicate charts.
    """
    all_charts: list[dict[str, Any]] = []
    messages: list[Message] = [Message(role="user", content=message)]
    final_text = ""
    usage: dict[str, int] = {}

    with httpx.Client(timeout=120) as http:
        client = _make_client(model_id, http)

        for _step in range(max_steps):
            req = CompletionRequest(
                system=_SYSTEM_PROMPT,
                messages=tuple(messages),
                tools=(_EXECUTE_PYTHON,),
                max_tokens=2048,
            )
            resp = client.complete(req)
            final_text = resp.text
            usage = dict(resp.usage)

            if not resp.tool_calls:
                break

            messages.append(Message(role="assistant", content=resp.text or ""))
            got_charts_this_step = False

            for call in resp.tool_calls:
                if call.name == "execute_python":
                    code = str(call.arguments.get("code", ""))
                    output, charts = _run_python(code, session_bootstrap)
                    all_charts.extend(charts)
                    if charts:
                        got_charts_this_step = True
                    result_json = json.dumps(
                        {"output": output, "charts_rendered": len(charts)}
                    )
                else:
                    result_json = json.dumps({"error": f"unknown tool: {call.name}"})

                messages.append(
                    Message(
                        role="tool",
                        tool_use_id=call.id,
                        name=call.name,
                        content=result_json,
                    )
                )

            # Once charts are produced, get one text summary and stop.
            if got_charts_this_step:
                req = CompletionRequest(
                    system=_SYSTEM_PROMPT,
                    messages=tuple(messages),
                    tools=(),
                    max_tokens=256,
                )
                resp = client.complete(req)
                final_text = resp.text
                usage = dict(resp.usage)
                break

    if not final_text and all_charts:
        final_text = "Chart rendered above."

    return final_text, all_charts, usage


# ── streaming agent loop ──────────────────────────────────────────────────────


def _build_dispatcher(
    session_bootstrap: str,
    charts_out: list[dict[str, Any]],
) -> ToolDispatcher:
    """Build a ToolDispatcher with execute_python and write_working handlers.

    Charts produced by execute_python are appended to ``charts_out`` so the
    caller can include them in the turn_end SSE payload.
    """
    dispatcher = ToolDispatcher()

    def _exec_python(args: dict[str, Any]) -> dict[str, Any]:
        code = str(args.get("code", ""))
        output, charts = _run_python(code, session_bootstrap)
        charts_out.extend(charts)
        return {"output": output, "charts_rendered": len(charts)}

    def _write_working(args: dict[str, Any]) -> dict[str, Any]:
        content = str(args.get("content", ""))
        return {"ok": True, "content": content}

    dispatcher.register("execute_python", _exec_python)
    dispatcher.register("write_working", _write_working)
    return dispatcher


def _stream_agent_loop(
    model_id: str,
    message: str,
    session_id: str,
    max_steps: int = 6,
    session_bootstrap: str = "",
) -> Generator[str, None, None]:
    """Yield SSE-formatted strings as the full harness agent runs.

    Uses AgentLoop.run_stream() so all harness features are active:
    guardrails, scratchpad tracking (scratchpad_delta events), A2A delegation.

    Events yielded:
        turn_start, tool_call, tool_result, scratchpad_delta,
        a2a_start, a2a_end, turn_end, error
    """
    all_charts: list[dict[str, Any]] = []
    dispatcher = _build_dispatcher(session_bootstrap, all_charts)

    try:
        with httpx.Client(timeout=120) as http:
            client = _make_client(model_id, http)
            loop = AgentLoop(dispatcher)
            for event in loop.run_stream(
                client=client,
                system=_SYSTEM_PROMPT,
                user_message=message,
                dataset_loaded=bool(session_bootstrap),
                session_id=session_id,
                max_steps=max_steps,
                tools=_CHAT_TOOLS,
            ):
                if event.type == "turn_end":
                    # Inject accumulated charts so the frontend can render them.
                    yield sse_line("turn_end", {**event.payload, "charts": all_charts})
                else:
                    yield event.to_sse()
    except Exception as exc:
        logger.error("stream_agent_loop failed: %s", exc, exc_info=True)
        yield sse_line("error", {"message": str(exc)})


# ── API ───────────────────────────────────────────────────────────────────────


def _traces_dir() -> Path:
    return Path(os.environ.get("TRACE_DIR", "traces"))


def _make_trace_id(conversation_id: str | None) -> str:
    timestamp = int(time.time() * 1000)
    nonce = secrets.token_hex(3)
    if conversation_id is None:
        return f"chat-{timestamp}-{nonce}"
    return f"{conversation_id}-{timestamp}-{nonce}"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MESSAGE_MAX_CHARS)
    session_id: str | None = Field(default=None)
    dataset_path: str | None = Field(default=None)  # absolute path from upload


class ChatResponse(BaseModel):
    session_id: str
    response: str
    charts: list[dict[str, Any]] = []


@router.post("")
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    from app.api.settings_api import get_settings

    conversation_id = payload.session_id
    if conversation_id is not None and not _CONVERSATION_ID_RE.match(conversation_id):
        raise HTTPException(status_code=400, detail="invalid session_id")

    settings = get_settings()
    model_id = settings.model

    trace_id = _make_trace_id(conversation_id)
    output_dir = _traces_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    with TraceSession(
        session_id=trace_id,
        level=1,
        level_label="chat",
        input_query=payload.message,
        trace_mode="always",
        output_dir=output_dir,
    ):
        try:
            session_bootstrap = (
                build_duckdb_globals(trace_id, payload.dataset_path)
                if payload.dataset_path
                else ""
            )
            response_text, charts, usage = _agent_loop(
                model_id,
                payload.message,
                session_bootstrap=session_bootstrap,
            )
        except Exception as exc:
            logger.error("agent loop failed for model %s: %s", model_id, exc, exc_info=True)
            response_text = f"[{model_id} error] {exc}"
            charts = []
            usage = {}

        latency_ms = int((time.monotonic() - started) * 1000)

        publish_llm_call(
            step_id="s1",
            turn=1,
            model=model_id,
            temperature=0.0,
            max_tokens=2048,
            prompt_text=payload.message,
            sections=[
                PromptSection(
                    source="user_query",
                    lines="1-1",
                    text=payload.message,
                ),
            ],
            response_text=response_text,
            tool_calls=[],
            stop_reason="end_turn",
            input_tokens=usage.get("input_tokens", _estimate_tokens(payload.message)),
            output_tokens=usage.get(
                "output_tokens", _estimate_tokens(response_text)
            ),
            cache_read_tokens=0,
            cache_creation_tokens=0,
            latency_ms=latency_ms,
        )

        publish_final_output(
            output_text=response_text,
            final_grade=None,
            judge_dimensions={},
        )

    return ChatResponse(session_id=trace_id, response=response_text, charts=charts)


@router.post("/stream")
def chat_stream_endpoint(payload: ChatRequest) -> StreamingResponse:
    """Stream agent events as Server-Sent Events (text/event-stream).

    The client reads the stream with ``fetch()`` and parses each ``data:`` line
    as JSON.  Events are typed via the ``type`` field; see ``stream_events.py``
    for the full schema.
    """
    from app.api.settings_api import get_settings

    conversation_id = payload.session_id
    if conversation_id is not None and not _CONVERSATION_ID_RE.match(conversation_id):
        raise HTTPException(status_code=400, detail="invalid session_id")

    settings = get_settings()
    model_id = settings.model
    trace_id = _make_trace_id(conversation_id)

    session_bootstrap = (
        build_duckdb_globals(trace_id, payload.dataset_path)
        if payload.dataset_path
        else ""
    )

    def event_generator() -> Generator[str, None, None]:
        yield from _stream_agent_loop(
            model_id=model_id,
            message=payload.message,
            session_id=trace_id,
            session_bootstrap=session_bootstrap,
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
