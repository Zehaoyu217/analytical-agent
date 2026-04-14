from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.harness.clients.base import ToolCall

ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_use_id: str
    tool_name: str
    ok: bool
    payload: Any = None
    error_message: str = ""


class ToolDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        if name in self._handlers:
            raise ValueError(f"tool '{name}' already registered")
        self._handlers[name] = handler

    def has(self, name: str) -> bool:
        return name in self._handlers

    def get_handler(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def dispatch(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.name)
        if handler is None:
            return ToolResult(
                tool_use_id=call.id, tool_name=call.name,
                ok=False, error_message=f"unknown tool: {call.name}",
            )
        try:
            payload = handler(dict(call.arguments))
        except Exception as exc:
            return ToolResult(
                tool_use_id=call.id, tool_name=call.name,
                ok=False, error_message=f"{type(exc).__name__}: {exc}",
            )
        return ToolResult(
            tool_use_id=call.id, tool_name=call.name,
            ok=True, payload=payload,
        )
