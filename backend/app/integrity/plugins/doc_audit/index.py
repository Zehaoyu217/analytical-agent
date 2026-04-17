from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .parser.ignore import IgnoreMatcher
from .parser.markdown import ParsedDoc, parse_doc


@dataclass(frozen=True)
class MarkdownIndex:
    docs: dict[str, ParsedDoc]
    anchors_by_path: dict[str, set[str]]
    link_graph: dict[str, set[str]]
    excluded: frozenset[str]
    ignored: frozenset[str]
    repo_root: Path

    @classmethod
    def build(cls, repo_root: Path, plugin_cfg: dict[str, Any]) -> MarkdownIndex:
        roots: list[str] = list(plugin_cfg.get("doc_roots", []))
        excluded_globs: list[str] = list(plugin_cfg.get("excluded_paths", []))
        ignore_file = plugin_cfg.get("claude_ignore_file", ".claude-ignore")

        ignore_matcher = IgnoreMatcher.load(repo_root / ignore_file, repo_root=repo_root)
        candidates = _collect_candidates(repo_root, roots)
        excluded: set[str] = set()
        keep: list[Path] = []
        for path in candidates:
            rel = _rel(path, repo_root)
            if _matches_any(rel, excluded_globs):
                excluded.add(rel)
                continue
            keep.append(path)

        docs: dict[str, ParsedDoc] = {}
        ignored: set[str] = set()
        for path in keep:
            rel = _rel(path, repo_root)
            try:
                parsed = parse_doc(path, rel_path=rel)
            except Exception:
                continue
            docs[rel] = parsed
            if ignore_matcher.matches(rel):
                ignored.add(rel)

        anchors_by_path: dict[str, set[str]] = {
            rel: {h.slug for h in parsed.headings if h.slug}
            for rel, parsed in docs.items()
        }

        link_graph: dict[str, set[str]] = defaultdict(set)
        for rel, parsed in docs.items():
            base_dir = PurePosixPath(rel).parent
            for link in parsed.links:
                if not link.target:
                    continue
                target_lower = link.target.lower()
                if target_lower.startswith(("http://", "https://", "mailto:", "ftp://")):
                    continue
                if not link.target.endswith(".md"):
                    continue
                resolved = _resolve(base_dir, link.target)
                if resolved:
                    link_graph[rel].add(resolved)

        return cls(
            docs=docs,
            anchors_by_path=anchors_by_path,
            link_graph=dict(link_graph),
            excluded=frozenset(excluded),
            ignored=frozenset(ignored),
            repo_root=repo_root,
        )


def _rel(p: Path, repo_root: Path) -> str:
    return p.relative_to(repo_root).as_posix()


def _collect_candidates(repo_root: Path, roots: list[str]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in roots:
        for p in sorted(repo_root.glob(pattern)):
            if p.is_file() and p.suffix == ".md" and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _matches_any(rel: str, patterns: list[str]) -> bool:
    from .parser.ignore import _glob_match  # reuse the same matcher

    for pat in patterns:
        if _glob_match(rel, pat):
            return True
    return False


def _resolve(base_dir: PurePosixPath, target: str) -> str | None:
    try:
        # Manual normalization of `..` without filesystem access
        parts: list[str] = []
        for part in (base_dir / target).parts:
            if part == "..":
                if parts:
                    parts.pop()
                else:
                    return None
            elif part == ".":
                continue
            else:
                parts.append(part)
        return PurePosixPath(*parts).as_posix() if parts else None
    except Exception:
        return None
