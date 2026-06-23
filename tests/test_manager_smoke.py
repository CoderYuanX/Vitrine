import os

import pytest

pytest.importorskip("gi")
gi = __import__("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk    # noqa: E402

# 无显示环境(CI)跳过:GTK 需要 X/Wayland
HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
pytestmark = pytest.mark.skipif(not HAS_DISPLAY, reason="需要图形显示")


def test_pages_construct():
    from manager.pages.overview import OverviewPage
    from manager.pages.datasources import DataSourcesPage
    from manager.pages.widgets_placeholder import WidgetsPlaceholderPage

    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None, on_autostart=lambda enabled: None)
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    wp = WidgetsPlaceholderPage()
    assert isinstance(ov, Gtk.Box) and isinstance(ds, Gtk.Box) and isinstance(wp, Gtk.Box)


def test_datasources_update_renders_topics():
    from manager.pages.datasources import DataSourcesPage
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    snap = {
        "core": {"clients": 1, "uptime": 1.0, "version": "0.1.0", "notices": []},
        "providers": [{"id": "system", "enabled": True, "status": "running", "topics": [
            {"topic": "system.cpu", "interval": 1.0, "last_value": {"percent": 5.0},
             "last_ts": 1.0, "last_error": None}]}],
    }
    ds.update(snap)                                       # 不抛即通过
    assert ds.has_topic_row("system.cpu")


def test_datasources_group_visible_after_update():
    # 回归:动态新增的 provider 组 frame 必须 show_all,否则数据源页一片空白
    # (窗口 show_all 早于数据到达,后加的子树默认不可见)。
    from manager.pages.datasources import DataSourcesPage
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    ds.update({"providers": [{"id": "system", "enabled": True, "status": "running",
        "topics": [{"topic": "system.cpu", "interval": 1.0, "last_value": {"percent": 5.0},
                    "last_ts": 1.0, "last_error": None}]}]})
    assert ds._switches["system"]["switch"].get_visible() is True   # 启用开关可见
    assert ds._groups["system"].get_visible() is True               # 组容器可见
    assert ds._rows["system.cpu"]["spin"].get_visible() is True     # 间隔 SpinButton 可见


def test_datasources_syncs_state_without_feedback_loop():
    # 别的客户端改了 provider/间隔后,下一帧 status 必须把开关与 SpinButton 同步到新状态,
    # 且程序化同步不得回环触发 set_provider/set_interval。
    from manager.pages.datasources import DataSourcesPage
    prov_calls, iv_calls = [], []
    ds = DataSourcesPage(on_set_provider=lambda p, e: prov_calls.append((p, e)),
                         on_set_interval=lambda t, i: iv_calls.append((t, i)))

    def snap(enabled, interval):
        return {"core": {}, "providers": [{"id": "system", "enabled": enabled, "status": "running",
                "topics": [{"topic": "system.cpu", "interval": interval, "last_value": None,
                            "last_ts": None, "last_error": None}]}]}

    ds.update(snap(True, 1.0))
    sw = ds._switches["system"]["switch"]
    spin = ds._rows["system.cpu"]["spin"]
    assert sw.get_active() is True and spin.get_value() == 1.0

    ds.update(snap(False, 5.0))                           # provider 关掉、间隔改成 5s
    assert sw.get_active() is False                       # 开关已同步
    assert spin.get_value() == 5.0                        # 间隔已同步
    assert prov_calls == [] and iv_calls == []            # 程序化同步未回环触发控制命令


def test_datasources_apply_data_skips_redundant_redraw():
    # status 心跳每 ~2s 携 last_value 重放,值未变时不应反复 set_text。
    # apply_data 以返回值表明是否真的更新了(供避免无谓重绘)。
    from manager.pages.datasources import DataSourcesPage
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    ds.update({"providers": [{"id": "system", "enabled": True, "status": "running",
        "topics": [{"topic": "system.cpu", "interval": 1.0, "last_value": None,
                    "last_ts": None, "last_error": None}]}]})
    assert ds.apply_data("system.cpu", {"percent": 5.0}) is True   # 首次 → 更新
    assert ds.apply_data("system.cpu", {"percent": 5.0}) is False  # 同值 → 跳过
    assert ds.apply_data("system.cpu", {"percent": 6.0}) is True   # 变化 → 更新
    assert ds.apply_data("unknown.topic", 1) is False             # 无此行 → 不动作


def test_overview_autostart_sync_no_feedback_loop():
    from manager.pages.overview import OverviewPage
    calls = []
    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda e: calls.append(e))
    ov.set_autostart_active(True)
    assert ov._autostart.get_active() is True
    assert calls == []                        # 程序化同步未回环触发 on_autostart
