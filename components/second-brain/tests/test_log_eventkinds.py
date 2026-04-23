from second_brain.log import EventKind


def test_automation_event_kinds_exist():
    assert EventKind.RETRY == "RETRY"
    assert EventKind.WATCH == "WATCH"
    assert EventKind.MAINTAIN == "MAINTAIN"
