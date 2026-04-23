from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Any

from second_brain.llm.providers import mlx_model_name

# Xet-backed downloads have been unreliable on this machine for larger MLX models.
# Set this before importing mlx_lm / huggingface_hub so first-time pulls use the
# standard Hub transport instead.
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


class MLXError(RuntimeError):
    """Raised when MLX is unavailable or returns malformed output."""


@dataclass(frozen=True)
class MLXResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str


def mlx_available() -> bool:
    return _mlx_load is not None and _mlx_generate is not None and _mlx_make_sampler is not None


def complete_chat(
    model: str,
    *,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> MLXResult:
    model_bundle = _load_bundle(model)
    model_obj, tokenizer = model_bundle
    prompt = _build_prompt(
        tokenizer,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw_text = _generate_text(
        model_obj,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = _sanitize_generated_text(raw_text)
    return MLXResult(
        text=text,
        tokens_in=_token_count(tokenizer, prompt),
        tokens_out=_token_count(tokenizer, text),
        model=mlx_model_name(model),
    )


def extract_tool_payload(text: str, tool_name: str) -> dict[str, Any]:
    cleaned = _sanitize_generated_text(text)
    for candidate in _json_candidates(cleaned):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        normalized = _normalize_payload(payload, tool_name)
        if normalized is not None:
            return normalized
    raise MLXError(f"mlx response contained no usable JSON payload for {tool_name}")


def _load_bundle(model: str) -> tuple[Any, Any]:
    if not mlx_available():
        raise MLXError(
            "mlx-lm is not installed; install second-brain[mlx] on Apple Silicon to use mlx/* models"
        )
    bare_model = mlx_model_name(model)
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
        raise MLXError(f"mlx generation failed: {exc}") from exc


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


def _normalize_payload(payload: Any, tool_name: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        if isinstance(payload.get("arguments"), dict):
            return payload["arguments"]
        if isinstance(payload.get("tool_input"), dict):
            return payload["tool_input"]
        if isinstance(payload.get(tool_name), dict):
            return payload[tool_name]
        return payload
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
