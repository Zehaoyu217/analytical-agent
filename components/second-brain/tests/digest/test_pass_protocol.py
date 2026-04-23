from __future__ import annotations

from typing import Any

from second_brain.config import Config
from second_brain.digest.passes import Pass
from second_brain.digest.schema import DigestEntry


class _FakePass:
    prefix = "r"
    section = "Reconciliation"

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        return [DigestEntry(id="", section=self.section, line="keep?", action={"action": "keep"})]


class _MissingMethod:
    prefix = "r"
    section = "Reconciliation"


class _MissingAttr:
    prefix = "r"

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        return []


def test_fake_pass_matches_protocol() -> None:
    assert isinstance(_FakePass(), Pass)


def test_pass_without_run_fails_protocol_check() -> None:
    assert not isinstance(_MissingMethod(), Pass)


def test_pass_without_section_fails_protocol_check() -> None:
    assert not isinstance(_MissingAttr(), Pass)
