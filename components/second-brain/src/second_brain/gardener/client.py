"""Thin LLM client adapter used by gardener passes.

Prefers OpenRouter (OpenAI-compatible) so we can swap models freely. Falls
back to Anthropic's native API for ``anthropic/*`` models when
``OPENROUTER_API_KEY`` is absent but ``ANTHROPIC_API_KEY`` is set.

The adapter is deliberately tiny: synchronous, no retries, single request
per call. The runner sits on top and handles budget, audit, and
pass-level orchestration.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from second_brain.llm.mlx_client import complete_chat
from second_brain.llm.providers import (
    anthropic_model_name,
    mlx_model_name,
    ollama_base_url,
    ollama_model_name,
    ollama_num_ctx,
    resolve_provider,
)


class LLMError(RuntimeError):
    """Raised when the upstream LLM API fails or returns an invalid body."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class LLMClient:
    """Minimal LLM client.

    Parameters
    ----------
    model:
        Fully-qualified model id (e.g. ``anthropic/claude-sonnet-4-6``).
    api_key:
        Optional override. When omitted, pulls from env.
    timeout:
        Per-request HTTP timeout (seconds).
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._timeout = timeout
        self._transport = transport
        self._openrouter_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self._ollama_host = os.environ.get("OLLAMA_HOST")

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResult:
        try:
            provider = resolve_provider(
                self.model,
                openrouter_key=self._openrouter_key,
                anthropic_key=self._anthropic_key,
            )
        except RuntimeError as exc:
            raise LLMError(str(exc)) from exc
        if provider == "ollama":
            return self._call_ollama(system, user, max_tokens, temperature)
        if provider == "mlx":
            return self._call_mlx(system, user, max_tokens, temperature)
        if provider == "openrouter":
            return self._call_openrouter(system, user, max_tokens, temperature)
        return self._call_anthropic(system, user, max_tokens, temperature)

    # ------------------------------------------------------------------
    # providers
    # ------------------------------------------------------------------

    def _call_openrouter(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._openrouter_key}",
            "Content-Type": "application/json",
        }
        body = self._post(_OPENROUTER_URL, headers=headers, payload=payload)
        try:
            text = body["choices"][0]["message"]["content"] or ""
            usage = body.get("usage") or {}
            return LLMResult(
                text=text,
                tokens_in=int(usage.get("prompt_tokens", 0)),
                tokens_out=int(usage.get("completion_tokens", 0)),
                model=str(body.get("model", self.model)),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"malformed openrouter response: {exc}") from exc

    def _call_anthropic(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> LLMResult:
        # Strip the vendor prefix for native Anthropic calls.
        bare_model = anthropic_model_name(self.model)
        payload = {
            "model": bare_model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "x-api-key": self._anthropic_key or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = self._post(_ANTHROPIC_URL, headers=headers, payload=payload)
        try:
            parts = body.get("content") or []
            text = "".join(
                p.get("text", "") for p in parts if isinstance(p, dict)
            )
            usage = body.get("usage") or {}
            return LLMResult(
                text=text,
                tokens_in=int(usage.get("input_tokens", 0)),
                tokens_out=int(usage.get("output_tokens", 0)),
                model=str(body.get("model", bare_model)),
            )
        except (KeyError, TypeError) as exc:
            raise LLMError(f"malformed anthropic response: {exc}") from exc

    def _call_ollama(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> LLMResult:
        payload = {
            "model": ollama_model_name(self.model),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "num_ctx": ollama_num_ctx(),
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        body = self._post(
            f"{ollama_base_url(self._ollama_host)}/api/chat",
            headers={"Content-Type": "application/json"},
            payload=payload,
        )
        try:
            message = body.get("message") or {}
            return LLMResult(
                text=str(message.get("content", "")),
                tokens_in=int(body.get("prompt_eval_count", 0)),
                tokens_out=int(body.get("eval_count", 0)),
                model=str(body.get("model", ollama_model_name(self.model))),
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise LLMError(f"malformed ollama response: {exc}") from exc

    def _call_mlx(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> LLMResult:
        try:
            result = complete_chat(
                self.model,
                system=system,
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except RuntimeError as exc:
            raise LLMError(str(exc)) from exc
        return LLMResult(
            text=result.text,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            model=mlx_model_name(self.model),
        )

    # ------------------------------------------------------------------
    # transport
    # ------------------------------------------------------------------

    def _post(
        self, url: str, *, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            client_kwargs: dict[str, Any] = {"timeout": self._timeout}
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            with httpx.Client(**client_kwargs) as c:
                resp = c.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"transport error: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"{resp.status_code} {resp.text[:300]}")
        try:
            return json.loads(resp.text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"non-JSON response: {exc}") from exc
