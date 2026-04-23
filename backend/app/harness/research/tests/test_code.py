from __future__ import annotations

from unittest.mock import patch

from app.harness.research.modules.code import CodeModule


def test_run_returns_empty_when_gh_unavailable():
    module = CodeModule()
    with patch("shutil.which", return_value=None):
        result = module.run("isotonic calibration", budget_tokens=30_000)
    assert result.examples == ()


def test_run_respects_tiny_budget():
    module = CodeModule()
    result = module.run("test", budget_tokens=100)
    assert result.examples == ()


def test_gh_search_parses_json_output():
    module = CodeModule()
    import json
    fake_json = json.dumps([
        {"url": "https://github.com/org/repo/blob/main/train.py",
         "repository": {"fullName": "org/repo", "stargazersCount": 42},
         "path": "train.py"}
    ])
    with patch.object(module, "_run_gh", return_value=fake_json):
        items = module._gh_search("calibration sklearn")
    assert len(items) == 1
    assert items[0]["repo"] == "org/repo"
    assert items[0]["stars"] == 42


def test_run_deduplicates_repos():
    module = CodeModule()
    same_repo_items = [
        {"url": f"https://github.com/org/repo/blob/main/file{i}.py",
         "repo": "org/repo", "file_path": f"file{i}.py", "stars": None}
        for i in range(10)
    ]
    with patch.object(module, "_gh_search", return_value=same_repo_items):
        with patch.object(module, "_read_file_snippet", return_value="code snippet"):
            result = module.run("test", budget_tokens=30_000)
    repos = {ex.repo for ex in result.examples}
    assert len(repos) == 1
    assert len(result.examples) <= 5   # capped by _MAX_REPOS


def test_result_examples_are_tuples():
    module = CodeModule()
    with patch.object(module, "_gh_search", return_value=[
        {"url": "https://github.com/a/b/blob/main/f.py",
         "repo": "a/b", "file_path": "f.py", "stars": None}
    ]):
        with patch.object(module, "_read_file_snippet", return_value="x = 1"):
            result = module.run("test", budget_tokens=30_000)
    assert isinstance(result.examples, tuple)
