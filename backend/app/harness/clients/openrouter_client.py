from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.harness.clients.base import (
    CompletionRequest,
    CompletionResponse,
    RateLimitError,
    ToolCall,
)
from app.harness.config import ModelProfile

logger = logging.getLogger(__name__)

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    """OpenAI-compatible client for OpenRouter (https://openrouter.ai)."""

    def __init__(self, profile: ModelProfile, http: Any) -> None:
        self.profile = profile
        self.name = profile.name
        self.tier = profile.tier
        self._http = http

    def _base_url(self) -> str:
        return (self.profile.host or _OPENROUTER_BASE).rstrip("/")

    def _api_key(self) -> str:
        return str(self.profile.options.get("api_key", ""))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "Analytical Agent",
        }

    def _payload(self, request: CompletionRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for m in request.messages:
            if m.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_use_id or "",
                        "content": m.content,
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                # Assistant message that made tool calls — must include tool_calls
                # so the model can correctly interpret the subsequent tool results.
                msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "type": "function",
                            "id": tc.id,
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in m.tool_calls
                    ],
                }
                messages.append(msg)
            else:
                messages.append({"role": m.role, "content": m.content})

        payload: dict[str, Any] = {
            "model": self.profile.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.reasoning_effort:
            # OpenRouter's reasoning API. Models that don't support it will
            # return 4xx which the outer retry logic drops the param on.
            payload["reasoning"] = {"effort": request.reasoning_effort}
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]
            if request.tool_choice is not None:
                payload["tool_choice"] = request.tool_choice
        return payload

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        url = f"{self._base_url()}/chat/completions"
        payload = self._payload(request)
        resp = self._http.post(url, json=payload, headers=self._headers())
        if resp.status_code == 429:
            raise RateLimitError(
                provider="openrouter",
                model=self.profile.model_id,
                detail=resp.text[:500],
            )
        # Some models reject tool_choice="required" or the reasoning param
        # with a 4xx. Retry once without the rejected params so the loop
        # keeps running instead of breaking the turn.
        if resp.status_code in (400, 422) and (
            "tool_choice" in payload or "reasoning" in payload
        ):
            logger.debug(
                "openrouter %s rejected param set (%s); retrying without "
                "reasoning + tool_choice",
                self.profile.model_id, resp.status_code,
            )
            payload.pop("tool_choice", None)
            payload.pop("reasoning", None)
            resp = self._http.post(url, json=payload, headers=self._headers())
        if resp.status_code == 429:
            raise RateLimitError(
                provider="openrouter",
                model=self.profile.model_id,
                detail=resp.text[:500],
            )
        if resp.status_code != 200:
            raise RuntimeError(f"openrouter HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = str(message.get("content") or "")
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            if isinstance(args_raw, str):
                try:
                    args: dict[str, Any] = json.loads(args_raw)
                except Exception:
                    args = {"_raw": args_raw}
            else:
                args = dict(args_raw)
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or uuid.uuid4().hex),
                    name=str(fn.get("name", "")),
                    arguments=args,
                )
            )
        finish_reason = choice.get("finish_reason", "stop")
        stop_reason = (
            "tool_use"
            if tool_calls
            else ("end_turn" if finish_reason == "stop" else finish_reason)
        )
        usage = data.get("usage") or {}
        return CompletionResponse(
            text=text,
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage={
                "input_tokens": int(usage.get("prompt_tokens", 0)),
                "output_tokens": int(usage.get("completion_tokens", 0)),
            },
            raw=data,
        )

    def warmup(self) -> None:
        return
