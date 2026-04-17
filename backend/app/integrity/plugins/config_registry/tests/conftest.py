"""Synthetic mini-repo fixture for Plugin E tests.

Mirrors the real claude-code-agent layout minimally:
  backend/app/skills/{alpha,beta,beta/sub_skill}/SKILL.md
  scripts/{deploy.sh, gen_data.py, build.ts}
  config/integrity.yaml
  graphify/graph.augmented.json (2 routes + 1 dead-route)
  backend/app/api/foo_api.py (router + on_event)
  pyproject.toml, package.json, .claude/settings.json,
  Dockerfile, Makefile, .env.example, vite.config.ts,
  tsconfig.json, .gitignore, config/manifest.yaml (prior)
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
             "HOME": str(repo), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


@pytest.fixture
def tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    # Skills tree
    _write(repo, "backend/app/skills/__init__.py", "")
    _write(repo, "backend/app/skills/alpha/__init__.py", "")
    _write(repo, "backend/app/skills/alpha/SKILL.md",
           "---\nname: alpha\nversion: 1.0.0\ndescription: Alpha skill.\n---\n# Alpha\n")
    _write(repo, "backend/app/skills/alpha/skill.yaml",
           "dependencies:\n  packages: []\nerrors: {}\n")
    _write(repo, "backend/app/skills/beta/__init__.py", "")
    _write(repo, "backend/app/skills/beta/SKILL.md",
           "---\nname: beta\nversion: 1.0.0\ndescription: Beta hub.\n---\n# Beta\n")
    _write(repo, "backend/app/skills/beta/sub_skill/__init__.py", "")
    _write(repo, "backend/app/skills/beta/sub_skill/SKILL.md",
           "---\nname: sub_skill\nversion: 1.0.0\ndescription: Beta sub.\n---\n# Sub\n")

    # Scripts
    _write(repo, "scripts/deploy.sh", "#!/usr/bin/env bash\necho deploy\n")
    _write(repo, "scripts/gen_data.py", "#!/usr/bin/env python3\nprint('gen')\n")
    _write(repo, "scripts/build.ts", "// build script\nconsole.log('build');\n")

    # Configs
    _write(repo, "pyproject.toml",
           '[project]\nname = "tiny"\nversion = "0.1.0"\n')
    _write(repo, "package.json",
           '{"name": "tiny", "version": "0.1.0", "scripts": {}, "dependencies": {}}\n')
    _write(repo, ".claude/settings.json", '{"hooks": {}}\n')
    _write(repo, "Dockerfile", "FROM python:3.12-slim\nRUN echo hi\n")
    _write(repo, "Makefile", ".PHONY: test\ntest:\n\techo test\n")
    _write(repo, ".env.example", "FOO=\nBAR=baz\n")
    _write(repo, "vite.config.ts", "export default {};\n")
    _write(repo, "tsconfig.json", '{"compilerOptions": {}}\n')

    # Integrity config (so plugin.scan works)
    _write(repo, "config/integrity.yaml",
           "plugins:\n  config_registry:\n    enabled: true\n")

    # Base graph (empty — all routes come from augmented)
    base_graph = {"nodes": [], "links": []}
    _write(repo, "graphify/graph.json", json.dumps(base_graph, indent=2))

    # Graph (2 live routes + 1 dead route — id no longer in any source)
    graph = {
        "nodes": [
            {"id": "route::POST::/api/trace", "label": "POST /api/trace",
             "extractor": "fastapi_routes",
             "source_file": "backend/app/api/foo_api.py", "source_location": 5},
            {"id": "route::GET::/api/health", "label": "GET /api/health",
             "extractor": "fastapi_routes",
             "source_file": "backend/app/api/foo_api.py", "source_location": 12},
            {"id": "route::DELETE::/api/legacy", "label": "DELETE /api/legacy",
             "extractor": "fastapi_routes",
             "source_file": "backend/app/api/legacy_removed.py", "source_location": 1},
        ],
        "links": [],
    }
    _write(repo, "graphify/graph.augmented.json", json.dumps(graph, indent=2))

    # Functions source — matches first 2 routes
    _write(repo, "backend/app/api/__init__.py", "")
    _write(repo, "backend/app/api/foo_api.py",
           'from fastapi import APIRouter\n\nrouter = APIRouter()\n\n'
           '@router.post("/api/trace")\ndef trace_endpoint():\n    return {}\n\n'
           '@router.get("/api/health")\ndef health_endpoint():\n    return {}\n')

    # Main with FastAPI events
    _write(repo, "backend/app/main.py",
           'from fastapi import FastAPI\n\napp = FastAPI()\n\n'
           '@app.on_event("startup")\nasync def startup():\n    pass\n')

    # .gitignore
    _write(repo, ".gitignore", "build/\ndist/\n*.pyc\n")

    # Prior committed manifest — empty inventories so we can test "first run" diff
    _write(repo, "config/manifest.yaml",
           "# AUTO-GENERATED\ngenerated_at: \"2026-04-16\"\n"
           "generator_version: \"1.0.0\"\nmanifest_version: 1\n"
           "configs: []\nfunctions: []\nroutes: []\nscripts: []\nskills: []\n")

    # git init + commit so blob shas resolve via `git hash-object`
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "tiny_repo initial")

    return repo


@pytest.fixture
def today_fixed() -> date:
    return date(2026, 4, 17)
