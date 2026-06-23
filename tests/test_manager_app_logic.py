import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402,F401

from manager.app import ManagerApp


def _app():
    return ManagerApp()                        # 仅构造 Gio.Application,不 run/activate


def test_set_autostart_uses_manager_exec(monkeypatch):
    import core.autostart as autostart
    captured = []
    monkeypatch.setattr(autostart, "enable_autostart", lambda cmd: captured.append(cmd))
    monkeypatch.setattr(autostart, "disable_autostart", lambda: captured.append("disabled"))
    app = _app()
    app._set_autostart(True)
    assert captured and "-m manager" in captured[0]   # 自启的是面板而非 core
    app._set_autostart(False)
    assert captured[-1] == "disabled"


def test_autostart_cross_sync_no_loop():
    app = _app()
    set_calls, tray_calls, ov_calls = [], [], []
    app._set_autostart = lambda e: set_calls.append(e)
    app._tray = type("T", (), {"set_autostart_active": lambda self, e: tray_calls.append(e)})()
    app._overview = type("O", (), {"set_autostart_active": lambda self, e: ov_calls.append(e)})()

    app._on_overview_autostart(True)           # 概览触发 → 写自启 + 同步托盘(不反向调概览)
    assert set_calls == [True] and tray_calls == [True] and ov_calls == []

    app._on_tray_autostart(False)              # 托盘触发 → 写自启 + 同步概览(不反向调托盘)
    assert set_calls == [True, False] and ov_calls == [False] and tray_calls == [True]


def test_close_with_no_tray_quits(monkeypatch):
    import manager.app as appmod
    monkeypatch.setattr(appmod, "load_close_to_tray", lambda: None)   # 偏好未决定
    app = _app()
    app._tray = None
    quit_calls = []
    app._quit = lambda: quit_calls.append(1)
    assert app._on_close() is True             # 接管关窗事件返回 True
    assert quit_calls == [1]                   # 无托盘 → 直接退出(不隐藏、不 hold)


def test_minimize_hides_to_tray_only_when_tray_present():
    # 最小化(iconify)行为:有托盘 → 收进托盘(返回 True 表示应 hide,不留 dock 条目);
    # 无托盘(降级)→ 保持系统默认最小化(False),否则窗口最小化即消失且无处唤回。
    app = _app()
    app._tray = object()
    assert app._minimize_should_hide(True) is True       # 有托盘 + 最小化 → 收托盘
    assert app._minimize_should_hide(False) is False     # 非最小化(还原)→ 不动作
    app._tray = None
    assert app._minimize_should_hide(True) is False      # 无托盘 → 不接管最小化


def test_on_event_error_shows_message():
    app = _app()
    errors = []
    app._show_error = lambda message: errors.append(message)
    assert app._on_event({"type": "error", "code": "bad_request", "message": "bad input"}) is False
    assert errors == ["bad input"]


def test_show_error_logs(caplog):
    import logging
    app = _app()
    app._win = None
    with caplog.at_level(logging.ERROR, logger="manager.app"):
        app._show_error("boom-msg")
    assert any("boom-msg" in r.getMessage() for r in caplog.records)
