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

    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None)
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
