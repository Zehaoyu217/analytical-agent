from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from second_brain.extract.schema import RECORD_CLAIMS_TOOL, validate_claim_record
from second_brain.llm.providers import model_readiness
from second_brain.llm.tool_client import ToolLLMClient

Density = str  # "sparse" | "moderate" | "dense"

DEFAULT_SMALL_MODEL = "mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit"
DEFAULT_LARGE_MODEL = "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit"
DEFAULT_LARGE_INPUT_CHARS = 24_000


@dataclass(frozen=True)
class ExtractRequest:
    body: str
    density: Density
    rubric: str
    source_id: str


@dataclass(frozen=True)
class ExtractResponse:
    claims: list[dict[str, Any]]


class ExtractorClient(Protocol):
    def extract(self, req: ExtractRequest) -> ExtractResponse: ...


class FakeExtractorClient:
    def __init__(self, *, canned: list[dict[str, Any]]) -> None:
        self._canned = canned

    def extract(self, req: ExtractRequest) -> ExtractResponse:
        return ExtractResponse(claims=list(self._canned))


_DENSITY_GUIDANCE = {
    "sparse": "Only the 1-3 most load-bearing claims.",
    "moderate": "5-10 claims covering the main thrusts.",
    "dense": "As many atomic claims as the text justifies; favor the author's phrasing.",
}

_SYSTEM_PROMPT = (
    "You extract atomic, falsifiable claims from source texts. "
    "Always call the record_claims tool. Every claim must be grounded in the given body. "
    "Prefer the author's phrasing. Do not invent citations."
)


class AutoExtractorClient:
    """Provider-aware extractor with local-first model selection."""

    def __init__(
        self,
        *,
        model: str | None = None,
        small_model: str = DEFAULT_SMALL_MODEL,
        large_model: str = DEFAULT_LARGE_MODEL,
        large_input_chars: int = DEFAULT_LARGE_INPUT_CHARS,
        max_tokens: int = 4096,
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

    def extract(self, req: ExtractRequest) -> ExtractResponse:
        client = ToolLLMClient(
            self._pick_model(req),
            transport=self._transport,
            ollama_host=self._ollama_host,
        )
        result = client.call_tool(
            system=_SYSTEM_PROMPT,
            user=self._build_user_prompt(req),
            tool=RECORD_CLAIMS_TOOL,
            max_tokens=self.max_tokens,
        )
        claims = list(result.tool_input.get("claims", []))
        for claim in claims:
            validate_claim_record(claim)
        return ExtractResponse(claims=claims)

    def _pick_model(self, req: ExtractRequest) -> str:
        candidates = [self.model] if self.model else (
            [self.large_model, self.small_model]
            if len(req.body) >= self.large_input_chars
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
        raise RuntimeError("no extractor model available:\n- " + "\n- ".join(reasons))

    @staticmethod
    def _build_user_prompt(req: ExtractRequest) -> str:
        density_hint = _DENSITY_GUIDANCE.get(req.density, _DENSITY_GUIDANCE["moderate"])
        return (
            f"Source id: {req.source_id}\n"
            f"Extraction density: {req.density} - {density_hint}\n"
            f"Rubric: {req.rubric or '(default)'}\n\n"
            f"BODY:\n{req.body}\n"
        )


class AnthropicClient(AutoExtractorClient):
    """Compatibility wrapper for callers that still want native Anthropic defaults."""

    def __init__(self, *, model: str = "claude-opus-4-7", max_tokens: int = 4096) -> None:
        super().__init__(model=model, max_tokens=max_tokens)
