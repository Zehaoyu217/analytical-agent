from pathlib import Path
from backend.app.integrity.plugins.config_registry.schemas.tsconfig import TsconfigSchema

def test_valid(tmp_path: Path):
    p = tmp_path / "tsconfig.json"
    p.write_text('{"compilerOptions": {"strict": true}}')
    assert TsconfigSchema().validate(p, p.read_text()) == []

def test_missing_compiler_options(tmp_path: Path):
    p = tmp_path / "tsconfig.json"
    p.write_text('{}')
    failures = TsconfigSchema().validate(p, p.read_text())
    assert any(f.location == "compilerOptions" for f in failures)

def test_extends_missing_file(tmp_path: Path):
    p = tmp_path / "tsconfig.json"
    p.write_text('{"extends": "./does-not-exist.json", "compilerOptions": {}}')
    failures = TsconfigSchema().validate(p, p.read_text())
    assert any("extends" in f.location for f in failures)
