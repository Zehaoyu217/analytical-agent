from pathlib import Path

from app.integrity.plugins.config_registry.schemas.env_example import EnvExampleSchema


def test_valid(tmp_path: Path):
    p = tmp_path / ".env.example"
    p.write_text("# comment\nFOO=\nBAR=baz\n")
    assert EnvExampleSchema().validate(p, p.read_text()) == []

def test_lowercase_key(tmp_path: Path):
    p = tmp_path / ".env.example"
    p.write_text("foo=bar\n")
    failures = EnvExampleSchema().validate(p, p.read_text())
    assert any("foo" in f.location for f in failures)

def test_missing_equals(tmp_path: Path):
    p = tmp_path / ".env.example"
    p.write_text("FOOBAR\n")
    failures = EnvExampleSchema().validate(p, p.read_text())
    assert any(f.rule == "bad_format" for f in failures)
