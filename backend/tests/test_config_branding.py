"""Unit tests for load_branding() (H6.T3)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config import BrandingConfig, load_branding


def test_load_branding_returns_defaults_when_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: E501
    """When no YAML file exists, load_branding() must return the hardcoded defaults."""
    # Point CCAGENT_HOME to an empty temp dir so neither override nor repo-default is used.
    monkeypatch.setenv("CCAGENT_HOME", str(tmp_path))

    # Temporarily patch the repo path so it doesn't accidentally find the repo yaml.
    import app.config as cfg_module
    monkeypatch.setattr(cfg_module, "_REPO_BRANDING_YAML", tmp_path / "does_not_exist.yaml")

    result = load_branding()

    assert isinstance(result, BrandingConfig)
    assert result.agent_name == "Analytical Agent"
    assert result.ui_accent_color == "#e0733a"
    assert len(result.ui_spinner_phrases) > 0


def test_load_branding_reads_repo_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_branding() reads values from the repo-default YAML when present."""
    yaml_file = tmp_path / "branding.yaml"
    yaml_file.write_text(
        yaml.dump({
            "agent": {"name": "TestBot", "persona": "You are TestBot."},
            "ui": {
                "title": "TestBot UI",
                "accent_color": "#123456",
                "spinner_phrases": ["Working...", "Busy..."],
            },
        })
    )

    import app.config as cfg_module
    monkeypatch.setattr(cfg_module, "_REPO_BRANDING_YAML", yaml_file)
    # Make sure CCAGENT_HOME doesn't have an override.
    monkeypatch.delenv("CCAGENT_HOME", raising=False)

    result = load_branding()

    assert result.agent_name == "TestBot"
    assert result.agent_persona == "You are TestBot."
    assert result.ui_title == "TestBot UI"
    assert result.ui_accent_color == "#123456"
    assert result.ui_spinner_phrases == ["Working...", "Busy..."]


def test_load_branding_home_override_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """$CCAGENT_HOME/config/branding.yaml overrides the repo default."""
    # Create a repo-default yaml (different values).
    repo_yaml = tmp_path / "repo_branding.yaml"
    repo_yaml.write_text(
        yaml.dump({"agent": {"name": "RepoAgent"}, "ui": {"title": "Repo UI"}})
    )

    # Create an override yaml under a fake CCAGENT_HOME.
    home_dir = tmp_path / "home"
    override_dir = home_dir / "config"
    override_dir.mkdir(parents=True)
    (override_dir / "branding.yaml").write_text(
        yaml.dump({"agent": {"name": "HomeAgent"}, "ui": {"title": "Home UI"}})
    )

    import app.config as cfg_module
    monkeypatch.setattr(cfg_module, "_REPO_BRANDING_YAML", repo_yaml)
    monkeypatch.setenv("CCAGENT_HOME", str(home_dir))

    result = load_branding()

    assert result.agent_name == "HomeAgent"
    assert result.ui_title == "Home UI"
