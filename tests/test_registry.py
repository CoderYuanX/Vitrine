import json
from manager.registry import WidgetRegistry


def test_discover_empty(tmp_path):
    assert WidgetRegistry(tmp_path).discover() == []


def test_discover_one(tmp_path):
    d = tmp_path / "Clock"; d.mkdir()
    (d / "widget.json").write_text(json.dumps(
        {"id": "clock", "name": "时钟", "qml": "Clock.qml", "defaultSize": [320, 210]}))
    (d / "Clock.qml").write_text("x")
    r = WidgetRegistry(tmp_path).discover()
    assert len(r) == 1
    assert r[0]["id"] == "clock"
    assert r[0]["name"] == "时钟"
    assert r[0]["qml"].endswith("Clock/Clock.qml")
    assert r[0]["default_size"] == [320, 210]


def test_skip_dir_without_metadata(tmp_path):
    (tmp_path / "Empty").mkdir()
    assert WidgetRegistry(tmp_path).discover() == []


def test_skip_bad_json(tmp_path):
    d = tmp_path / "Bad"; d.mkdir()
    (d / "widget.json").write_text("{ not json")
    assert WidgetRegistry(tmp_path).discover() == []


def test_category_and_implemented_defaults(tmp_path):
    d = tmp_path / "Clock"; d.mkdir()
    (d / "widget.json").write_text(json.dumps({"id": "clock", "name": "时钟"}))
    r = WidgetRegistry(tmp_path).discover()[0]
    assert r["category"] == "clock"      # 默认 = id
    assert r["implemented"] is True       # 默认 True


def test_category_and_implemented_explicit(tmp_path):
    d = tmp_path / "Weather"; d.mkdir()
    (d / "widget.json").write_text(json.dumps(
        {"id": "weather", "name": "天气", "category": "weather", "implemented": False}))
    r = WidgetRegistry(tmp_path).discover()[0]
    assert r["category"] == "weather"
    assert r["implemented"] is False
