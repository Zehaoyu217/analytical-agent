"""Smoke tests for the wired chat_api harness (P15).

These tests verify that the chat_api module boots cleanly and exposes the
full tool catalog + PreTurnInjector system prompt expected by the rest of
the stack.  They are not end-to-end streaming tests — those live under
``tests/integration``.
"""
from __future__ import annotations

import pytest

from app.api import chat_api
from app.harness.clients.base import ToolSchema
from app.harness.wiring import (
    get_pre_turn_injector,
    get_skill_registry,
    get_wiki_engine,
    get_wiki_wrap_up_adapter,
    reset_singletons_for_tests,
)


def test_chat_tools_catalog_is_full():
    """P15+ exposes the orchestration tool set; regressions shrink this list."""
    names = [t.name for t in chat_api._CHAT_TOOLS]
    assert "execute_python" in names
    assert "write_working" in names
    assert "skill" in names
    assert "save_artifact" in names
    assert "promote_finding" in names
    assert "delegate_subagent" in names
    assert "todo_write" in names  # P19


def test_each_tool_is_valid_toolschema():
    for tool in chat_api._CHAT_TOOLS:
        assert isinstance(tool, ToolSchema)
        assert tool.name
        assert tool.description
        assert isinstance(tool.input_schema, dict)


def test_system_prompt_is_assembled():
    """The system prompt must come from PreTurnInjector (not the old local
    financial-analyst string)."""
    prompt = chat_api._build_system_prompt()
    assert len(prompt) > 2000  # full prompt is ~13K chars
    # data_scientist.md signatures
    assert "working loop" in prompt.lower() or "scratchpad" in prompt.lower()
    # skill menu injected
    assert "skill" in prompt.lower()


def test_system_prompt_includes_token_budget():
    """P21: the assembled prompt must surface the context budget so the agent
    knows how aggressive compaction is and why to use artifacts."""
    prompt = chat_api._build_system_prompt()
    assert "## Context Budget" in prompt
    assert "get_artifact" in prompt
    assert "save_artifact" in prompt


def test_dispatcher_has_core_tools_registered():
    # Build a stub client — _build_dispatcher only needs it for delegate_subagent.
    from app.harness.clients.base import ModelClient

    class _NullClient(ModelClient):
        def complete(self, request):  # pragma: no cover - not actually called here
            raise NotImplementedError

    dispatcher = chat_api._build_dispatcher(
        session_id="smoke-test",
        session_bootstrap="",
        charts_out=[],
        outputs_out={},
        client=_NullClient(),  # type: ignore[abstract]
    )
    registered = set(dispatcher._handlers)
    expected = {
        "execute_python",
        "skill",
        "save_artifact",
        "write_working",
        "promote_finding",
        "delegate_subagent",
        "todo_write",
    }
    missing = expected - registered
    assert not missing, f"dispatcher missing tools: {missing}"


def test_wiring_singletons_are_idempotent():
    reset_singletons_for_tests()
    a1 = get_wiki_engine()
    a2 = get_wiki_engine()
    assert a1 is a2
    b1 = get_skill_registry()
    b2 = get_skill_registry()
    assert b1 is b2
    c1 = get_pre_turn_injector()
    c2 = get_pre_turn_injector()
    assert c1 is c2


def test_wiki_wrap_up_adapter_truncates_overlong_working():
    """WikiEngine raises on >200 line working.md; the adapter must truncate
    instead so wrap-up never crashes a turn."""
    reset_singletons_for_tests()
    adapter = get_wiki_wrap_up_adapter()
    huge = "\n".join(f"line {i}" for i in range(500))
    # Must not raise.
    adapter.update_working(huge)
    wiki = get_wiki_engine()
    stored = (wiki.root / "working.md").read_text(encoding="utf-8")
    assert stored.count("\n") < 250  # truncated
    assert "truncated:" in stored  # sentinel header


def test_wiring_respects_env_var_override(tmp_path, monkeypatch):
    """Tests can point singletons at a temp directory via env vars."""
    reset_singletons_for_tests()
    monkeypatch.setenv("CCAGENT_WIKI_ROOT", str(tmp_path / "wiki"))
    wiki = get_wiki_engine()
    assert wiki.root == tmp_path / "wiki"
    # Cleanup for later tests.
    reset_singletons_for_tests()


def test_module_imports_cleanly():
    """chat_api must import without error even when wiki or skills are absent."""
    import app.api.chat_api as m
    assert hasattr(m, "_SYSTEM_PROMPT")
    assert isinstance(m._SYSTEM_PROMPT, str)
    assert len(m._SYSTEM_PROMPT) > 10


def test_get_context_status_in_chat_tools():
    from app.api.chat_api import _CHAT_TOOLS
    names = [t.name for t in _CHAT_TOOLS]
    assert "get_context_status" in names


def test_ctx_status_handler_returns_correct_shape():
    from app.context.manager import ContextManager, ContextLayer
    ctx = ContextManager()
    ctx.add_layer(ContextLayer(name="System Prompt", tokens=1200, compactable=False, items=[]))
    ctx.add_layer(ContextLayer(name="User Message", tokens=300, compactable=True, items=[]))

    def _handler(args: dict) -> dict:
        snap = ctx.snapshot()
        return {
            "total_tokens": snap["total_tokens"],
            "max_tokens": snap["max_tokens"],
            "utilization_pct": round(snap["utilization"] * 100),
            "compaction_needed": snap["compaction_needed"],
            "layers": [{"name": lyr["name"], "tokens": lyr["tokens"]} for lyr in snap["layers"]],
        }

    result = _handler({})
    assert result["total_tokens"] == 1500
    assert isinstance(result["utilization_pct"], int)
    assert len(result["layers"]) == 2
    assert result["layers"][0]["name"] == "System Prompt"


def test_fs_tools_in_chat_tools():
    from app.api.chat_api import _CHAT_TOOLS
    names = [t.name for t in _CHAT_TOOLS]
    assert "read_file" in names
    assert "glob_files" in names
    assert "search_text" in names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
