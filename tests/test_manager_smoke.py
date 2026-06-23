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
