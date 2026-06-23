import json
import logging
import time

import pytest
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed

from core.config import Config
from core.hub import Hub
from core.providers.base import Provider
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider
from core.server import start_in_thread


def test_start_in_thread_raises_when_unbindable():
    # 不可绑定的地址(RFC5737 TEST-NET-1,本机没有该 IP)→ 首选端口与端口 0 两次 bind 都失败。
    # start_in_thread 必须把异常抛回调用方,而非空等 5s 后返回 port=None。
    with pytest.raises(OSError):
        start_in_thread(_hub(), "192.0.2.1", 0)


def _hub():
    return Hub([SystemProvider(), TimeProvider()], Config.default(), token="secret")


class BoomProvider(Provider):
    id = "boom"

    def topics(self):
        return ["boom.x"]

    def default_interval(self, topic):
        return 0.5

    def poll(self, topic):
        raise RuntimeError("boom")


# 注意:server 每 ~2s 广播一次 status 心跳,故 data/ok/status 帧会交错。
# 所有断言都按"读到匹配帧为止"进行,绝不假设帧顺序。
def _recv(ws):
    return json.loads(ws.recv(timeout=2))


def _recv_until(ws, pred, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        try:
            m = json.loads(ws.recv(timeout=timeout))
        except Exception:
            break
        if pred(m):
            return m
    raise AssertionError("未在超时内收到期望帧")


def _ok(ws, rid):
    return _recv_until(ws, lambda m: m.get("type") in ("ok", "error") and m.get("id") == rid)


def _hello(ws):
    ws.send(json.dumps({"id": "h", "action": "hello", "token": "secret"}))
    assert _ok(ws, "h")["type"] == "ok"


def test_subscribe_receives_data():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            ws.send(json.dumps({"id": "s", "action": "subscribe", "topics": ["time.now"]}))
            assert _ok(ws, "s")["type"] == "ok"
            msg = _recv_until(ws, lambda m: m.get("type") == "data" and m.get("topic") == "time.now")
            assert "iso" in msg["data"]
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_unauthed_data_request_closed():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            ws.send(json.dumps({"action": "subscribe", "topics": ["time.now"]}))
            reply = _recv(ws)
            assert reply["code"] == "unauthorized"
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_set_interval_changes_push_rate():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            ws.send(json.dumps({"id": "iv", "action": "set_interval", "topic": "time.now", "interval": 0.5}))
            assert _ok(ws, "iv")["type"] == "ok"
            ws.send(json.dumps({"id": "s", "action": "subscribe", "topics": ["time.now"]}))
            assert _ok(ws, "s")["type"] == "ok"
            # 0.5s 周期,~1.6s 内应收到 ≥2 帧 time.now data
            deadline = time.time() + 1.6
            count = 0
            while time.time() < deadline:
                try:
                    m = json.loads(ws.recv(timeout=2))
                except Exception:
                    break
                if m.get("type") == "data" and m.get("topic") == "time.now":
                    count += 1
            assert count >= 2
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_disable_provider_stops_topic():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            ws.send(json.dumps({"id": "s", "action": "subscribe", "topics": ["time.now"]}))
            assert _ok(ws, "s")["type"] == "ok"
            _recv_until(ws, lambda m: m.get("type") == "data" and m.get("topic") == "time.now")
            ws.send(json.dumps({"id": "d", "action": "set_provider", "provider": "time", "enabled": False}))
            assert _ok(ws, "d")["type"] == "ok"
            time.sleep(0.6)                              # 让在途帧排空
            # 之后 1.5s 内不应再出现 time.now 的 data(status 心跳帧会被忽略)
            drained = True
            end = time.time() + 1.5
            while time.time() < end:
                try:
                    m = json.loads(ws.recv(timeout=2))
                except Exception:
                    break
                if m.get("type") == "data" and m.get("topic") == "time.now":
                    drained = False
                    break
            assert drained
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_apply_effects_restarts_stops_and_starts_topic_tasks():
    import asyncio

    from core.hub import Conn
    from core.server import CoreServer

    async def run():
        hub = Hub([TimeProvider()], Config.default(), token="secret")
        server = CoreServer(hub, heartbeat=0)
        server._loop = asyncio.get_running_loop()

        server._start_topic("time.now")
        original = server._tasks["time.now"]

        interval_reply = hub.handle(Conn(authed=True), {
            "id": "iv", "action": "set_interval",
            "topic": "time.now", "interval": 0.5,
        })
        server._apply_effects(interval_reply)
        restarted = server._tasks["time.now"]
        await asyncio.sleep(0)

        assert restarted is not original
        assert original.cancelled()
        assert not restarted.done()

        disable_reply = hub.handle(Conn(authed=True), {
            "id": "off", "action": "set_provider",
            "provider": "time", "enabled": False,
        })
        server._apply_effects(disable_reply)
        await asyncio.sleep(0)
        assert server._tasks["time.now"].done()

        enable_reply = hub.handle(Conn(authed=True), {
            "id": "on", "action": "set_provider",
            "provider": "time", "enabled": True,
        })
        server._apply_effects(enable_reply)
        restarted_after_enable = server._tasks["time.now"]
        assert not restarted_after_enable.done()

        restarted_after_enable.cancel()
        await asyncio.sleep(0)

    asyncio.run(run())


def test_concurrent_auth_gate_keeps_unauthorized_client_isolated():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as good:
            _hello(good)
            with connect(f"ws://127.0.0.1:{port}") as bad:
                bad.send(json.dumps({"id": "bad", "action": "list_providers"}))
                reply = _recv(bad)
                assert reply["code"] == "unauthorized"

                with pytest.raises(ConnectionClosed):
                    bad.recv(timeout=1)

            good.send(json.dumps({"id": "ls", "action": "list_providers"}))
            status = _recv_until(good, lambda m: m.get("type") == "status" and m.get("id") == "ls")
            assert status["status"]["core"]["clients"] == 1
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_bad_token_rejects_and_closes_connection():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            ws.send(json.dumps({"id": "h", "action": "hello", "token": "WRONG"}))
            reply = _recv(ws)
            assert reply["type"] == "error"
            assert reply["code"] == "unauthorized"

            with pytest.raises(ConnectionClosed):
                ws.recv(timeout=1)

        with connect(f"ws://127.0.0.1:{port}") as good:
            _hello(good)
            good.send(json.dumps({"id": "ls", "action": "list_providers"}))
            status = _recv_until(good, lambda m: m.get("type") == "status" and m.get("id") == "ls")
            assert status["status"]["core"]["clients"] == 1
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_broadcast_removes_dead_connections():
    # 广播时 send 失败(对端已断)的连接必须就地从 _conns 移除,
    # 否则每次心跳/推送都对死连接做无效 send,直到 recv 循环才察觉。
    import asyncio

    from core.hub import Conn
    from core.server import CoreServer

    server = CoreServer(_hub())

    class GoodWS:
        def __init__(self):
            self.sent = []

        async def send(self, frame):
            self.sent.append(frame)

    class DeadWS:
        async def send(self, frame):
            raise ConnectionError("peer gone")

    good, dead = GoodWS(), DeadWS()
    server._conns[good] = Conn(authed=True)
    server._conns[dead] = Conn(authed=True)

    asyncio.run(server._broadcast_status())

    assert dead not in server._conns                     # 死连接被清理
    assert good in server._conns                          # 正常连接保留
    assert len(good.sent) == 1                            # 正常连接照常收到


def test_provider_error_broadcasts_status():
    hub = Hub([BoomProvider()], Config.default(), token="secret")
    server, thread, port = start_in_thread(hub, "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            # poll 抛异常后 server 立即广播 status:provider=error、topic.last_error 有值
            status = _recv_until(
                ws,
                lambda m: m.get("type") == "status"
                and any(p["id"] == "boom" and p["status"] == "error"
                        for p in m["status"]["providers"]),
                timeout=4,
            )["status"]
            boom = next(p for p in status["providers"] if p["id"] == "boom")
            assert boom["topics"][0]["last_error"] is not None
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_provider_poll_error_written_to_log(tmp_path):
    from core import logs

    logs.setup_logging("core", log_dir=tmp_path)
    log_path = tmp_path / "core.log"
    hub = Hub([BoomProvider()], Config.default(), token="secret")
    server, thread, port = start_in_thread(hub, "127.0.0.1", 0)
    try:
        deadline = time.time() + 4
        while time.time() < deadline:
            if log_path.exists() and "boom.x" in log_path.read_text():
                break
            time.sleep(0.1)
        text = log_path.read_text()
        assert "boom" in text          # provider id + 异常文本
        assert "boom.x" in text        # topic
        assert "Traceback" in text     # 堆栈
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)
        lg = logging.getLogger("core")                     # 还原,避免污染同文件其它用例
        for h in [h for h in lg.handlers if getattr(h, "_managewidgets", False)]:
            lg.removeHandler(h); h.close()
        lg.propagate = True
