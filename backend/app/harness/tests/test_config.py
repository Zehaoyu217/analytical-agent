from __future__ import annotations

import pytest

from app.harness.config import HarnessConfig, ModelProfile, load_config


def test_load_config_parses_models_yaml(tmp_path) -> None:
    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        """
mode: config
models:
  claude_sonnet:
    provider: anthropic
    model_id: claude-sonnet-4-6
    thinking_budget: 8000
    tier: observatory
  gemma_fast:
    provider: ollama
    model_id: gemma4:26b
    host: http://localhost:11434
    num_ctx: 16384
    tier: strict
roles:
  think: gemma_fast
  evaluate: claude_sonnet
warmup: [gemma_fast]
guardrails:
  mode: per_tier
  retry_on_gate_block: null
""",
        encoding="utf-8",
    )
    cfg = load_config(config_path)
    assert isinstance(cfg, HarnessConfig)
    assert cfg.mode == "config"
    assert cfg.roles["think"] == "gemma_fast"
    profile = cfg.models["gemma_fast"]
    assert isinstance(profile, ModelProfile)
    assert profile.provider == "ollama"
    assert profile.tier == "strict"
    assert profile.num_ctx == 16384
    assert "gemma_fast" in cfg.warmup


def test_load_config_rejects_unknown_role_target(tmp_path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        """
mode: config
models: {}
roles: {think: doesnt_exist}
warmup: []
guardrails: {mode: per_tier, retry_on_gate_block: null}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="role 'think'"):
        load_config(config_path)


def test_load_config_rejects_unknown_tier(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
mode: config
models:
  x: {provider: anthropic, model_id: x, tier: mystery}
roles: {think: x}
warmup: []
guardrails: {mode: per_tier, retry_on_gate_block: null}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tier"):
        load_config(path)
