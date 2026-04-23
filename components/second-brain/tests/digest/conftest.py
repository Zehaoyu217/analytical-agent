from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.config import Config


@pytest.fixture
def digest_cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    (home / "digests").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


ClaimWriter = Callable[..., Path]


def _write_claim(
    cfg: Config,
    slug: str,
    *,
    confidence: str = "high",
    contradicts: list[str] | None = None,
    resolution: str | None = None,
    extracted_at: datetime | None = None,
    status: str = "active",
    taxonomy: str | None = None,
    kind: str = "empirical",
) -> Path:
    extracted = extracted_at or datetime.now(UTC) - timedelta(days=1)
    lines = [
        "---",
        f"id: {slug}",
        f"statement: 'stmt for {slug}'",
        f"kind: {kind}",
        f"confidence: {confidence}",
        "scope: ''",
        f"contradicts: {contradicts or []}",
        "supports: []",
        "refines: []",
        f"extracted_at: {extracted.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"status: {status}",
        f"resolution: {resolution if resolution else 'null'}",
        "abstract: ''",
    ]
    if taxonomy is not None:
        lines.append(f"taxonomy: {taxonomy}")
    lines += ["---", ""]
    path = cfg.claims_dir / f"{slug}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.fixture
def write_claim() -> ClaimWriter:
    return _write_claim
