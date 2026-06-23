import os

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3  # noqa: F401
    HAS_INDICATOR = True
except (ValueError, ImportError):
    HAS_INDICATOR = False

HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
pytestmark = pytest.mark.skipif(
    not (HAS_DISPLAY and HAS_INDICATOR), reason="需要图形显示与 AyatanaAppIndicator3")


def _tray(calls):
    from manager.tray import TrayIndicator
    return TrayIndicator(
        on_toggle_window=lambda: calls.append("toggle"),
        on_start_core=lambda: calls.append("start"),
        on_stop_core=lambda: calls.append("stop"),
        on_set_autostart=lambda e: calls.append(("autostart", e)),
        on_quit=lambda: calls.append("quit"),
        autostart_enabled=False,
    )


def test_tray_constructs_and_updates_without_feedback_loop():
    calls = []
    tray = _tray(calls)
    tray.set_connection("connected", 35355)        # 不抛
    tray.set_connection("disconnected")            # 沿用上次端口/切灰
    tray.set_connection("error")
    tray.refresh_window_item(True)
    tray.refresh_window_item(False)
    tray.set_autostart_active(True)                # 程序化同步:不得回环触发 on_set_autostart
    assert ("autostart", True) not in calls
    assert ("autostart", False) not in calls


def test_tray_menu_callbacks_fire():
    calls = []
    tray = _tray(calls)
    tray._item_window.emit("activate")
    tray._item_start.emit("activate")
    tray._item_stop.emit("activate")
    tray._item_quit.emit("activate")
    assert calls == ["toggle", "start", "stop", "quit"]
    tray._item_autostart.set_active(True)          # 用户手动切换(未阻塞)→ 触发回调
    assert ("autostart", True) in calls
