from pathlib import Path

from app.integrity.plugins.config_registry.schemas.vite_config import ViteConfigSchema


def test_valid(tmp_path: Path):
    p = tmp_path / "vite.config.ts"
    p.write_text("export default { plugins: [] };\n")
    assert ViteConfigSchema().validate(p, p.read_text()) == []

def test_missing_export_default(tmp_path: Path):
    p = tmp_path / "vite.config.ts"
    p.write_text("const x = 1;\n")
    failures = ViteConfigSchema().validate(p, p.read_text())
    assert any(f.rule == "missing_export_default" for f in failures)
