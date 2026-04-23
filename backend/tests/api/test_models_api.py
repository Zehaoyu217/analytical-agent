from __future__ import annotations

from app.api import models_api


def test_models_api_includes_mlx_group(monkeypatch) -> None:
    monkeypatch.setattr(models_api, "_mlx_runtime_available", lambda: True)
    monkeypatch.setattr(
        models_api,
        "_fetch_mlx_models",
        lambda: [
            models_api.ModelEntry(
                id="mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit",
                label="Gemma 4 E2B",
                description="MLX local · cached",
            )
        ],
    )

    response = models_api.list_models()
    groups = {group.provider: group for group in response.groups}

    assert groups["mlx"].available is True
    assert groups["mlx"].models[0].id == "mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit"


def test_models_api_marks_mlx_unavailable_when_runtime_missing(monkeypatch) -> None:
    monkeypatch.setattr(models_api, "_mlx_runtime_available", lambda: False)

    response = models_api.list_models()
    groups = {group.provider: group for group in response.groups}

    assert groups["mlx"].available is False
    assert groups["mlx"].models == []
    assert "backend[mlx]" in groups["mlx"].note


def test_models_api_has_no_ollama_group() -> None:
    """Ollama was removed — the response must not advertise it."""
    response = models_api.list_models()
    providers = {group.provider for group in response.groups}
    assert "ollama" not in providers
    assert "anthropic" not in providers


def test_mlx_label_uses_curated_name_when_mapped() -> None:
    model_id = "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit"
    assert models_api._mlx_label(model_id) == "Gemma 4 E4B Vision"


def test_mlx_label_distinguishes_vision_from_text_variants() -> None:
    """Non-LM Gemma 4 builds keep the vision tower; -lm builds strip it."""
    assert models_api._mlx_label(
        "mlx/jorch/gemma-4-e4b-it-lm-4bit"
    ) == "Gemma 4 E4B Text"
    assert models_api._mlx_label(
        "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit"
    ) == "Gemma 4 E4B Vision"


def test_mlx_label_falls_back_to_humanizer_for_unknown_ids() -> None:
    """Unmapped ids must still produce a readable (if imperfect) label."""
    unknown = "mlx/some-org/new-llm-42b-it-4bit"
    fallback = models_api._mlx_label(unknown)
    # Humanizer strips the "mlx/" prefix and turns hyphens into spaces.
    assert fallback == "some org/new llm 42b it 4bit"
    # Never returns an empty string.
    assert fallback


def test_fetch_mlx_models_applies_label_map(monkeypatch) -> None:
    monkeypatch.setattr(
        models_api,
        "cached_model_ids",
        lambda: [
            "mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit",
            "mlx/unknown/brand-new-model-4bit",
        ],
    )
    entries = {e.id: e for e in models_api._fetch_mlx_models()}
    # Every id produces a non-empty label — either mapped or humanizer fallback.
    assert entries["mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit"].label
    assert entries["mlx/unknown/brand-new-model-4bit"].label
