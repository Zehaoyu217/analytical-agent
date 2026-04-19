from __future__ import annotations

from app.harness.guardrails.types import GuardrailFinding, Severity


def test_severity_order() -> None:
    assert Severity.FAIL.blocks_strict()
    assert Severity.WARN.warns()
    assert not Severity.WARN.blocks_strict()


def test_finding_is_frozen() -> None:
    import dataclasses

    import pytest
    f = GuardrailFinding(code="x", severity=Severity.WARN, message="msg")
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.code = "y"  # type: ignore[misc]
