import pytest

from manager.task_bridge import TaskBridge
from manager.task_store import TaskStore


@pytest.fixture
def bridge(tmp_path):
    return TaskBridge(store=TaskStore(path=tmp_path / "tasks.json"))


def test_add_emits_changed_and_today_returns_colored(bridge):
    fired = []
    bridge.changed.connect(lambda: fired.append(1))
    bridge.add("写周报", "meeting", "2026-06-22")
    assert fired, "add 应发 changed"
    items = bridge.today("2026-06-22")
    assert len(items) == 1
    assert items[0]["text"] == "写周报"
    assert items[0]["color"] == "#7c3aed"   # meeting 色


def test_blank_text_not_added(bridge):
    bridge.add("   ", "work", "2026-06-22")
    assert bridge.today("2026-06-22") == []


def test_invalid_due_swallowed(bridge):
    bridge.add("x", "work", "bad-date")
    assert bridge.today("2026-06-22") == []


def test_toggle_and_week_counts(bridge):
    # bridge.add 是 void Slot(不返回 id),从 today() 取 id 再 toggle
    bridge.add("a", "work", "2026-06-22")
    bridge.add("b", "work", "2026-06-22")
    bridge.toggle(bridge.today("2026-06-22")[0]["id"])
    assert bridge.doneThisWeek("2026-06-22") == 1
    assert bridge.activeThisWeek("2026-06-22") == 1
    assert bridge.totalThisWeek("2026-06-22") == 2


def test_week_items_have_label_and_color(bridge):
    bridge.add("周五", "personal", "2026-06-26")
    wk = bridge.week("2026-06-22")
    assert wk[0]["label"] == "本周五"
    assert wk[0]["color"] == "#16a34a"


def test_catColor(bridge):
    assert bridge.catColor("important") == "#d97706"
    assert bridge.catColor("nope") == "#2f6bff"   # 回落 work
