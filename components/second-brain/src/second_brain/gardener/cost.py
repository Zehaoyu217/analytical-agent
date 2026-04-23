"""Model pricing table + cost estimation helpers.

Prices in USD per 1M tokens (input, output). Unknown models use a
conservative fallback so budget guardrails still trip.
"""
from __future__ import annotations

MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "anthropic/claude-haiku-4-5": (1.00, 5.00),
    "anthropic/claude-sonnet-4-6": (3.00, 15.00),
    "anthropic/claude-opus-4-7": (15.00, 75.00),
    # OpenAI
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-oss-120b:free": (0.0, 0.0),
    # DeepSeek
    "deepseek/deepseek-chat": (0.27, 1.10),
    # Local (Ollama) — no API cost
    "ollama/llama3.1": (0.0, 0.0),
    "ollama/qwen2.5": (0.0, 0.0),
    "ollama/gemma4:e2b": (0.0, 0.0),
    "ollama/gemma4:e4b": (0.0, 0.0),
    # Local (MLX) — no API cost
    "mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit": (0.0, 0.0),
    "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit": (0.0, 0.0),
    "mlx/NexVeridian/gemma-4-26B-A4b-it-4bit": (0.0, 0.0),
    "mlx/mlx-community/Qwen3.5-9B-OptiQ-4bit": (0.0, 0.0),
}

_FALLBACK: tuple[float, float] = (1.0, 5.0)


def price_for(model: str) -> tuple[float, float]:
    return MODEL_PRICING.get(model, _FALLBACK)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    in_per_mtok, out_per_mtok = price_for(model)
    return (tokens_in / 1_000_000) * in_per_mtok + (
        tokens_out / 1_000_000
    ) * out_per_mtok
