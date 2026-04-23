from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from second_brain.llm.mlx_client import complete_chat, extract_tool_payload
from second_brain.llm.providers import (
    anthropic_model_name,
    mlx_model_name,
    ollama_base_url,
    ollama_model_name,
    ollama_num_ctx,
    resolve_provider,
)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class ToolLLMError(RuntimeError):
    """Raised when a provider call fails or returns no usable tool payload."""


@dataclass(frozen=True)
class ToolLLMResult:
    tool_input: dict[str, Any]
    tokens_in: int
    tokens_out: int
    model: str


class ToolLLMClient:
    def __init__(
        self,
        model: str,
        *,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
        openrouter_key: str | None = None,
        anthropic_key: str | None = None,
        ollama_host: str | None = None,
    ) -> None:
        self.model = model
        self._timeout = timeout
        self._transport = transport
        self._openrouter_key = openrouter_key or os.environ.get("OPENROUTER_API_KEY")
        self._anthropic_key = anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
        self._ollama_host = ollama_host

    def call_tool(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> ToolLLMResult:
        provider = resolve_provider(
            self.model,
            openrouter_key=self._openrouter_key,
            anthropic_key=self._anthropic_key,
        )
        if provider == "ollama":
            return self._call_ollama(system, user, tool, max_tokens, temperature)
        if provider == "mlx":
            return self._call_mlx(system, user, tool, max_tokens, temperature)
        if provider == "openrouter":
            return self._call_openrouter(system, user, tool, max_tokens, temperature)
        return self._call_anthropic(system, user, tool, max_tokens, temperature)

    def _call_openrouter(
        self,
        system: str,
        user: str,
        tool: dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> ToolLLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "tools": [self._openai_tool(tool)],
            "tool_choice": {
                "type": "function",
                "function": {"name": tool["name"]},
            },
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._openrouter_key}",
            "Content-Type": "application/json",
        }
        body = self._post(_OPENROUTER_URL, headers=headers, payload=payload)
        try:
            message = body["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            tool_input = self._parse_openai_tool_calls(tool_calls, tool["name"])
            usage = body.get("usage") or {}
            return ToolLLMResult(
                tool_input=tool_input,
                tokens_in=int(usage.get("prompt_tokens", 0)),
                tokens_out=int(usage.get("completion_tokens", 0)),
                model=str(body.get("model", self.model)),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ToolLLMError(f"malformed openrouter response: {exc}") from exc

    def _call_anthropic(
        self,
        system: str,
        user: str,
        tool: dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> ToolLLMResult:
        bare_model = anthropic_model_name(self.model)
        payload = {
            "model": bare_model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": tool["name"]},
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
            blocks = body.get("content") or []
            for block in blocks:
                if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
                    usage = body.get("usage") or {}
                    return ToolLLMResult(
                        tool_input=dict(block.get("input") or {}),
                        tokens_in=int(usage.get("input_tokens", 0)),
                        tokens_out=int(usage.get("output_tokens", 0)),
                        model=str(body.get("model", bare_model)),
                    )
        except (AttributeError, TypeError) as exc:
            raise ToolLLMError(f"malformed anthropic response: {exc}") from exc
        raise ToolLLMError(f"anthropic response contained no {tool['name']} tool_use")

    def _call_ollama(
        self,
        system: str,
        user: str,
        tool: dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> ToolLLMResult:
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
            "tools": [self._openai_tool(tool)],
        }
        url = f"{ollama_base_url(self._ollama_host)}/api/chat"
        body = self._post(url, headers={"Content-Type": "application/json"}, payload=payload)
        try:
            message = body.get("message") or {}
            tool_calls = message.get("tool_calls") or []
            tool_input = self._parse_openai_tool_calls(tool_calls, tool["name"])
            return ToolLLMResult(
                tool_input=tool_input,
                tokens_in=int(body.get("prompt_eval_count", 0)),
                tokens_out=int(body.get("eval_count", 0)),
                model=str(body.get("model", ollama_model_name(self.model))),
            )
        except (AttributeError, TypeError) as exc:
            raise ToolLLMError(f"malformed ollama response: {exc}") from exc

    def _call_mlx(
        self,
        system: str,
        user: str,
        tool: dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> ToolLLMResult:
        strict_system = (
            f"{system}\n\n"
            f"You must produce exactly one JSON object for the tool `{tool['name']}`. "
            "Do not emit markdown fences, analysis, or extra prose."
        )
        strict_user = (
            f"{user}\n\n"
            f"Tool name: {tool['name']}\n"
            "Return only the JSON object matching this schema. "
            "The first character of your response must be `{` and the last character must be `}`.\n"
            f"{json.dumps(tool['input_schema'], indent=2, sort_keys=True)}"
        )
        attempts = [
            strict_user,
            (
                f"{strict_user}\n\n"
                "If you drifted into prose on the first try, correct it now. "
                "Use this JSON shape and fill in the values only where the source supports them:\n"
                f"{json.dumps(self._schema_stub(tool['input_schema']), indent=2, sort_keys=True)}"
            ),
        ]
        last_error: RuntimeError | None = None
        result = None
        tool_input: dict[str, Any] | None = None
        for prompt in attempts:
            result = complete_chat(
                self.model,
                system=strict_system,
                user=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            try:
                tool_input = extract_tool_payload(result.text, tool["name"])
                break
            except RuntimeError as exc:
                last_error = exc
        if tool_input is None or result is None:
            raise ToolLLMError(str(last_error or "mlx tool call failed"))
        return ToolLLMResult(
            tool_input=tool_input,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            model=mlx_model_name(self.model),
        )

    def _post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            client_kwargs: dict[str, Any] = {"timeout": self._timeout}
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            with httpx.Client(**client_kwargs) as client:
                resp = client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise ToolLLMError(f"transport error: {exc}") from exc
        if resp.status_code >= 400:
            raise ToolLLMError(f"{resp.status_code} {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise ToolLLMError(f"non-JSON response: {exc}") from exc

    @staticmethod
    def _openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool["input_schema"],
            },
        }

    @staticmethod
    def _parse_openai_tool_calls(
        tool_calls: list[dict[str, Any]],
        expected_name: str,
    ) -> dict[str, Any]:
        for call in tool_calls:
            fn = call.get("function") or {}
            if fn.get("name") != expected_name:
                continue
            arguments = fn.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    raise ToolLLMError(f"tool call arguments were not valid JSON: {exc}") from exc
            if isinstance(arguments, dict):
                return arguments
        raise ToolLLMError(f"response contained no {expected_name} tool call")

    @classmethod
    def _schema_stub(cls, schema: dict[str, Any]) -> Any:
        schema_type = schema.get("type")
        if schema_type == "object":
            properties = schema.get("properties") or {}
            required = schema.get("required") or list(properties.keys())
            return {
                str(key): cls._schema_stub(dict(properties.get(key) or {}))
                for key in required
            }
        if schema_type == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                return [cls._schema_stub(items)]
            return []
        if schema_type == "integer":
            return 0
        if schema_type == "number":
            return 0.0
        if schema_type == "boolean":
            return False
        return ""
