from manager.supervisor import CoreSupervisor


def _sup(**kw):
    # idle_add 默认同步执行(把 ws 线程回调切回主线程的真实语义在测试里压平);
    # timeout_add 默认吞掉(不真正调度轮询)
    defaults = dict(on_state=lambda s: None, on_event=lambda m: None,
                    idle_add=lambda fn, *a: fn(*a), timeout_add=lambda ms, fn: None)
    defaults.update(kw)
    return CoreSupervisor(**defaults)


def _client(connected):
    return type("C", (), {"is_connected": lambda self: connected})()


def test_maybe_autostart_only_when_disconnected():
    started = []
    sup = _sup()
    sup.start_core = lambda: started.append(1)

    sup._client = _client(True)
    sup.maybe_autostart()
    assert started == []                       # 已连接 → 不拉核

    sup._client = _client(False)
    sup.maybe_autostart()
    assert started == [1]                       # 未连接 → 拉核一次


def test_connect_wires_client(monkeypatch):
    import manager.supervisor as sup_mod
    monkeypatch.setattr(sup_mod, "discover", lambda rt, cfg: ("127.0.0.1", 5, "tok"))
    created = {}

    class FakeClient:
        def __init__(self, host, port, token, on_event, on_state):
            created.update(host=host, port=port, token=token)
            self.started = False
            self.subs = []
            self.sent = []

        def start(self):
            self.started = True

        def subscribe(self, topics):
            self.subs = list(topics)

        def send(self, msg, on_reply=None):
            self.sent.append(msg)

        def is_connected(self):
            return False

    sup = _sup(client_factory=FakeClient)
    sup.connect()
    assert created["port"] == 5 and created["token"] == "tok"
    assert sup._client.started is True
    assert set(sup._client.subs) == {"system.cpu", "system.mem", "time.now"}
    assert {"id": "ls", "action": "list_providers"} in sup._client.sent


def test_start_core_rolls_back_guard_on_popen_failure(monkeypatch):
    import manager.supervisor as sup_mod
    states = []
    sup = _sup(on_state=lambda s: states.append(s))
    monkeypatch.setattr(sup_mod.subprocess, "Popen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    sup.start_core()
    assert sup._start_polls_active is False     # 防重入标志已回滚
    assert states == ["disconnected"]           # 状态置灰
    again = []
    monkeypatch.setattr(sup_mod.subprocess, "Popen",
                        lambda *a, **k: again.append(1) or type("P", (), {})())
    monkeypatch.setattr(sup_mod, "read_runtime", lambda p: None)
    sup.start_core()
    assert again == [1]                          # 回滚后能再次尝试


def test_reconnect_when_ready_waits_for_fresh_runtime(monkeypatch):
    import manager.supervisor as sup_mod
    sup = _sup()
    reconnects = []
    sup.reconnect = lambda: reconnects.append(1)
    sup._prev_started_at = 100.0
    sup._start_polls = 0
    sup._start_polls_active = True

    monkeypatch.setattr(sup_mod, "read_runtime", lambda p: {"started_at": 100.0})
    assert sup._reconnect_when_ready() is True   # 陈旧 runtime → 继续轮询
    assert reconnects == []

    monkeypatch.setattr(sup_mod, "read_runtime", lambda p: {"started_at": 200.0})
    assert sup._reconnect_when_ready() is False   # 新 runtime → 停轮询
    assert reconnects == [1]
    assert sup._start_polls_active is False


def test_reconnect_when_ready_gives_up_after_timeout(monkeypatch):
    import manager.supervisor as sup_mod
    states = []
    sup = _sup(on_state=lambda s: states.append(s))
    sup.reconnect = lambda: None
    sup._prev_started_at = 100.0
    sup._start_polls = 19
    sup._start_polls_active = True
    monkeypatch.setattr(sup_mod, "read_runtime", lambda p: {"started_at": 100.0})
    assert sup._reconnect_when_ready() is False
    assert sup._start_polls_active is False
    assert states == ["start_failed"]            # 超时给出明确终态


def test_set_interval_reports_error_and_refreshes_status():
    sent = []
    events = []
    sup = _sup(on_event=lambda m: events.append(m))

    class _Cli:
        def send(self, msg, on_reply=None):
            sent.append((msg, on_reply))

    sup._client = _Cli()
    sup.set_interval("system.cpu", 9999)
    assert sent[0][0]["action"] == "set_interval"
    assert sent[0][0]["id"].startswith("set-interval-")

    sent[0][1]({"type": "error", "id": sent[0][0]["id"],
                "code": "invalid_interval", "message": "interval must be valid"})
    assert events[-1]["message"] == "interval must be valid"   # 经 on_event 回显
    assert sent[1][0] == {"id": "refresh", "action": "list_providers"}   # 失败后刷新权威状态


def test_set_provider_uses_unique_ids():
    sent = []

    class _Cli:
        def send(self, msg, on_reply=None):
            sent.append(msg)

    sup = _sup()
    sup._client = _Cli()
    sup.set_provider("system", False)
    sup.set_provider("time", True)
    assert sent[0]["id"] != sent[1]["id"]        # 每次请求 id 唯一
    assert sent[0]["action"] == "set_provider"


def test_stop_core_shutdown_when_connected():
    sent = []

    class _Cli:
        def is_connected(self):
            return True

        def send(self, msg, on_reply=None):
            sent.append(msg)

    sup = _sup()
    sup._client = _Cli()
    sup.stop_core()
    assert sent == [{"action": "shutdown"}]      # 已连 → 走优雅 shutdown


def test_stop_core_sigterm_when_disconnected(monkeypatch):
    import manager.supervisor as sup_mod
    sup = _sup()
    sup._client = None
    monkeypatch.setattr(sup_mod, "read_runtime", lambda p: {"pid": 4321})
    monkeypatch.setattr(sup_mod, "pid_is_core", lambda pid: True)
    killed = []
    monkeypatch.setattr(sup_mod.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    sup.stop_core()
    assert killed == [(4321, sup_mod.signal.SIGTERM)]   # 未连 → 按 pid 发 SIGTERM


def test_start_core_logs_on_popen_failure(monkeypatch, caplog):
    import logging
    import manager.supervisor as sup_mod
    sup = _sup()
    monkeypatch.setattr(sup_mod.subprocess, "Popen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with caplog.at_level(logging.ERROR, logger="manager.supervisor"):
        sup.start_core()
    assert any(r.levelno == logging.ERROR for r in caplog.records)
