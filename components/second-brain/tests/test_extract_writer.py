from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from second_brain.config import Config
from second_brain.extract.writer import write_claims
from second_brain.frontmatter import load_document
from second_brain.schema.claim import (
    ClaimConfidence,
    ClaimFrontmatter,
    ClaimKind,
    ClaimStatus,
)


def test_write_claims_creates_files(sb_home: Path) -> None:
    cfg = Config.load()
    claim = ClaimFrontmatter(
        id="clm_x",
        statement="X is Y.",
        kind=ClaimKind.EMPIRICAL,
        confidence=ClaimConfidence.HIGH,
        scope="narrow",
        supports=["src_a"],
        contradicts=[],
        refines=[],
        extracted_at=datetime.now(UTC),
        status=ClaimStatus.ACTIVE,
        resolution=None,
        abstract="abs",
    )
    write_claims(cfg, [claim])
    path = cfg.claims_dir / "clm_x.md"
    assert path.exists()
    meta, body = load_document(path)
    assert meta["id"] == "clm_x"
    assert "# X is Y" in body
