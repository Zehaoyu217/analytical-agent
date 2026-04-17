from backend.app.integrity.issue import IntegrityIssue, carry_first_seen


def make_issue(rule: str, node_id: str, first_seen: str = "2026-04-17") -> IntegrityIssue:
    return IntegrityIssue(
        rule=rule,
        severity="WARN",
        node_id=node_id,
        location="x.py:1",
        message="m",
        evidence={},
        fix_class=None,
        first_seen=first_seen,
    )


def test_dedup_key_combines_rule_and_node_id():
    a = make_issue("graph.dead_code", "mod_fn")
    b = make_issue("graph.drift_added", "mod_fn")
    c = make_issue("graph.dead_code", "mod_fn")
    assert a.dedup_key() != b.dedup_key()
    assert a.dedup_key() == c.dedup_key()


def test_carry_first_seen_preserves_prior_date():
    prior = [make_issue("graph.dead_code", "mod_fn", first_seen="2026-04-10")]
    today = [make_issue("graph.dead_code", "mod_fn", first_seen="2026-04-17")]
    out = carry_first_seen(today, prior)
    assert out[0].first_seen == "2026-04-10"


def test_carry_first_seen_keeps_today_when_new():
    prior: list[IntegrityIssue] = []
    today = [make_issue("graph.dead_code", "fresh_node", first_seen="2026-04-17")]
    out = carry_first_seen(today, prior)
    assert out[0].first_seen == "2026-04-17"


def test_serialize_roundtrip():
    a = make_issue("graph.dead_code", "mod_fn")
    d = a.to_dict()
    b = IntegrityIssue.from_dict(d)
    assert a == b
