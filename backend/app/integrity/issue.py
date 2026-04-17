from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Severity = Literal["INFO", "WARN", "ERROR", "CRITICAL"]


@dataclass(frozen=True)
class IntegrityIssue:
    rule: str
    severity: Severity
    node_id: str
    location: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    fix_class: str | None = None
    first_seen: str = ""

    def dedup_key(self) -> tuple[str, str]:
        return (self.rule, self.node_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IntegrityIssue":
        return cls(
            rule=d["rule"],
            severity=d["severity"],
            node_id=d["node_id"],
            location=d["location"],
            message=d["message"],
            evidence=dict(d.get("evidence", {})),
            fix_class=d.get("fix_class"),
            first_seen=d.get("first_seen", ""),
        )


def carry_first_seen(
    today: list[IntegrityIssue],
    prior: list[IntegrityIssue],
) -> list[IntegrityIssue]:
    prior_by_key = {p.dedup_key(): p.first_seen for p in prior}
    out: list[IntegrityIssue] = []
    for issue in today:
        prior_first = prior_by_key.get(issue.dedup_key())
        if prior_first:
            out.append(IntegrityIssue.from_dict({**issue.to_dict(), "first_seen": prior_first}))
        else:
            out.append(issue)
    return out
