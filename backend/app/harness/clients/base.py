from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class RateLimitError(Exception):
    """Raised when an upstream provider returns a rate-limit (HTTP 429).

    Clients should raise this instead of a bare ``RuntimeError`` so the
    fallback wrapper (``FallbackModelClient``) can catch rate-limit errors
    specifically and try the next model in the chain.
    """

    def __init__(self, provider: str, model: str, detail: str = "") -> None:
        self.provider = provider
        self.model = model
        self.detail = detail
        super().__init__(
            f"{provider} rate-limited on model '{model}'"
            + (f": {detail}" if detail else "")
        )


@dataclass(frozen=True, slots=True)
class Message:
    role: str
    content: str
    name: str | None = None
    tool_use_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ToolSchema:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    system: str
    messages: tuple[Message, ...]
    tools: tuple[ToolSchema, ...] = field(default_factory=tuple)
    max_tokens: int = 4096
    temperature: float | None = None
    thinking_budget: int | None = None
    tool_choice: str | None = None  # "required", "auto", "none", or None (provider default)
    # OpenRouter reasoning effort ("low" | "medium" | "high"). Only honored by
    # models whose ``supported_parameters`` advertise ``reasoning`` (e.g.
    # openai/gpt-oss-120b). Ignored by MLX and by models without native
    # reasoning support.
    reasoning_effort: str | None = None


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    text: str
    tool_calls: tuple[ToolCall, ...]
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


@runtime_checkable
class ModelClient(Protocol):
    name: str
    tier: str

    def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    def warmup(self) -> None: ...
