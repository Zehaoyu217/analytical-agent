from __future__ import annotations

import logging
import uuid
from typing import Any

from app.harness.clients.base import (
    CompletionRequest,
    CompletionResponse,
    ToolCall,
)
from app.harness.config import ModelProfile

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, profile: ModelProfile, http: Any) -> None:
        self.profile = profile
        self.name = profile.name
        self.tier = profile.tier
        self._http = http

    def _endpoint(self, path: str) -> str:
        host = (self.profile.host or "http://localhost:11434").rstrip("/")
        return f"{host}{path}"

    def _options(self, request: CompletionRequest) -> dict[str, Any]:
        opts = dict(self.profile.options)
        if self.profile.num_ctx is not None:
            opts["num_ctx"] = self.profile.num_ctx
        if request.max_tokens:
            opts["num_predict"] = request.max_tokens
        if request.temperature is not None:
            opts["temperature"] = request.temperature
        return opts

    def _payload(self, request: CompletionRequest) -> dict[str, Any]:
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for m in request.messages:
            if m.role == "tool":
                messages.append({"role": "tool", "content": m.content, "name": m.name or ""})
            else:
                messages.append({"role": m.role, "content": m.content})
        payload: dict[str, Any] = {
            "model": self.profile.model_id,
            "messages": messages,
            "stream": False,
            "options": self._options(request),
        }
        if self.profile.keep_alive:
            payload["keep_alive"] = self.profile.keep_alive
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
        return payload

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        resp = self._http.post(self._endpoint("/api/chat"), json=self._payload(request))
        if resp.status_code != 200:
            raise RuntimeError(f"ollama HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        message = data.get("message") or {}
        text = str(message.get("content", ""))
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                import json as _json
                try:
                    args = _json.loads(args)
                except Exception:
                    args = {"_raw": args}
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or uuid.uuid4().hex),
                    name=str(fn.get("name", "")),
                    arguments=dict(args),
                )
            )
        stop_reason = "tool_use" if tool_calls else "end_turn"
        return CompletionResponse(
            text=text,
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage={
                "input_tokens": int(data.get("prompt_eval_count", 0)),
                "output_tokens": int(data.get("eval_count", 0)),
            },
            raw=data,
        )

    def warmup(self) -> None:
        payload = {
            "model": self.profile.model_id,
            "messages": [{"role": "user", "content": "ok"}],
            "stream": False,
            "keep_alive": self.profile.keep_alive or "30m",
            "options": {"num_predict": 1},
        }
        try:
            self._http.post(self._endpoint("/api/chat"), json=payload, timeout=300)
        except Exception as exc:
            logger.warning(
                "ollama warmup failed for model %s: %s", self.profile.model_id, exc, exc_info=True
            )
