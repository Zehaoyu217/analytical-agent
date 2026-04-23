#!/usr/bin/env python3
"""Download and optionally smoke-test the local MLX models used by this repo."""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time
from collections.abc import Sequence

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

try:
    from mlx_lm import generate, load
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        "mlx-lm is not installed. Run `uv sync --project backend --extra mlx` first."
    ) from exc

_DEFAULT_MODELS = (
    "mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit",
    "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit",
    "mlx/NexVeridian/gemma-4-26B-A4b-it-4bit",
    "mlx/mlx-community/Qwen3.5-9B-OptiQ-4bit",
)
_DEFAULT_PROMPT = "Reply with exactly: ready"


def _bare_model_id(model_id: str) -> str:
    return model_id.split("/", 1)[1] if model_id.startswith("mlx/") else model_id


def _build_prompt(tokenizer: object, prompt: str) -> str:
    apply_chat_template = getattr(tokenizer, "apply_chat_template", None)
    if callable(apply_chat_template):
        try:
            rendered = apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
        except TypeError:
            rendered = apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
            )
        if isinstance(rendered, str):
            return rendered
    return prompt


def _clear_mlx_cache() -> None:
    try:
        import mlx.core as mx
    except ImportError:
        return
    metal = getattr(mx, "metal", None)
    clear_cache = getattr(metal, "clear_cache", None)
    if callable(clear_cache):
        clear_cache()


def preload_models(models: Sequence[str], *, smoke: bool, prompt: str, max_tokens: int) -> int:
    failures: list[str] = []
    for model_id in models:
        bare_model = _bare_model_id(model_id)
        started = time.monotonic()
        model_obj = None
        tokenizer = None
        print(f"[mlx] loading {model_id}", flush=True)
        try:
            model_obj, tokenizer = load(bare_model)
            elapsed = time.monotonic() - started
            print(f"[mlx] loaded {model_id} in {elapsed:.1f}s", flush=True)
            if smoke:
                rendered_prompt = _build_prompt(tokenizer, prompt)
                reply = generate(
                    model_obj,
                    tokenizer,
                    prompt=rendered_prompt,
                    max_tokens=max_tokens,
                    verbose=False,
                )
                preview = reply.strip().replace("\n", " ")
                print(f"[mlx] smoke {model_id}: {preview[:200]}", flush=True)
        except Exception as exc:
            failures.append(f"{model_id}: {exc}")
            print(f"[mlx] failed {model_id}: {exc}", file=sys.stderr, flush=True)
        finally:
            del model_obj
            del tokenizer
            gc.collect()
            _clear_mlx_cache()
    if failures:
        print("\n[mlx] failures:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("\n[mlx] all models ready", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="*", default=list(_DEFAULT_MODELS))
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a tiny generation after each load.",
    )
    parser.add_argument(
        "--prompt",
        default=_DEFAULT_PROMPT,
        help="Prompt used for the smoke test.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=24,
        help="Maximum generation tokens for the smoke test.",
    )
    args = parser.parse_args()
    return preload_models(
        args.models,
        smoke=args.smoke,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
    )


if __name__ == "__main__":
    raise SystemExit(main())
