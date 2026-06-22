from pathlib import Path

import pytest

from manager.task_store import TaskStore


@pytest.fixture
def store(tmp_path):
    return TaskStore(path=tmp_path / "tasks.json")


def test_add_then_today_lists_it(store):
    store.add("写周报", cat="work", due="2026-06-22")
    items = store.today("2026-06-22")
    assert len(items) == 1
    assert items[0]["text"] == "写周报"
    assert items[0]["cat"] == "work"
    assert items[0]["done"] is False
    assert items[0]["id"]


def test_today_filters_by_due_date(store):
    store.add("今天", due="2026-06-22")
    store.add("明天", due="2026-06-23")
    assert [t["text"] for t in store.today("2026-06-22")] == ["今天"]


def test_toggle_flips_done_and_persists(store):
    tid = store.add("a", due="2026-06-22")
    store.toggle(tid)
    assert store.today("2026-06-22")[0]["done"] is True
    again = TaskStore(path=store.path)
    assert again.today("2026-06-22")[0]["done"] is True
    store.toggle(tid)
    assert store.today("2026-06-22")[0]["done"] is False


def test_remove(store):
    tid = store.add("a", due="2026-06-22")
    store.remove(tid)
    assert store.today("2026-06-22") == []


def test_week_excludes_today_includes_rest_of_week_with_label(store):
    # 2026-06-22 是周一 → 本周 06-22(一)~06-28(日)
    store.add("今天", due="2026-06-22")
    store.add("周五", due="2026-06-26")
    store.add("下周一", due="2026-06-29")
    wk = store.week("2026-06-22")
    assert [t["text"] for t in wk] == ["周五"]
    assert wk[0]["label"] == "本周五"


def test_week_counts_done_and_active_include_today(store):
    store.add("今天-未完成", due="2026-06-22")
    t2 = store.add("今天-已完成", due="2026-06-22")
    store.add("周三-未完成", due="2026-06-24")
    store.toggle(t2)
    assert store.done_in_week("2026-06-22") == 1
    assert store.active_in_week("2026-06-22") == 2


def test_empty_store_returns_empty(store):
    assert store.today("2026-06-22") == []
    assert store.week("2026-06-22") == []
    assert store.done_in_week("2026-06-22") == 0
    assert store.active_in_week("2026-06-22") == 0


def test_invalid_due_raises(store):
    with pytest.raises(ValueError):
        store.add("x", due="not-a-date")
