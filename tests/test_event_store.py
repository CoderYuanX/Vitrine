from manager.event_store import EventStore, CAT_COLORS


def _store(tmp_path):
    return EventStore(path=tmp_path / "events.json")


def test_add_then_read_day(tmp_path):
    s = _store(tmp_path)
    eid = s.add("2026-06-21", "写周报", cat="work", time="09:00")
    assert eid
    day = s.for_day(2026, 5, 21)  # month is 0-based to match QML/JS
    assert len(day) == 1
    assert day[0]["title"] == "写周报"
    assert day[0]["cat"] == "work"
    assert day[0]["time"] == "09:00"


def test_persists_across_instances(tmp_path):
    s1 = _store(tmp_path)
    s1.add("2026-06-21", "持久化事件", cat="personal")
    s2 = _store(tmp_path)
    assert len(s2.for_day(2026, 5, 21)) == 1
    assert s2.for_day(2026, 5, 21)[0]["title"] == "持久化事件"


def test_remove(tmp_path):
    s = _store(tmp_path)
    eid = s.add("2026-06-21", "临时", cat="work")
    s.remove(eid)
    assert s.for_day(2026, 5, 21) == []


def test_for_day_sorted_by_time(tmp_path):
    s = _store(tmp_path)
    s.add("2026-06-21", "下午", cat="work", time="14:00")
    s.add("2026-06-21", "上午", cat="work", time="09:00")
    s.add("2026-06-21", "无时间", cat="work", time="")
    titles = [e["title"] for e in s.for_day(2026, 5, 21)]
    # 有时间的按时间升序在前,无时间的排最后
    assert titles == ["上午", "下午", "无时间"]


def test_for_month_filters(tmp_path):
    s = _store(tmp_path)
    s.add("2026-06-01", "六月", cat="work")
    s.add("2026-07-01", "七月", cat="work")
    june = s.for_month(2026, 5)
    assert [e["title"] for e in june] == ["六月"]


def test_dots_maps_day_to_color(tmp_path):
    s = _store(tmp_path)
    s.add("2026-06-21", "会议", cat="meeting")
    dots = s.dots(2026, 5)
    assert dots[21] == CAT_COLORS["meeting"]
    assert 20 not in dots


def test_upcoming_excludes_past_and_sorts(tmp_path):
    s = _store(tmp_path)
    s.add("2026-06-20", "昨天", cat="work")          # 过去
    s.add("2026-06-25", "后天", cat="work", time="10:00")
    s.add("2026-06-22", "明天", cat="work", time="08:00")
    up = s.upcoming("2026-06-21", limit=5)
    assert [e["title"] for e in up] == ["明天", "后天"]


def test_unknown_cat_defaults_to_work(tmp_path):
    s = _store(tmp_path)
    s.add("2026-06-21", "无分类", cat="nope")
    assert s.for_day(2026, 5, 21)[0]["cat"] == "work"


def test_malformed_file_is_ignored(tmp_path):
    p = tmp_path / "events.json"
    p.write_text("{ not json")
    s = EventStore(path=p)
    assert s.for_month(2026, 5) == []
    # 仍可正常写入
    s.add("2026-06-21", "恢复", cat="work")
    assert len(s.for_day(2026, 5, 21)) == 1
