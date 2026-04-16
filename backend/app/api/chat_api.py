"""Chat endpoint with the wired-up data-scientist harness.

The agent uses the full PreTurnInjector system prompt (data_scientist.md +
operational state from the wiki + skill menu + statistical gotchas), and a
ToolDispatcher carrying the complete tool catalog (sandbox + skills + wiki +
artifacts + A2A delegation).

POST /api/chat        — synchronous JSON response (back-compat surface)
POST /api/chat/stream — SSE stream consumed by the frontend right panel
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

from app.artifacts.events import get_event_bus
from app.config import get_config
from app.core.home import traces_path
from app.context.manager import ContextLayer, session_registry
from app.data.db_init import get_data_context
from app.harness.a2a import register_delegate_tool
from app.harness.clients.anthropic_client import AnthropicClient
from app.harness.clients.base import (
    CompletionRequest,
    Message,
    ModelClient,
    ToolSchema,
)
from app.harness.clients.fallback_client import FallbackModelClient
from app.harness.clients.ollama_client import OllamaClient
from app.harness.clients.openrouter_client import OpenRouterClient
from app.harness.config import ModelProfile
from app.harness.dispatcher import ToolDispatcher
from app.harness.hooks import HookRunner
from app.harness.injector import InjectorInputs, TokenBudget
from app.harness.loop import AgentLoop
from app.harness.sandbox import SandboxExecutor
from app.harness.sandbox_bootstrap import build_duckdb_globals
from app.harness.skill_tools import register_core_tools
from app.harness.stream_events import sse_line
from app.harness.turn_state import TurnState
from app.harness.wiring import (
    get_artifact_store,
    get_pre_turn_injector,
    get_session_db,
    get_skill_registry,
    get_wiki_engine,
    get_wiki_wrap_up_adapter,
)
from app.harness.wrap_up import TurnWrapUp
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
_DEFAULT_MAX_STEPS = 20

# ── chart capture suffix (run after every sandbox call) ──────────────────────

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
_ARTIFACT_MARKER_RE = re.compile(r"\n?__SAVED_ARTIFACT__(.*?)__END_SAVED_ARTIFACT__\n?", re.DOTALL)


def _strip_charts(stdout: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract Vega-Lite specs emitted by the chart-capture suffix."""
    charts: list[dict[str, Any]] = []
    for match in _VEGA_MARKER_RE.finditer(stdout):
        with contextlib.suppress(Exception):
            charts.append(json.loads(match.group(1).strip()))
    cleaned = _VEGA_MARKER_RE.sub("", stdout).strip()
    return cleaned, charts


def _strip_sandbox_artifacts(stdout: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract save_artifact payloads emitted by the sandbox save_artifact function."""
    artifacts: list[dict[str, Any]] = []
    for match in _ARTIFACT_MARKER_RE.finditer(stdout):
        with contextlib.suppress(Exception):
            artifacts.append(json.loads(match.group(1).strip()))
    cleaned = _ARTIFACT_MARKER_RE.sub("", stdout).strip()
    return cleaned, artifacts


# ── tool schemas advertised to the LLM ───────────────────────────────────────
#
# The data-scientist prompt drives the agent through the sandbox: it imports
# correlate/profile/validate as Python functions and runs them inline. The
# explicit `correlation.correlate` etc. handlers are still registered on the
# dispatcher so the agent CAN call them directly when convenient, but only the
# orchestration tools are advertised in the LLM tool menu — keeping the menu
# focused and the tokens small.

_EXECUTE_PYTHON = ToolSchema(
    name="execute_python",
    description=(
        "Run a focused Python block in the analytical sandbox. Pre-imported: "
        "numpy as np, pandas as pd, altair as alt, duckdb. "
        "`df` is None unless the user uploaded a file — always load tables with "
        "`conn.execute('SELECT * FROM tablename').df()`. "
        "The read-only DuckDB `conn` has: transactions, accounts, customers, "
        "loans, daily_rates, bank_macro_panel, bank_segment_revenue, bank_wide. "
        "Skills available as functions — call signature examples: "
        "`profile(conn.execute('SELECT * FROM loans').df(), name='loans_v1')`, "
        "`find_anomalies(df_slice, method='iqr')`. "
        "Other skill functions: correlate, compare, validate, characterize, "
        "decompose, find_changepoints, lag_correlate, fit, plus chart helpers "
        "(bar, multi_line, histogram, scatter_trend, boxplot, "
        "correlation_heatmap). Assign Altair charts to a variable — they are "
        "auto-captured. print() output is returned."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
        },
        "required": ["code"],
    },
)

_WRITE_WORKING = ToolSchema(
    name="write_working",
    description=(
        "Persist the working scratchpad (working.md) for this session. Use "
        "markdown sections: ## TODO, ## COT, ## Findings, ## Evidence. Append "
        "to COT — never erase prior thoughts. Findings need ID + artifact "
        "citation + validation tag (see system prompt for the exact format)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Full markdown for working.md"},
        },
        "required": ["content"],
    },
)

_LOAD_SKILL = ToolSchema(
    name="skill",
    description=(
        "Load the full SKILL.md body for a skill from the menu. Returns the "
        "skill's instructions so you can use it correctly. Use this BEFORE "
        "invoking a skill you have not used before in this session."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name from the menu"},
        },
        "required": ["name"],
    },
)

_SAVE_ARTIFACT = ToolSchema(
    name="save_artifact",
    description=(
        "Save an artifact (table, chart spec, report, etc.) to the session "
        "store. Returns an artifact_id you can cite from findings."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["table", "chart", "report", "analysis"]},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "content": {"type": "string"},
            "format": {"type": "string"},
        },
        "required": ["type", "title", "content"],
    },
)

_PROMOTE_FINDING = ToolSchema(
    name="promote_finding",
    description=(
        "Promote a validated finding to the wiki (knowledge/wiki/findings/). "
        "Requires evidence_ids and a stat_validate PASS verdict."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "finding_id": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "validated": {"type": "boolean"},
        },
        "required": ["finding_id", "body", "evidence_ids"],
    },
)

_DELEGATE_SUBAGENT = ToolSchema(
    name="delegate_subagent",
    description=(
        "Spawn a focused sub-agent for a self-contained task (bulk retrieval, "
        "long tails, anything that would bloat the parent context). The "
        "sub-agent runs independently and returns {artifact_id, summary, steps}."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Task description"},
            "tools_allowed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Subset of parent tool names the child may call",
            },
        },
        "required": ["task"],
    },
)

_TODO_WRITE = ToolSchema(
    name="todo_write",
    description=(
        "Declare or update the session task list. Replaces the full list "
        "(think about the whole plan each time — not incremental diffs). "
        "Each item needs a short id, a clear action-oriented content line, "
        "and a status of pending / in_progress / completed. Use exactly ONE "
        "in_progress item at a time so the human can see where you are."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                    },
                    "required": ["id", "content", "status"],
                },
            },
        },
        "required": ["todos"],
    },
)

_GET_CONTEXT_STATUS = ToolSchema(
    name="get_context_status",
    description=(
        "Return the current context window utilization for this session. "
        "Use when you need to know how much context budget remains before "
        "deciding whether to run a long analysis or compress working memory."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)

_READ_FILE = ToolSchema(
    name="read_file",
    description=(
        "Read the content of a file relative to the project root. "
        "Use to inspect skill code, docs, dataset files, or config. "
        "Returns content as a string and line count."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to project root"},
        },
        "required": ["path"],
    },
)

_GLOB_FILES = ToolSchema(
    name="glob_files",
    description=(
        "List files matching a glob pattern relative to the project root. "
        "Use to discover skill packages, find config files, or enumerate datasets. "
        "Returns up to 200 results."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. 'backend/app/skills/**/*.py'"},
        },
        "required": ["pattern"],
    },
)

_SEARCH_TEXT = ToolSchema(
    name="search_text",
    description=(
        "Search for a regex pattern in files under a directory. "
        "Use to find function definitions, skill names, or dataset columns. "
        "Returns up to 50 matches with file path, line number, and matched text."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory to search in (relative to project root)"},
        },
        "required": ["pattern"],
    },
)

_CHAT_TOOLS: tuple[ToolSchema, ...] = (
    _EXECUTE_PYTHON,
    _WRITE_WORKING,
    _LOAD_SKILL,
    _SAVE_ARTIFACT,
    _PROMOTE_FINDING,
    _DELEGATE_SUBAGENT,
    _TODO_WRITE,
    _GET_CONTEXT_STATUS,
    _READ_FILE,
    _GLOB_FILES,
    _SEARCH_TEXT,
)

# Read-only / non-mutating tools. Plan Mode narrows the tool menu to this set
# so the model cannot accidentally execute code or write artifacts while
# producing a plan — belt-and-braces alongside the system-prompt instruction.
_PLAN_MODE_TOOL_NAMES: frozenset[str] = frozenset({
    "skill",
    "write_working",
    "todo_write",
})


def filter_tools_for_plan_mode(
    tools: tuple[ToolSchema, ...] | list[ToolSchema],
) -> tuple[ToolSchema, ...]:
    """Return only the tools safe to expose while the agent is in Plan Mode.

    Drops anything that executes code, writes artifacts, promotes findings, or
    spawns sub-agents. The agent is left with enough to plan (skills to read,
    working-md to sketch, todos to declare) but not to mutate state.

    The allowed set is read from ``config/toolsets.yaml`` (``planning`` toolset)
    when available; falls back to the hardcoded ``_PLAN_MODE_TOOL_NAMES`` frozenset.
    """
    try:
        from app.harness.wiring import get_toolset_resolver  # noqa: PLC0415
        planning_tools = get_toolset_resolver().resolve("planning")
    except Exception:  # noqa: BLE001
        planning_tools = _PLAN_MODE_TOOL_NAMES
    return tuple(t for t in tools if t.name in planning_tools)

# ── prompt assembly ───────────────────────────────────────────────────────────


def _build_system_prompt(
    active_profile_summary: str | None = None,
    plan_mode: bool = False,
    session_id: str = "",
) -> str:
    """Assemble the full data-scientist system prompt for this turn."""
    injector = get_pre_turn_injector()
    inputs = InjectorInputs(
        active_profile_summary=active_profile_summary,
        token_budget=TokenBudget(),
        plan_mode=plan_mode,
        session_id=session_id,
    )
    base = injector.build(inputs)
    data_ctx = get_data_context()
    if data_ctx:
        base = base + "\n\n## Live Data Context\n\n" + data_ctx
    return base


# _SYSTEM_PROMPT is no longer eagerly built at import time — that triggered a
# full singleton init (skill-tree walk, wiki file reads) on every worker
# start for zero benefit, since both chat endpoints always call
# _get_system_prompt() per-turn anyway.
#
# prompts_api now calls _build_system_prompt() directly for its devtools view.


def _get_system_prompt(plan_mode: bool = False, session_id: str = "") -> str:
    """Build a fresh system prompt for each turn (wiki state changes)."""
    return _build_system_prompt(plan_mode=plan_mode, session_id=session_id)


# ── model factory ─────────────────────────────────────────────────────────────


def _openrouter_fallback_models() -> list[str]:
    """Ordered list of OpenRouter model ids to retry on 429.

    Source: ``OPENROUTER_FALLBACK_MODELS`` env var, comma-separated. Entries
    are stripped and empties dropped. When unset, no fallback occurs.
    """
    raw = os.environ.get("OPENROUTER_FALLBACK_MODELS", "").strip()
    if not raw:
        return []
    return [m for m in (p.strip() for p in raw.split(",")) if m]


def _make_client(model_id: str, http: httpx.Client) -> ModelClient:
    config = get_config()
    if model_id.startswith("claude-"):
        profile = ModelProfile(
            name=model_id, provider="anthropic", model_id=model_id, tier="advisory",
        )
        return AnthropicClient(profile, anthropic.Anthropic())  # type: ignore[return-value]
    if "/" in model_id:
        primary = _make_openrouter_client(model_id, config.openrouter_api_key, http)
        fallback_ids = [
            fid for fid in _openrouter_fallback_models() if fid != model_id
        ]
        if not fallback_ids:
            return primary
        fallbacks = [
            _make_openrouter_client(fid, config.openrouter_api_key, http)
            for fid in fallback_ids
        ]
        return FallbackModelClient(primary, fallbacks)  # type: ignore[return-value]
    profile = ModelProfile(
        name=model_id, provider="ollama", model_id=model_id,
        tier="advisory", host=config.ollama_base_url,
    )
    return OllamaClient(profile, http)  # type: ignore[return-value]


def _make_openrouter_client(
    model_id: str, api_key: str, http: httpx.Client,
) -> OpenRouterClient:
    profile = ModelProfile(
        name=model_id, provider="openrouter", model_id=model_id,
        tier="advisory", host="https://openrouter.ai/api/v1",
        options={"api_key": api_key},
    )
    return OpenRouterClient(profile, http)


# ── dispatcher wiring ─────────────────────────────────────────────────────────


def _to_frontend_artifact(content: str, fmt: str, artifact_type: str) -> tuple[str, str]:
    """Convert save_artifact content/format to a frontend-renderable (content, format) pair.

    Returns ("", "") when the content is clearly a placeholder or unparseable.
    """
    import csv as _csv
    import io as _io
    stripped = content.strip()
    # Reject obvious placeholder strings produced by confused models
    if not stripped or stripped in ("result", "<chart placeholder>", "None", "nan"):
        return "", ""

    if fmt in ("vega-lite", "vega"):
        try:
            json.loads(stripped)  # validate it's real JSON
            return stripped, "vega-lite"
        except Exception:
            return "", ""
    if fmt == "mermaid":
        return stripped, "mermaid"
    if fmt == "table-json":
        return stripped, "table-json"
    if fmt == "csv" and artifact_type == "table":
        try:
            reader = _csv.DictReader(_io.StringIO(stripped))
            rows_raw = list(reader)
            if not rows_raw:
                return stripped, "csv"
            columns = list(rows_raw[0].keys())
            rows = [[row.get(c, "") for c in columns] for row in rows_raw]
            table_json = json.dumps({"columns": columns, "rows": rows, "total_rows": len(rows)})
            return table_json, "table-json"
        except Exception:
            return stripped, "csv"
    if fmt in ("json",):
        try:
            data = json.loads(stripped)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                columns = list(data[0].keys())
                rows = [[row.get(c) for c in columns] for row in data]
                table_json = json.dumps({"columns": columns, "rows": rows, "total_rows": len(rows)})
                return table_json, "table-json"
            if isinstance(data, dict) and "columns" in data:
                return stripped, "table-json"
        except Exception:
            pass
    # Fallback: show raw content as text
    if len(stripped) > 4:
        return stripped, "text"
    return "", ""


def _build_dispatcher(
    session_id: str,
    session_bootstrap: str,
    charts_out: list[dict[str, Any]],
    outputs_out: dict[str, str],
    saved_artifacts_out: list[dict[str, Any]],
    client: ModelClient,
) -> ToolDispatcher:
    """Build a fully-wired dispatcher for one chat turn.

    Side-effects:
    * ``charts_out``  — appended every time execute_python emits Vega-Lite
    * ``outputs_out["latest"]`` — last execute_python stdout (for SSE injection)
    * ``saved_artifacts_out`` — appended every time save_artifact stores a renderable artifact
    """
    dispatcher = ToolDispatcher()

    sandbox = SandboxExecutor(
        python_executable=sys.executable,
        timeout_sec=30,
        extra_globals_script=session_bootstrap,
    )
    artifact_store = get_artifact_store()
    wiki = get_wiki_engine()
    skill_registry = get_skill_registry()

    from app.artifacts.models import Artifact as _Artifact

    register_core_tools(
        dispatcher=dispatcher,
        artifact_store=artifact_store,
        wiki=wiki,
        sandbox=sandbox,
        session_id=session_id,
        registry=skill_registry,
        session_db=get_session_db(),
    )

    # Override `sandbox.run` with a chart- and artifact-capturing variant exposed
    # under the LLM-facing `execute_python` name.
    def _execute_python(args: dict[str, Any]) -> dict[str, Any]:
        code = str(args.get("code", ""))
        result = sandbox.run(code + "\n\n" + _CHART_CAPTURE_SUFFIX)
        cleaned, charts = _strip_charts(result.stdout)
        cleaned, raw_artifacts = _strip_sandbox_artifacts(cleaned)
        charts_out.extend(charts)
        outputs_out["latest"] = cleaned
        # Persist sandbox save_artifact() payloads and queue for SSE emission.
        for raw in raw_artifacts:
            fe_content, fe_format = _to_frontend_artifact(
                raw.get("content", ""), raw.get("format", "text"), raw.get("type", "analysis")
            )
            if fe_content:
                art = _Artifact(
                    type=raw.get("type", "analysis"),
                    title=raw.get("title", "Artifact"),
                    description="",
                    content=fe_content,
                    format=fe_format,
                )
                saved = artifact_store.add_artifact(session_id, art)
                saved_artifacts_out.append({
                    "id": saved.id,
                    "title": saved.title or f"{saved.type} {saved.id}",
                    "type": saved.type,
                    "format": fe_format,
                    "content": fe_content,
                    "session_id": session_id,
                    "created_at": time.time(),
                })
        if not result.ok:
            err = result.stderr.strip()
            return {
                "ok": False,
                "output": cleaned,
                "error": err or "non-zero exit",
                "charts_rendered": len(charts),
            }
        return {
            "ok": True,
            "output": cleaned or "(no output)",
            "charts_rendered": len(charts),
        }

    dispatcher.register("execute_python", _execute_python, override=True)
    register_delegate_tool(
        dispatcher=dispatcher,
        client=client,
        parent_session_id=session_id,
    )

    # In-session task tracking (P19) — TodoWrite-style list scoped to
    # ``session_id`` so the frontend can display the agent's current plan.
    from app.harness.todo_store import get_todo_store

    todo_store = get_todo_store()

    def _todo_write_handler(args: dict[str, Any]) -> dict[str, Any]:
        raw = args.get("todos")
        if not isinstance(raw, list):
            return {"ok": False, "error": "'todos' must be an array"}
        try:
            stored = todo_store.replace(session_id, raw)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "count": len(stored),
            "todos": [t.to_dict() for t in stored],
        }

    dispatcher.register("todo_write", _todo_write_handler)

    # Override save_artifact to capture renderable artifacts for SSE emission.
    # register_core_tools already registered the base handler; we replace it here
    # so saved_artifacts_out is populated without touching skill_tools.py.
    def _save_artifact_capturing(args: dict[str, Any]) -> dict[str, Any]:
        content = args["content"]
        if not isinstance(content, str):
            content = str(content)
        art = _Artifact(
            type=args.get("type", "table"),
            title=args.get("title", ""),
            description=args.get("summary", args.get("description", "")),
            content=content,
            format=args.get("format", args.get("mime_type", "html")),
        )
        saved = artifact_store.add_artifact(session_id, art)
        fe_content, fe_format = _to_frontend_artifact(content, art.format, art.type)
        if fe_content:
            saved_artifacts_out.append({
                "id": saved.id,
                "title": saved.title or f"{saved.type} {saved.id}",
                "type": saved.type,
                "format": fe_format,
                "content": fe_content,
                "session_id": session_id,
                "created_at": __import__("time").time(),
            })
        return {"artifact_id": saved.id}

    dispatcher.register("save_artifact", _save_artifact_capturing, override=True)
    return dispatcher


# ── synchronous endpoint (back-compat) ───────────────────────────────────────


def _agent_loop_sync(
    model_id: str,
    message: str,
    session_id: str,
    session_bootstrap: str,
    max_steps: int = _DEFAULT_MAX_STEPS,
    plan_mode: bool = False,
) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    """Run the wired AgentLoop synchronously and return (text, charts, usage)."""
    charts: list[dict[str, Any]] = []
    outputs: dict[str, str] = {}
    saved_artifacts: list[dict[str, Any]] = []
    usage: dict[str, int] = {}
    tools = filter_tools_for_plan_mode(_CHAT_TOOLS) if plan_mode else _CHAT_TOOLS
    system_prompt = _get_system_prompt(plan_mode=plan_mode)

    with httpx.Client(timeout=300) as http:
        client = _make_client(model_id, http)
        dispatcher = _build_dispatcher(
            session_id=session_id,
            session_bootstrap=session_bootstrap,
            charts_out=charts,
            outputs_out=outputs,
            saved_artifacts_out=saved_artifacts,
            client=client,
        )
        loop = AgentLoop(dispatcher, hook_runner=HookRunner())
        outcome = loop.run(
            client=client,
            system=system_prompt,
            user_message=message,
            dataset_loaded=bool(session_bootstrap),
            max_steps=max_steps,
            tools=tools,
        )
        final_text = outcome.final_text
        # AgentLoop doesn't surface usage today — derive a rough estimate.
        usage = {
            "input_tokens": _estimate_tokens(message + system_prompt),
            "output_tokens": _estimate_tokens(final_text),
        }
        _run_wrap_up(outcome.turn_state, final_text, session_id, turn_index=1)
    return final_text or ("Chart rendered." if charts else ""), charts, usage


# ── streaming endpoint ───────────────────────────────────────────────────────


def _stream_agent_loop(
    model_id: str,
    message: str,
    session_id: str,
    session_bootstrap: str,
    max_steps: int = _DEFAULT_MAX_STEPS,
    plan_mode: bool = False,
) -> Generator[str, None, None]:
    """Yield SSE lines for one chat turn through the full harness.

    Events: turn_start, tool_call, tool_result, scratchpad_delta, artifact,
    a2a_start, a2a_end, turn_end, error.
    """
    charts: list[dict[str, Any]] = []
    outputs: dict[str, str] = {}
    saved_artifacts: list[dict[str, Any]] = []
    emitted_chart_count = 0
    emitted_saved_count = 0
    tools = filter_tools_for_plan_mode(_CHAT_TOOLS) if plan_mode else _CHAT_TOOLS

    # ── per-session context layers ───────────────────────────────────────────
    ctx = session_registry.get_or_create(session_id)
    sys_prompt = _get_system_prompt(plan_mode=plan_mode, session_id=session_id)
    sp_tokens = _estimate_tokens(sys_prompt)
    ctx.add_layer(ContextLayer(
        name="System Prompt", tokens=sp_tokens, compactable=False,
        items=[{"name": "data_scientist_prompt", "tokens": sp_tokens}],
    ))
    user_tokens = _estimate_tokens(message)
    ctx.add_layer(ContextLayer(
        name="User Message", tokens=user_tokens, compactable=True,
        items=[{"name": "user_turn", "tokens": user_tokens}],
    ))
    if session_bootstrap:
        boot_tokens = _estimate_tokens(session_bootstrap)
        ctx.add_layer(ContextLayer(
            name="Dataset Context", tokens=boot_tokens, compactable=True,
            items=[{"name": "dataset_bootstrap", "tokens": boot_tokens}],
        ))
    ctx.add_layer(ContextLayer(name="Assistant Turns", tokens=0, compactable=True, items=[]))
    ctx.add_layer(ContextLayer(name="Tool Results", tokens=0, compactable=True, items=[]))
    assistant_tokens = 0
    tool_result_tokens = 0
    # Running item lists so the devtools inspector shows ALL tools/turns, not
    # just the last one.  ContextManager.add_layer replaces by name, which
    # previously wiped the items list on every update.
    tool_items: list[dict[str, Any]] = []
    assistant_items: list[dict[str, Any]] = []

    final_outcome_state: TurnState | None = None
    final_text = ""

    try:
        with httpx.Client(timeout=300) as http:
            client = _make_client(model_id, http)
            dispatcher = _build_dispatcher(
                session_id=session_id,
                session_bootstrap=session_bootstrap,
                charts_out=charts,
                outputs_out=outputs,
                saved_artifacts_out=saved_artifacts,
                client=client,
            )

            # get_context_status closes over `ctx` so it returns live data
            # for this specific session. Registered after _build_dispatcher
            # because ctx is only in scope here.
            def _ctx_status_handler(args: dict[str, Any]) -> dict[str, Any]:
                snap = ctx.snapshot()
                return {
                    "total_tokens": snap["total_tokens"],
                    "max_tokens": snap["max_tokens"],
                    "utilization_pct": round(snap["utilization"] * 100),
                    "compaction_needed": snap["compaction_needed"],
                    "layers": [
                        {"name": lyr["name"], "tokens": lyr["tokens"]}
                        for lyr in snap["layers"]
                    ],
                }

            dispatcher.register("get_context_status", _ctx_status_handler)

            loop = AgentLoop(dispatcher, hook_runner=HookRunner())

            # We need the TurnState that AgentLoop builds internally so we can
            # hand it to TurnWrapUp afterward. AgentLoop.run_stream() doesn't
            # expose it, so we capture state via the scratchpad_delta + artifact
            # events we already see streaming through.
            captured_state = TurnState(dataset_loaded=bool(session_bootstrap))

            for event in loop.run_stream(
                client=client,
                system=sys_prompt,
                user_message=message,
                dataset_loaded=bool(session_bootstrap),
                session_id=session_id,
                max_steps=max_steps,
                tools=tools,
            ):
                if event.type == "scratchpad_delta":
                    captured_state.scratchpad = str(event.payload.get("content", ""))

                if event.type == "micro_compact":
                    ctx.record_compaction(
                        tokens_before=event.payload.get("tokens_before", 0),
                        tokens_after=event.payload.get("tokens_after", 0),
                        removed=[
                            {"name": f"compacted_tool_{i}"}
                            for i in range(event.payload.get("dropped_messages", 0))
                        ],
                        survived=list(event.payload.get("artifact_refs", [])),
                    )

                if event.type == "tool_result":
                    name = event.payload.get("name", "")
                    status = event.payload.get("status", "ok")
                    captured_state.record_tool(
                        name=name,
                        result_payload={"preview": event.payload.get("preview", "")},
                        status=status,
                    )
                    for aid in event.payload.get("artifact_ids", []) or []:
                        captured_state.record_artifact(str(aid))

                    # Emit fresh chart artifacts produced by execute_python.
                    while emitted_chart_count < len(charts):
                        spec = charts[emitted_chart_count]
                        artifact_id = f"chart-{secrets.token_hex(4)}"
                        title = spec.get("title", "Chart")
                        if not isinstance(title, str):
                            title = "Chart"
                        yield sse_line("artifact", {
                            "id": artifact_id,
                            "type": "artifact",
                            "artifact_type": "chart",
                            "title": title,
                            "format": "vega-lite",
                            "artifact_content": json.dumps(spec),
                            "session_id": session_id,
                            "created_at": time.time(),
                            "artifact_metadata": {},
                        })
                        emitted_chart_count += 1

                    # Emit table/report artifacts saved via save_artifact tool.
                    while emitted_saved_count < len(saved_artifacts):
                        sa = saved_artifacts[emitted_saved_count]
                        yield sse_line("artifact", {
                            "id": sa["id"],
                            "type": "artifact",
                            "artifact_type": sa["type"],
                            "title": sa["title"],
                            "format": sa["format"],
                            "artifact_content": sa["content"],
                            "session_id": sa["session_id"],
                            "created_at": sa["created_at"],
                            "artifact_metadata": {},
                        })
                        emitted_saved_count += 1

                    # Update Tool Results context layer, accumulating all items
                    # so the devtools inspector shows the full tool history.
                    result_text = json.dumps(event.payload)
                    item_tokens = _estimate_tokens(result_text)
                    tool_result_tokens += item_tokens
                    tool_items.append({"name": name or "tool", "tokens": item_tokens})
                    ctx.add_layer(ContextLayer(
                        name="Tool Results", tokens=tool_result_tokens,
                        compactable=True,
                        items=list(tool_items),
                    ))
                elif event.type == "turn_end":
                    final_text = event.payload.get("final_text", "") or ""
                    if final_text:
                        turn_tokens = _estimate_tokens(str(final_text))
                        assistant_tokens += turn_tokens
                        assistant_items.append({
                            "name": "assistant_response",
                            "tokens": turn_tokens,
                        })
                        ctx.add_layer(ContextLayer(
                            name="Assistant Turns", tokens=assistant_tokens,
                            compactable=True,
                            items=list(assistant_items),
                        ))

                if event.type == "turn_end":
                    yield sse_line("turn_end", {**event.payload, "charts": charts})
                elif event.type == "tool_result" and event.payload.get("name") == "execute_python":
                    augmented = {**event.payload, "stdout": outputs.get("latest", "")}
                    yield sse_line("tool_result", augmented)
                else:
                    yield event.to_sse()

            final_outcome_state = captured_state
    except Exception as exc:
        logger.error("stream_agent_loop failed: %s", exc, exc_info=True)
        yield sse_line("error", {"message": str(exc)})
        return

    if final_outcome_state is not None:
        try:
            _run_wrap_up(final_outcome_state, final_text, session_id, turn_index=1)
        except Exception as exc:
            logger.warning("turn wrap-up skipped: %s", exc)


def _run_wrap_up(
    state: TurnState, final_text: str, session_id: str, turn_index: int,
) -> None:
    """Hand the completed turn to TurnWrapUp for memory consolidation."""
    wiki = get_wiki_wrap_up_adapter()
    bus = get_event_bus()

    class _BusAdapter:
        def __init__(self, bus_inst: Any) -> None:
            self._bus = bus_inst

        def emit(self, event: dict) -> None:
            etype = event.get("type", "turn_completed")
            self._bus.emit(etype, event)

    wrap = TurnWrapUp(wiki=wiki, event_bus=_BusAdapter(bus))
    wrap.finalize(
        state=state,
        final_text=final_text,
        session_id=session_id,
        turn_index=turn_index,
    )
    # Run Stop hooks after the turn is fully wrapped up.
    try:
        HookRunner().run_stop(session_id)
    except Exception:
        pass


# ── HTTP layer ───────────────────────────────────────────────────────────────


def _traces_dir() -> Path:
    raw = os.environ.get("TRACE_DIR")
    return Path(raw) if raw else traces_path()


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
    dataset_path: str | None = Field(default=None)
    plan_mode: bool = Field(
        default=False,
        description=(
            "When true, the agent plans only — execute_python, save_artifact, "
            "promote_finding, and delegate_subagent are removed from the tool "
            "menu and the system prompt instructs the model to propose a plan "
            "and wait for user approval before acting."
        ),
    )


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
        session_id=trace_id, level=1, level_label="chat",
        input_query=payload.message, trace_mode="always", output_dir=output_dir,
        session_db=get_session_db(),
    ):
        try:
            session_bootstrap = build_duckdb_globals(trace_id, payload.dataset_path, registry=get_skill_registry())
            response_text, charts, usage = _agent_loop_sync(
                model_id=model_id,
                message=payload.message,
                session_id=trace_id,
                session_bootstrap=session_bootstrap,
                plan_mode=payload.plan_mode,
            )
        except Exception as exc:
            logger.error("agent loop failed for model %s: %s", model_id, exc, exc_info=True)
            response_text = f"[{model_id} error] {exc}"
            charts = []
            usage = {}

        latency_ms = int((time.monotonic() - started) * 1000)

        publish_llm_call(
            step_id="s1", turn=1, model=model_id, temperature=0.0, max_tokens=4096,
            prompt_text=payload.message,
            sections=[
                PromptSection(source="user_query", lines="1-1", text=payload.message),
            ],
            response_text=response_text,
            tool_calls=[], stop_reason="end_turn",
            input_tokens=usage.get("input_tokens", _estimate_tokens(payload.message)),
            output_tokens=usage.get(
                "output_tokens", _estimate_tokens(response_text)
            ),
            cache_read_tokens=0, cache_creation_tokens=0,
            latency_ms=latency_ms,
        )
        publish_final_output(
            output_text=response_text, final_grade=None, judge_dimensions={},
        )

    return ChatResponse(session_id=trace_id, response=response_text, charts=charts)


@router.post("/stream")
def chat_stream_endpoint(payload: ChatRequest) -> StreamingResponse:
    from app.api.settings_api import get_settings

    conversation_id = payload.session_id
    if conversation_id is not None and not _CONVERSATION_ID_RE.match(conversation_id):
        raise HTTPException(status_code=400, detail="invalid session_id")

    settings = get_settings()
    model_id = settings.model
    trace_id = _make_trace_id(conversation_id)
    session_bootstrap = build_duckdb_globals(trace_id, payload.dataset_path, registry=get_skill_registry())
    output_dir = _traces_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    def event_generator() -> Generator[str, None, None]:
        # Wrap streaming in a TraceSession so DevTools can load timeline/prompt
        # for the current session. Without this, /api/trace/traces/{id}/...
        # returns 404 because no trace file is ever written.
        with TraceSession(
            session_id=trace_id,
            level=1,
            level_label="chat",
            input_query=payload.message,
            trace_mode="always",
            output_dir=output_dir,
            session_db=get_session_db(),
        ):
            final_text = ""
            for line in _stream_agent_loop(
                model_id=model_id,
                message=payload.message,
                session_id=trace_id,
                session_bootstrap=session_bootstrap,
                plan_mode=payload.plan_mode,
            ):
                # Best-effort: capture final_text from the turn_end SSE event
                # so we can publish an llm_call record for the Prompt tab.
                if '"type": "turn_end"' in line:
                    with contextlib.suppress(Exception):
                        payload_data = json.loads(line.split("data: ", 1)[1])
                        final_text = payload_data.get("final_text", "") or ""
                yield line

            # publish_llm_call is now emitted per-turn by loop.py run_stream().
            # We only need to publish the final_output sentinel here.
            with contextlib.suppress(Exception):
                publish_final_output(
                    output_text=final_text, final_grade=None, judge_dimensions={},
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
