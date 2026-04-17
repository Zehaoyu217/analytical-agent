from pathlib import Path
from backend.app.integrity.plugins.config_registry.schemas.integrity_yaml import IntegrityYamlSchema

def test_valid(tmp_path: Path):
    p = tmp_path / "integrity.yaml"
    p.write_text("plugins:\n  graph_lint:\n    enabled: true\n")
    assert IntegrityYamlSchema().validate(p, p.read_text()) == []

def test_plugins_not_mapping(tmp_path: Path):
    p = tmp_path / "integrity.yaml"
    p.write_text("plugins: []\n")
    failures = IntegrityYamlSchema().validate(p, p.read_text())
    assert any(f.location == "plugins" for f in failures)

def test_plugin_missing_enabled(tmp_path: Path):
    p = tmp_path / "integrity.yaml"
    p.write_text("plugins:\n  foo: {}\n")
    failures = IntegrityYamlSchema().validate(p, p.read_text())
    assert any("enabled" in f.location for f in failures)
