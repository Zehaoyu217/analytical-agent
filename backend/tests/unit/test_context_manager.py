from app.context.manager import ContextLayer, ContextManager, _SessionRegistry


def test_add_layer() -> None:
    mgr = ContextManager(max_tokens=32768)
    mgr.add_layer(ContextLayer(
        name="system",
        tokens=1640,
        compactable=False,
        items=[{"name": "system_prompt", "tokens": 1640}],
    ))
    assert mgr.total_tokens == 1640
    assert mgr.utilization < 0.1


def test_utilization_calculation() -> None:
    mgr = ContextManager(max_tokens=10000)
    mgr.add_layer(ContextLayer(name="system", tokens=5000, compactable=False, items=[]))
    assert mgr.utilization == 0.5


def test_snapshot_returns_all_layers() -> None:
    mgr = ContextManager(max_tokens=32768)
    mgr.add_layer(ContextLayer(name="system", tokens=1640, compactable=False, items=[]))
    mgr.add_layer(ContextLayer(name="l1_always", tokens=1600, compactable=False, items=[]))
    mgr.add_layer(ContextLayer(name="conversation", tokens=3000, compactable=True, items=[]))
    snapshot = mgr.snapshot()
    assert snapshot["total_tokens"] == 6240
    assert len(snapshot["layers"]) == 3
    assert snapshot["max_tokens"] == 32768


def test_compaction_needed() -> None:
    mgr = ContextManager(max_tokens=10000, compaction_threshold=0.8)
    mgr.add_layer(ContextLayer(name="system", tokens=2000, compactable=False, items=[]))
    assert not mgr.compaction_needed
    mgr.add_layer(ContextLayer(name="conversation", tokens=7000, compactable=True, items=[]))
    assert mgr.compaction_needed


def test_compaction_history() -> None:
    mgr = ContextManager(max_tokens=10000, compaction_threshold=0.8)
    mgr.record_compaction(
        tokens_before=8500,
        tokens_after=4200,
        removed=[{"name": "old_ref.md", "tokens": 1200}],
        survived=["system", "l1_always"],
    )
    history = mgr.compaction_history
    assert len(history) == 1
    assert history[0]["tokens_freed"] == 4300


# ── Session registry tests ────────────────────────────────────────────────────

def test_session_registry_creates_on_first_access() -> None:
    reg = _SessionRegistry()
    mgr = reg.get_or_create("session-alpha")
    assert isinstance(mgr, ContextManager)


def test_session_registry_returns_same_instance() -> None:
    reg = _SessionRegistry()
    m1 = reg.get_or_create("session-beta")
    m2 = reg.get_or_create("session-beta")
    assert m1 is m2


def test_session_registry_get_returns_none_for_unknown() -> None:
    reg = _SessionRegistry()
    assert reg.get("no-such-session") is None


def test_session_registry_list_sessions() -> None:
    reg = _SessionRegistry()
    reg.get_or_create("s1")
    reg.get_or_create("s2")
    reg.get_or_create("s3")
    sessions = reg.list_sessions()
    assert set(sessions) >= {"s1", "s2", "s3"}


def test_session_registry_delete_removes_session() -> None:
    reg = _SessionRegistry()
    reg.get_or_create("deleteme")
    assert reg.get("deleteme") is not None
    reg.delete("deleteme")
    assert reg.get("deleteme") is None


def test_session_registry_different_sessions_are_isolated() -> None:
    reg = _SessionRegistry()
    m1 = reg.get_or_create("iso-1")
    m2 = reg.get_or_create("iso-2")
    m1.add_layer(ContextLayer(name="system", tokens=1000, compactable=False, items=[]))
    assert m2.total_tokens == 0


def test_session_registry_default_max_tokens() -> None:
    reg = _SessionRegistry()
    mgr = reg.get_or_create("max-tok-check")
    # Default should be 200k (matching claude-3 context window)
    assert mgr._max_tokens == 200_000


def test_session_registry_compaction_diff_loss_pct() -> None:
    """Validate that information_loss_pct arithmetic is correct."""
    reg = _SessionRegistry()
    mgr = reg.get_or_create("compaction-check")
    mgr.record_compaction(
        tokens_before=160_000,
        tokens_after=90_000,
        removed=[{"name": "old_tool_result", "tokens": 70_000}],
        survived=["System Prompt", "User Message"],
    )
    history = mgr.compaction_history
    assert len(history) == 1
    entry = history[0]
    tokens_freed = entry["tokens_freed"]
    loss_pct = tokens_freed / entry["tokens_before"] * 100
    # 70_000 / 160_000 * 100 = 43.75%
    assert abs(loss_pct - 43.75) < 0.01
    # Severity: >= 40% → HIGH
    severity = "HIGH" if loss_pct >= 40 else "MEDIUM" if loss_pct >= 20 else "LOW"
    assert severity == "HIGH"
