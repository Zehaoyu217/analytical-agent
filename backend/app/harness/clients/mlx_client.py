from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from app.harness.clients.base import (
    CompletionRequest,
    CompletionResponse,
    ToolCall,
)
from app.harness.config import ModelProfile

logger = logging.getLogger(__name__)

# Xet-backed downloads have been unreliable on this machine for larger MLX models.
# Set this before importing mlx_lm / huggingface_hub so first-time pulls use the
# standard Hub transport.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

try:
    from mlx_lm import generate as _mlx_generate
    from mlx_lm import load as _mlx_load
    from mlx_lm.sample_utils import make_sampler as _mlx_make_sampler
except ImportError:
    _mlx_generate = None
    _mlx_load = None
    _mlx_make_sampler = None

_CACHE_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_CHANNEL_THOUGHT_RE = re.compile(r"<\|channel\|?>thought\b", re.IGNORECASE)
_CHANNEL_FINAL_RE = re.compile(r"<\|channel\|?>final\b", re.IGNORECASE)
_CHANNEL_CLOSE_RE = re.compile(r"<channel\|>", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
_HF_CACHE_CANDIDATES = tuple(
    path
    for path in (
        (
            Path(os.environ["HF_HUB_CACHE"]).expanduser()
            if os.environ.get("HF_HUB_CACHE")
            else None
        ),
        (
            Path(os.environ["HUGGINGFACE_HUB_CACHE"]).expanduser()
            if os.environ.get("HUGGINGFACE_HUB_CACHE")
            else None
        ),
        Path.home() / ".cache" / "huggingface" / "hub",
    )
    if path is not None
)


class MLXClient:
    def __init__(self, profile: ModelProfile) -> None:
        self.profile = profile
        self.name = profile.name
        self.tier = profile.tier

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        model_obj, tokenizer = _load_bundle(self.profile.model_id)
        max_tokens = request.max_tokens or 4096
        temperature = self._temperature(request)

        if request.tools:
            return self._complete_with_tools(
                model_obj=model_obj,
                tokenizer=tokenizer,
                request=request,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        prompt_messages = self._prompt_messages(request, repair=False)
        prompt = _build_prompt(tokenizer, prompt_messages)
        raw_text = _generate_text(
            model_obj,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = _sanitize_generated_text(raw_text)
        usage = {
            "input_tokens": _token_count(tokenizer, prompt),
            "output_tokens": _token_count(tokenizer, text),
        }
        return CompletionResponse(
            text=text,
            tool_calls=(),
            stop_reason="end_turn",
            usage=usage,
            raw={"text": text},
        )

    def _complete_with_tools(
        self,
        *,
        model_obj: Any,
        tokenizer: Any,
        request: CompletionRequest,
        max_tokens: int,
        temperature: float,
    ) -> CompletionResponse:
        last_text = ""
        last_usage = {"input_tokens": 0, "output_tokens": 0}
        for repair in (False, True):
            prompt_messages = self._prompt_messages(request, repair=repair)
            prompt = _build_prompt(tokenizer, prompt_messages)
            raw_text = _generate_text(
                model_obj,
                tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = _sanitize_generated_text(raw_text)
            usage = {
                "input_tokens": _token_count(tokenizer, prompt),
                "output_tokens": _token_count(tokenizer, text),
            }
            last_text = text
            last_usage = usage
            parsed = _parse_tool_response(text, request)
            if parsed is not None:
                return CompletionResponse(
                    text=parsed["text"],
                    tool_calls=tuple(parsed["tool_calls"]),
                    stop_reason="tool_use" if parsed["tool_calls"] else "end_turn",
                    usage=usage,
                    raw={"text": text, "parsed": parsed["raw"]},
                )
        return CompletionResponse(
            text=last_text,
            tool_calls=(),
            stop_reason="end_turn",
            usage=last_usage,
            raw={"text": last_text},
        )

    def warmup(self) -> None:
        try:
            self.complete(
                CompletionRequest(
                    system="Reply with exactly OK.",
                    messages=(),
                    tools=(),
                    max_tokens=8,
                    temperature=0.0,
                )
            )
        except Exception as exc:
            logger.warning(
                "mlx warmup failed for model %s: %s",
                self.profile.model_id,
                exc,
                exc_info=True,
            )

    def _prompt_messages(
        self,
        request: CompletionRequest,
        *,
        repair: bool,
    ) -> list[dict[str, str]]:
        if request.tools:
            transcript = _format_transcript(request.messages)
            messages = [
                {"role": "system", "content": _tool_system_prompt(request)},
                {
                    "role": "user",
                    "content": _tool_user_prompt(
                        transcript=transcript,
                        request=request,
                        repair=repair,
                    ),
                },
            ]
            return messages
        transcript = _format_transcript(request.messages)
        user_content = transcript or "No prior transcript."
        user_content += "\n\nRespond to the latest user request directly."
        system = request.system or "You are a helpful AI assistant."
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

    def _temperature(self, request: CompletionRequest) -> float:
        if request.temperature is not None:
            return request.temperature
        raw = self.profile.options.get("temperature")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0


def mlx_available() -> bool:
    return _mlx_load is not None and _mlx_generate is not None and _mlx_make_sampler is not None


def cached_model_ids() -> list[str]:
    ids: list[str] = []
    for root in _HF_CACHE_CANDIDATES:
        if not str(root) or not root.exists():
            continue
        for path in sorted(root.glob("models--*")):
            name = path.name.removeprefix("models--").replace("--", "/", 1)
            if "/" not in name:
                continue
            ids.append(f"mlx/{name}")
    deduped: list[str] = []
    seen: set[str] = set()
    for model_id in ids:
        if model_id in seen:
            continue
        seen.add(model_id)
        deduped.append(model_id)
    return deduped


def _load_bundle(model: str) -> tuple[Any, Any]:
    if not mlx_available():
        raise RuntimeError(
            "mlx-lm is not installed; install backend[mlx] on Apple Silicon to use mlx/* models"
        )
    bare_model = _mlx_model_name(model)
    with _CACHE_LOCK:
        bundle = _MODEL_CACHE.get(bare_model)
        if bundle is None:
            bundle = _mlx_load(bare_model)  # type: ignore[misc]
            _MODEL_CACHE[bare_model] = bundle
    return bundle


def _build_prompt(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    apply_chat_template = getattr(tokenizer, "apply_chat_template", None)
    if callable(apply_chat_template):
        try:
            prompt = apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            try:
                prompt = apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except TypeError:
                prompt = apply_chat_template(messages, tokenize=False)
        if isinstance(prompt, str):
            return prompt
    blocks = [f"{message['role'].upper()}:\n{message['content']}" for message in messages]
    blocks.append("ASSISTANT:")
    return "\n\n".join(blocks)


def _generate_text(
    model_obj: Any,
    tokenizer: Any,
    *,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    try:
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "verbose": False,
        }
        if temperature > 0:
            kwargs["sampler"] = _mlx_make_sampler(temp=temperature)  # type: ignore[misc]
        return str(
            _mlx_generate(  # type: ignore[misc]
                model_obj,
                tokenizer,
                **kwargs,
            )
        )
    except Exception as exc:  # pragma: no cover - runtime wrapper
        raise RuntimeError(f"mlx generation failed: {exc}") from exc


def _sanitize_generated_text(text: str) -> str:
    without_thinking = _THINK_BLOCK_RE.sub("", text)
    without_thinking = _strip_channel_thought(without_thinking)
    lowered = without_thinking.lower()
    if "<think>" in lowered and "</think>" not in lowered:
        json_start = without_thinking.find("{")
        without_thinking = without_thinking[json_start:] if json_start >= 0 else ""
    return without_thinking.strip()


def _strip_channel_thought(text: str) -> str:
    cleaned = text
    while True:
        start_match = _CHANNEL_THOUGHT_RE.search(cleaned)
        if start_match is None:
            break
        end_candidates = [
            match.start()
            for pattern in (_CHANNEL_FINAL_RE, _CHANNEL_CLOSE_RE)
            if (match := pattern.search(cleaned, start_match.end())) is not None
        ]
        if not end_candidates:
            cleaned = cleaned[: start_match.start()]
            break
        cleaned = cleaned[: start_match.start()] + cleaned[min(end_candidates) :]
    cleaned = _CHANNEL_FINAL_RE.sub("", cleaned)
    cleaned = _CHANNEL_CLOSE_RE.sub("", cleaned)
    return cleaned


def _format_transcript(messages: tuple[Any, ...]) -> str:
    blocks: list[str] = []
    for message in messages:
        if message.role == "user":
            blocks.append(f"User:\n{message.content}")
            continue
        if message.role == "assistant":
            content = message.content or ""
            if content.strip():
                blocks.append(f"Assistant:\n{content}")
            if message.tool_calls:
                rendered = [
                    json.dumps(
                        {
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                        },
                        sort_keys=True,
                    )
                    for tool_call in message.tool_calls
                ]
                blocks.append("Assistant tool calls:\n" + "\n".join(rendered))
            continue
        header = f"Tool result ({message.name or message.tool_use_id or 'tool'}):"
        blocks.append(f"{header}\n{message.content}")
    return "\n\n".join(blocks).strip()


def _tool_system_prompt(request: CompletionRequest) -> str:
    preamble = request.system.strip()
    contract = (
        "You are operating inside claude-code-agent. When tools are available, "
        "respond with exactly one JSON object and no extra prose.\n\n"
        "Valid response shapes:\n"
        "{\"type\":\"message\",\"content\":\"...\"}\n"
        "{\"type\":\"tool_calls\",\"tool_calls\":["
        "{\"name\":\"tool_name\",\"arguments\":{}}]}\n\n"
        "Rules:\n"
        "- Never use a tool name that is not in the provided tool menu.\n"
        "- If tool_choice is \"required\", you must return type=\"tool_calls\".\n"
        "- If you already have enough information, return type=\"message\".\n"
        "- Tool arguments must be valid JSON objects matching the schema.\n"
        "- You may return multiple independent tool calls.\n"
        "- Do not wrap JSON in markdown fences."
    )
    return f"{preamble}\n\n{contract}" if preamble else contract


def _tool_user_prompt(
    *,
    transcript: str,
    request: CompletionRequest,
    repair: bool,
) -> str:
    lines = [
        "Conversation transcript:",
        transcript or "(empty transcript)",
        "",
        f"tool_choice mode: {request.tool_choice or 'auto'}",
        "",
        "Tool menu:",
        _format_tool_menu(request.tools),
        "",
        "Return the JSON object now.",
    ]
    if repair:
        lines.extend(
            [
                "",
                "Your previous response was invalid.",
                "Use one of these exact shapes and nothing else:",
                "{\"type\":\"message\",\"content\":\"...\"}",
                "{\"type\":\"tool_calls\",\"tool_calls\":["
                "{\"name\":\"tool_name\",\"arguments\":{}}]}",
            ]
        )
    return "\n".join(lines)


def _format_tool_menu(tools: tuple[Any, ...]) -> str:
    rendered: list[str] = []
    for tool in tools:
        rendered.append(
            json.dumps(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                },
                sort_keys=True,
            )
        )
    return "\n".join(rendered)


def _parse_tool_response(
    text: str,
    request: CompletionRequest,
) -> dict[str, Any] | None:
    allowed_names = {tool.name for tool in request.tools}
    candidates = _json_candidates(text)
    return _parse_tool_candidates(candidates, allowed_names, request.tool_choice)


def _parse_tool_candidates(
    candidates: list[str],
    allowed_names: set[str],
    tool_choice: str | None,
) -> dict[str, Any] | None:
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        normalized = _normalize_tool_payload(payload, allowed_names)
        if normalized is None:
            continue
        if tool_choice == "required" and not normalized["tool_calls"]:
            continue
        return normalized
    return None


def _normalize_tool_payload(
    payload: Any,
    allowed_names: set[str],
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    raw_tool_calls = payload.get("tool_calls")
    if raw_tool_calls is None and "name" in payload:
        raw_tool_calls = [payload]

    tool_calls = _parse_tool_calls(raw_tool_calls, allowed_names)
    if tool_calls:
        return {
            "text": str(payload.get("content") or ""),
            "tool_calls": tool_calls,
            "raw": payload,
        }

    if payload.get("type") == "message" or "content" in payload:
        content = str(payload.get("content") or "")
        return {
            "text": content,
            "tool_calls": [],
            "raw": payload,
        }
    return None


def _parse_tool_calls(raw_calls: Any, allowed_names: set[str]) -> list[ToolCall]:
    if not isinstance(raw_calls, list):
        return []
    parsed: list[ToolCall] = []
    for entry in raw_calls:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        if name not in allowed_names:
            continue
        arguments = entry.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"_raw": arguments}
        if not isinstance(arguments, dict):
            continue
        parsed.append(
            ToolCall(
                id=str(entry.get("id") or uuid.uuid4().hex),
                name=name,
                arguments=dict(arguments),
            )
        )
    return parsed


def _json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)
    for match in _CODE_FENCE_RE.finditer(text):
        fenced = match.group(1).strip()
        if fenced:
            candidates.append(fenced)
    balanced = _extract_first_json_object(text)
    if balanced:
        candidates.append(balanced)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start=start):
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _token_count(tokenizer: Any, text: str) -> int:
    if not text:
        return 0
    try:
        encoded = tokenizer(text, add_special_tokens=False)
    except Exception:
        return 0
    if isinstance(encoded, dict):
        input_ids = encoded.get("input_ids")
    else:
        input_ids = getattr(encoded, "input_ids", None)
    if isinstance(input_ids, list):
        if input_ids and isinstance(input_ids[0], list):
            return len(input_ids[0])
        return len(input_ids)
    return 0


def _mlx_model_name(model: str) -> str:
    return model.split("/", 1)[1] if model.startswith("mlx/") else model
