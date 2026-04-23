from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from second_brain.llm.providers import model_readiness
from second_brain.llm.tool_client import ToolLLMClient
from second_brain.reconcile.schema import RECORD_RESOLUTION_TOOL, validate_resolution_record

DEFAULT_SMALL_MODEL = "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit"
DEFAULT_LARGE_MODEL = "mlx/NexVeridian/gemma-4-26B-A4b-it-4bit"
DEFAULT_LARGE_INPUT_CHARS = 20_000


@dataclass(frozen=True)
class ReconcileRequest:
    claim_a_id: str
    claim_a_body: str
    claim_b_id: str
    claim_b_body: str
    supports_a: str
    supports_b: str


@dataclass(frozen=True)
class ReconcileResponse:
    resolution_md: str
    applies_where: str
    primary_claim_id: str
    rationale: str = ""


class ReconcilerClient(Protocol):
    def reconcile(self, req: ReconcileRequest) -> ReconcileResponse: ...


class FakeReconcilerClient:
    def __init__(self, *, canned: dict[str, Any]) -> None:
        validate_resolution_record(canned)
        self._canned = dict(canned)

    def reconcile(self, req: ReconcileRequest) -> ReconcileResponse:
        rec = dict(self._canned)
        return ReconcileResponse(
            resolution_md=rec["resolution_md"],
            applies_where=rec["applies_where"],
            primary_claim_id=rec["primary_claim_id"],
            rationale=rec.get("rationale", ""),
        )


_SYSTEM_PROMPT = (
    "You reconcile pairs of contradicting claims. Always call record_resolution. "
    "Produce a short markdown note explaining the dimension of disagreement "
    "(scope, methodology, era, definition, interpretation, or reject if one side is wrong). "
    "Pick a primary claim that wins in the current context."
)


class AnthropicReconcilerClient:
    """Compatibility wrapper for callers that still want native Anthropic defaults."""

    def __init__(self, *, model: str = "claude-opus-4-7", max_tokens: int = 2048) -> None:
        self._client = AutoReconcilerClient(model=model, max_tokens=max_tokens)

    def reconcile(self, req: ReconcileRequest) -> ReconcileResponse:
        return self._client.reconcile(req)


class AutoReconcilerClient:
    """Provider-aware reconciler with local-first model selection."""

    def __init__(
        self,
        *,
        model: str | None = None,
        small_model: str = DEFAULT_SMALL_MODEL,
        large_model: str = DEFAULT_LARGE_MODEL,
        large_input_chars: int = DEFAULT_LARGE_INPUT_CHARS,
        max_tokens: int = 2048,
        transport: Any | None = None,
        ollama_host: str | None = None,
    ) -> None:
        self.model = model
        self.small_model = small_model
        self.large_model = large_model
        self.large_input_chars = large_input_chars
        self.max_tokens = max_tokens
        self._transport = transport
        self._ollama_host = ollama_host

    def reconcile(self, req: ReconcileRequest) -> ReconcileResponse:
        user_prompt = (
            f"# Claim A ({req.claim_a_id})\n{req.claim_a_body}\n\n"
            f"## Support for A\n{req.supports_a}\n\n"
            f"# Claim B ({req.claim_b_id})\n{req.claim_b_body}\n\n"
            f"## Support for B\n{req.supports_b}\n"
        )
        client = ToolLLMClient(
            self._pick_model(user_prompt),
            transport=self._transport,
            ollama_host=self._ollama_host,
        )
        result = client.call_tool(
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            tool=RECORD_RESOLUTION_TOOL,
            max_tokens=self.max_tokens,
        )
        rec = result.tool_input
        validate_resolution_record(rec)
        return ReconcileResponse(
            resolution_md=rec["resolution_md"],
            applies_where=rec["applies_where"],
            primary_claim_id=rec["primary_claim_id"],
            rationale=rec.get("rationale", ""),
        )

    def _pick_model(self, user_prompt: str) -> str:
        candidates = [self.model] if self.model else (
            [self.large_model, self.small_model]
            if len(user_prompt) >= self.large_input_chars
            else [self.small_model, self.large_model]
        )
        reasons: list[str] = []
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        for candidate in candidates:
            if not candidate:
                continue
            ok, reason = model_readiness(
                candidate,
                openrouter_key=openrouter_key,
                anthropic_key=anthropic_key,
                ollama_host=self._ollama_host,
                transport=self._transport,
            )
            if ok:
                return candidate
            reasons.append(f"{candidate}: {reason}")
        raise RuntimeError("no reconciliation model available:\n- " + "\n- ".join(reasons))
