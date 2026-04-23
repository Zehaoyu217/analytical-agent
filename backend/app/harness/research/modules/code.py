from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

from app.harness.research.types import CodeExample, CodeResult

logger = logging.getLogger(__name__)

_GH_TIMEOUT = 15
_MAX_SNIPPET_CHARS = 500
_MAX_REPOS = 5
_BUDGET_MIN = 1_000


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


class CodeModule:
    """Searches GitHub for working code examples using the gh CLI."""

    def run(self, query: str, budget_tokens: int) -> CodeResult:
        if budget_tokens < _BUDGET_MIN or not shutil.which("gh"):
            return CodeResult()

        items = self._gh_search(query)
        if not items:
            return CodeResult()

        examples: list[CodeExample] = []
        tokens_used = 0
        seen_repos: set[str] = set()

        for item in items:
            if len(examples) >= _MAX_REPOS:
                break
            repo = item.get("repo", "")
            seen_repos.add(repo)

            snippet = self._read_file_snippet(item.get("url", ""))
            tokens_used += _estimate_tokens(snippet)
            if tokens_used > budget_tokens * 0.9:
                break

            examples.append(CodeExample(
                url=item.get("url", ""),
                repo=repo,
                file_path=item.get("file_path", ""),
                snippet=snippet[:_MAX_SNIPPET_CHARS],
                relevance=f"Matches query: {query[:80]}",
                stars=item.get("stars"),
            ))

        return CodeResult(examples=tuple(examples))

    def _run_gh(self, args: list[str]) -> str:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True, text=True, timeout=_GH_TIMEOUT,
        )
        return result.stdout if result.returncode == 0 else ""

    def _gh_search(self, query: str) -> list[dict[str, Any]]:
        output = self._run_gh([
            "search", "code", query,
            "--language", "python",
            "--limit", "20",
            "--json", "url,repository,path",
        ])
        if not output:
            return []
        try:
            items = json.loads(output)
            return [
                {
                    "url": item.get("url", ""),
                    "repo": item.get("repository", {}).get("fullName", ""),
                    "file_path": item.get("path", ""),
                    "stars": item.get("repository", {}).get("stargazersCount"),
                }
                for item in items
            ]
        except Exception:
            return []

    def _read_file_snippet(self, url: str) -> str:
        if not url or "github.com" not in url:
            return ""
        try:
            parts = url.replace("https://github.com/", "").split("/blob/", 1)
            if len(parts) != 2:
                return ""
            repo = parts[0]
            ref_path = parts[1].split("/", 1)
            if len(ref_path) != 2:
                return ""
            file_path = ref_path[1]
            output = self._run_gh([
                "api", f"repos/{repo}/contents/{file_path}",
                "--jq", ".content",
            ])
            if output:
                import base64
                content = base64.b64decode(output.strip()).decode("utf-8", errors="ignore")
                return content[:_MAX_SNIPPET_CHARS]
        except Exception as exc:
            logger.debug("File read failed for %s: %s", url, exc)
        return ""
