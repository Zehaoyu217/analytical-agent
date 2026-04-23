from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder

_GH_SHORTHAND = re.compile(r"^gh:([A-Za-z0-9][A-Za-z0-9._-]*)/([A-Za-z0-9][A-Za-z0-9._-]*)$")
_HTTPS_REPO = re.compile(r"^(https?://[^\s;&|`$<>()\\]+\.git)$")
_FILE_REPO = re.compile(r"^(file://[^\s;&|`$<>()\\]+)$")

_DEFAULT_INCLUDE: tuple[str, ...] = (
    "README*",
    "docs/**/*.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
)
_DEFAULT_EXCLUDE: tuple[str, ...] = ("node_modules/**", "target/**", ".git/**")


class RepoConverter(Converter):
    kind: ClassVar[str] = "repo"

    def __init__(
        self,
        *,
        include_globs: tuple[str, ...] = _DEFAULT_INCLUDE,
        exclude_globs: tuple[str, ...] = _DEFAULT_EXCLUDE,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._include = include_globs
        self._exclude = exclude_globs
        self._timeout = timeout_seconds

    def matches(self, source: IngestInput) -> bool:
        origin = source.origin or ""
        if _GH_SHORTHAND.match(origin):
            return True
        if origin.startswith(("https://", "http://")) and origin.endswith(".git"):
            return True
        if origin.startswith("file://"):
            return True
        return False

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        url = self._resolve(source.origin)
        with tempfile.TemporaryDirectory(prefix="sb_repo_") as td:
            clone_dir = Path(td) / "repo"
            self._clone(url, clone_dir)
            raws = self._capture(clone_dir, target)
            title = self._title_from_readme(clone_dir)
            body = self._body(raws, target)
        return SourceArtifacts(
            processed_body=body,
            raw=raws,
            title_hint=title,
        )

    def _resolve(self, origin: str) -> str:
        m = _GH_SHORTHAND.match(origin)
        if m:
            owner, repo = m.group(1), m.group(2)
            return f"https://github.com/{owner}/{repo}.git"
        if _HTTPS_REPO.match(origin) or _FILE_REPO.match(origin):
            return origin
        raise ValueError(f"unrecognized repo origin: {origin!r}")

    def _clone(self, url: str, dest: Path) -> None:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
            check=True,
            capture_output=True,
            timeout=self._timeout,
        )

    def _capture(self, clone_dir: Path, target: SourceFolder):
        raws = []
        seen: set[Path] = set()
        for pattern in self._include:
            for candidate in clone_dir.glob(pattern):
                if not candidate.is_file():
                    continue
                rel = candidate.relative_to(clone_dir)
                if self._excluded(rel):
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                rel_path = f"raw/{rel.as_posix()}"
                raw = target.write_raw(
                    rel_path=rel_path,
                    content=candidate.read_bytes(),
                    kind="original",
                )
                raws.append(raw)
        return raws

    def _excluded(self, rel: Path) -> bool:
        posix = rel.as_posix()
        return any(rel.match(pat) or _fnmatch_prefix(posix, pat) for pat in self._exclude)

    @staticmethod
    def _title_from_readme(clone_dir: Path) -> str:
        for name in ("README.md", "README", "README.rst"):
            p = clone_dir / name
            if p.exists():
                for line in p.read_text("utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if s.startswith("# "):
                        return s[2:].strip()
                    if s:
                        return s[:120]
        return clone_dir.name

    @staticmethod
    def _body(raws, target: SourceFolder) -> str:
        # Compose a short markdown body that concatenates captured files for BM25.
        parts: list[str] = []
        for r in raws:
            p = target.root / r.path
            if p.suffix.lower() in {".md", ".rst", ".txt", ".toml", ".json"}:
                parts.append(f"## {r.path}\n\n{p.read_text('utf-8', errors='replace')}")
        return ("\n\n".join(parts) + "\n") if parts else "\n"


def _fnmatch_prefix(posix: str, pattern: str) -> bool:
    # Very small helper so that "node_modules/**" matches paths under node_modules/.
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return posix.startswith(prefix + "/") or posix == prefix
    return False
