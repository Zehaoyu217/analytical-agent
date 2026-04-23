from __future__ import annotations

import pytest

from second_brain.gardener.cost import (
    MODEL_PRICING,
    estimate_cost,
    price_for,
)


@pytest.mark.parametrize(
    "model",
    [
        "anthropic/claude-haiku-4-5",
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-opus-4-7",
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "openai/gpt-oss-120b:free",
        "deepseek/deepseek-chat",
        "ollama/gemma4:e4b",
        "mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit",
        "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit",
        "mlx/NexVeridian/gemma-4-26B-A4b-it-4bit",
    ],
)
def test_known_models_have_pricing(model: str) -> None:
    in_rate, out_rate = price_for(model)
    assert in_rate >= 0
    assert out_rate >= 0
    assert (in_rate, out_rate) == MODEL_PRICING[model]


def test_unknown_model_uses_fallback() -> None:
    assert price_for("vendor/unknown-model-99") == (1.0, 5.0)


def test_local_ollama_is_free() -> None:
    assert price_for("ollama/llama3.1") == (0.0, 0.0)
    assert estimate_cost("ollama/llama3.1", 10_000, 10_000) == 0.0
    assert price_for("ollama/gemma4:e4b") == (0.0, 0.0)
    assert price_for("mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit") == (0.0, 0.0)
    assert price_for("mlx/mlx-community/Qwen3.5-9B-OptiQ-4bit") == (0.0, 0.0)
    assert price_for("openai/gpt-oss-120b:free") == (0.0, 0.0)


def test_estimate_cost_haiku() -> None:
    # haiku: (1.00 in, 5.00 out) per 1M tok
    # 1M in + 1M out = 1 + 5 = 6
    assert estimate_cost("anthropic/claude-haiku-4-5", 1_000_000, 1_000_000) == pytest.approx(6.0)


def test_estimate_cost_sonnet_small() -> None:
    # sonnet: (3, 15) per 1M
    # 10k in + 5k out = 3*0.01 + 15*0.005 = 0.03 + 0.075 = 0.105
    assert estimate_cost("anthropic/claude-sonnet-4-6", 10_000, 5_000) == pytest.approx(0.105)
