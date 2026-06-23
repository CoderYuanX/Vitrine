import json
import time

from websockets.sync.client import connect

from core.config import Config
from core.hub import Hub
from core.providers.base import Provider
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider
from core.server import start_in_thread


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
