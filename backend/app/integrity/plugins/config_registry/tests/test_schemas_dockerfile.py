from pathlib import Path

from app.integrity.plugins.config_registry.schemas.dockerfile import DockerfileSchema


def test_valid(tmp_path: Path):
    p = tmp_path / "Dockerfile"
    p.write_text("FROM python:3.12\nRUN echo\n")
    assert DockerfileSchema().validate(p, p.read_text()) == []

def test_missing_from(tmp_path: Path):
    p = tmp_path / "Dockerfile"
    p.write_text("RUN echo\n")
    failures = DockerfileSchema().validate(p, p.read_text())
    assert any(f.rule == "missing_from" for f in failures)

def test_undeclared_stage(tmp_path: Path):
    p = tmp_path / "Dockerfile"
    p.write_text("FROM python:3.12 AS build\nFROM python:3.12\nCOPY --from=missing /a /b\n")
    failures = DockerfileSchema().validate(p, p.read_text())
    assert any("missing" in f.message for f in failures)
