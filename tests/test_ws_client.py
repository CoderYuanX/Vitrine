import threading
import time

from core.config import Config
from core.hub import Hub
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider
from core.server import start_in_thread
from manager.ws_client import CoreClient


def _hub():
    return Hub([SystemProvider(), TimeProvider()], Config.default(), token="secret")


def test_client_connects_subscribes_and_receives():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    events = []
    lock = threading.Lock()

    def on_event(msg):
        with lock:
            events.append(msg)

    client = CoreClient("127.0.0.1", port, "secret", on_event=on_event, on_state=lambda s: None)
    client.start()
    client.subscribe(["time.now"])
    try:
        deadline = time.time() + 4
        got = False
        while time.time() < deadline:
            with lock:
                got = any(e.get("type") == "data" and e.get("topic") == "time.now" for e in events)
            if got:
                break
            time.sleep(0.1)
        assert got
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)


def test_send_before_connect_is_queued_and_delivered():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    events = []
    lock = threading.Lock()

    def on_event(m):
        with lock:
            events.append(m)

    client = CoreClient("127.0.0.1", port, "secret", on_event=on_event, on_state=lambda s: None)
    client.start()
    client.send({"id": "ls", "action": "list_providers"})   # 紧接 start,此刻多半还没连上
    try:
        deadline = time.time() + 4
        got = False
        while time.time() < deadline:
            with lock:
                got = any(m.get("type") == "status" and m.get("id") == "ls" for m in events)
            if got:
                break
            time.sleep(0.1)
        assert got                                          # 未连上时入队,连上后送达,不丢
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)


def test_subscribe_after_connected_takes_effect():
    # 显式覆盖 subscribe() 的"已连接 → 立即补订"分支
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    events = []
    lock = threading.Lock()

    def on_event(m):
        with lock:
            events.append(m)

    client = CoreClient("127.0.0.1", port, "secret", on_event=on_event, on_state=lambda s: None)
    client.start()                                       # 注意:连接前不订阅任何 topic
    try:
        deadline = time.time() + 4
        while time.time() < deadline and not client.is_connected():
            time.sleep(0.05)
        assert client.is_connected()                     # 已连接
        client.subscribe(["system.cpu"])                 # 连接后才订阅 → 走即时补订分支
        got = False
        deadline = time.time() + 4
        while time.time() < deadline:
            with lock:
                got = any(m.get("type") == "data" and m.get("topic") == "system.cpu" for m in events)
            if got:
                break
            time.sleep(0.1)
        assert got                                        # 补订生效,收到 system.cpu 数据
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)


def test_stop_interrupts_reconnect_backoff():
    import socket as _socket
    # 动态取一个空闲端口再关闭,确保无人监听(比硬编码 127.0.0.1:1 更稳)
    _s = _socket.socket()
    _s.bind(("127.0.0.1", 0))
    dead_port = _s.getsockname()[1]
    _s.close()
    # 连这个没人监听的端口 → client 进入重连退避;stop() 必须能立刻唤醒并让线程退出
    client = CoreClient("127.0.0.1", dead_port, "secret", on_event=lambda m: None, on_state=lambda s: None)
    client.start()
    time.sleep(0.4)                                       # 让它至少进入一次退避等待
    t0 = time.time()
    client.stop()                                         # 内部 join(timeout=5)
    assert client._thread is not None
    assert not client._thread.is_alive()                 # 线程已退出,无悬挂 daemon
    assert time.time() - t0 < 3                           # 远小于 backoff 上限,证明是被唤醒而非等满


def test_pending_reply_errors_on_teardown():
    # 带 on_reply 的请求在连接被拆除(此处:连到无人监听端口后 stop)时,
    # 回调必须被以 error 兜底触发,且 _pending 清空 —— 否则面板的错误回显会永远等不到
    import socket as _socket
    _s = _socket.socket()
    _s.bind(("127.0.0.1", 0))
    dead_port = _s.getsockname()[1]
    _s.close()
    replies = []
    lock = threading.Lock()

    def on_reply(m):
        with lock:
            replies.append(m)

    client = CoreClient("127.0.0.1", dead_port, "secret",
                        on_event=lambda m: None, on_state=lambda s: None)
    client.start()
    client.send({"id": "si", "action": "set_interval", "topic": "system.cpu", "interval": 1.0},
                on_reply=on_reply)
    time.sleep(0.4)                                       # 让它进入重连退避(始终连不上)
    client.stop()
    with lock:
        assert len(replies) == 1                          # 回调被兜底触发一次
        assert replies[0].get("type") == "error"          # 以 error 形式
    assert not client._pending                            # 无悬挂回调


def test_client_rejected_on_bad_token_then_state_reports():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    states = []
    client = CoreClient("127.0.0.1", port, "WRONG", on_event=lambda m: None,
                        on_state=lambda s: states.append(s))
    client.start()
    try:
        deadline = time.time() + 4
        while time.time() < deadline and "disconnected" not in states:
            time.sleep(0.1)
        assert "disconnected" in states or "error" in states
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)
