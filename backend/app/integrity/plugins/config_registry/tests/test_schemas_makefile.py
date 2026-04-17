from pathlib import Path
from backend.app.integrity.plugins.config_registry.schemas.makefile import MakefileSchema

def test_valid(tmp_path: Path):
    p = tmp_path / "Makefile"
    p.write_text(".PHONY: test build\ntest:\n\techo test\nbuild:\n\techo build\n")
    assert MakefileSchema().validate(p, p.read_text()) == []

def test_phony_missing_target(tmp_path: Path):
    p = tmp_path / "Makefile"
    p.write_text(".PHONY: test\ntest:\n\techo t\nbuild:\n\techo b\n")
    failures = MakefileSchema().validate(p, p.read_text())
    assert any("build" in f.message and "PHONY" in f.message for f in failures)

def test_camelcase_target(tmp_path: Path):
    p = tmp_path / "Makefile"
    p.write_text(".PHONY: testThing\ntestThing:\n\techo t\n")
    failures = MakefileSchema().validate(p, p.read_text())
    assert any("kebab" in f.message.lower() or "case" in f.message.lower() for f in failures)
