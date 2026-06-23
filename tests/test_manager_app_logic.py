import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402,F401

from manager.app import ManagerApp


def _app():
    return ManagerApp()                        # 仅构造 Gio.Application,不 run/activate


def test_maybe_autostart_core_only_when_disconnected():
    app = _app()
    started = []
    app._start_core = lambda: started.append(1)

    class _Client:
        def __init__(self, conn): self._c = conn
        def is_connected(self): return self._c

    app._client = _Client(True)
    app._maybe_autostart_core()
    assert started == []                       # 已连接 → 不拉核

    app._client = _Client(False)
    app._maybe_autostart_core()
    assert started == [1]                      # 未连接 → 拉核一次


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


def test_reconnect_when_ready_waits_for_fresh_runtime(monkeypatch):
    # 陈旧 runtime(started_at 未变)→ 不重连、继续轮询;新实例(started_at 变了)→ 重连并停轮询
    import manager.app as appmod
    app = _app()
    reconnects = []
    app._reconnect = lambda: reconnects.append(1)
    app._prev_started_at = 100.0               # _start_core 记下的旧实例时间戳
    app._start_polls = 0
    app._start_polls_active = True

    monkeypatch.setattr(appmod, "read_runtime", lambda p: {"started_at": 100.0})
    assert app._reconnect_when_ready() is True  # 陈旧 runtime → 继续轮询
    assert reconnects == []                     # 不误连旧实例

    monkeypatch.setattr(appmod, "read_runtime", lambda p: {"started_at": 200.0})
    assert app._reconnect_when_ready() is False  # 新 runtime → 停轮询
    assert reconnects == [1]                     # 以新 token 重连一次
    assert app._start_polls_active is False


def test_reconnect_when_ready_gives_up_after_timeout(monkeypatch):
    # 一直陈旧 runtime(started_at 未变)→ 轮询到上限(20)后放弃:停轮询且不重连
    import manager.app as appmod
    app = _app()
    reconnects = []
    app._reconnect = lambda: reconnects.append(1)
    app._prev_started_at = 100.0
    app._start_polls = 19                        # 下一次自增到 20 触发超时
    app._start_polls_active = True
    monkeypatch.setattr(appmod, "read_runtime", lambda p: {"started_at": 100.0})
    assert app._reconnect_when_ready() is False  # 到上限 → 停轮询
    assert reconnects == []                      # 超时不重连
    assert app._start_polls_active is False


def test_minimize_hides_to_tray_only_when_tray_present():
    # 最小化(iconify)行为:有托盘 → 收进托盘(返回 True 表示应 hide,不留 dock 条目);
    # 无托盘(降级)→ 保持系统默认最小化(False),否则窗口最小化即消失且无处唤回。
    app = _app()
    app._tray = object()
    assert app._minimize_should_hide(True) is True       # 有托盘 + 最小化 → 收托盘
    assert app._minimize_should_hide(False) is False     # 非最小化(还原)→ 不动作
    app._tray = None
    assert app._minimize_should_hide(True) is False      # 无托盘 → 不接管最小化
