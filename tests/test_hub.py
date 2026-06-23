from core.config import INTERVAL_MAX, INTERVAL_MIN, Config
from core.hub import Conn, Hub
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider


def make_hub():
    return Hub([SystemProvider(), TimeProvider()], Config.default(), token="secret")


def test_topics_and_interval_defaults():
    h = make_hub()
    assert set(h.topics()) == {"system.cpu", "system.mem", "time.now"}
    assert h.provider_id_of("system.cpu") == "system"
    assert h.interval("system.cpu") == 1.0
    assert h.interval("system.mem") == 2.0


def test_interval_override_from_config():
    cfg = Config.default()
    cfg.intervals["system.cpu"] = 7.0
    h = Hub([SystemProvider(), TimeProvider()], cfg, token="secret")
    assert h.interval("system.cpu") == 7.0


def test_subscribe_known_topic():
    h = make_hub()
    conn = Conn(authed=True)
    reply = h.handle(conn, {"id": "r1", "action": "subscribe", "topics": ["system.cpu"]})
    assert "system.cpu" in conn.subscriptions
    assert reply.direct == [{"type": "ok", "id": "r1"}]


def test_subscribe_unknown_topic_errors():
    h = make_hub()
    conn = Conn(authed=True)
    reply = h.handle(conn, {"id": "r2", "action": "subscribe", "topics": ["nope.x"]})
    assert "nope.x" not in conn.subscriptions
    assert reply.direct[0]["type"] == "error"
    assert reply.direct[0]["code"] == "unknown_topic"


def test_unsubscribe():
    h = make_hub()
    conn = Conn(authed=True, subscriptions={"system.cpu"})
    h.handle(conn, {"action": "unsubscribe", "topics": ["system.cpu"]})
    assert "system.cpu" not in conn.subscriptions


def test_providers_snapshot_shape():
    h = make_hub()
    h.record("system.cpu", {"percent": 12.0}, ts=100.0)
    providers = h.providers_snapshot()                    # 纯 providers 数组(core 实时段由 server 组装)
    sysprov = next(p for p in providers if p["id"] == "system")
    assert sysprov["enabled"] is True
    assert sysprov["status"] == "running"
    cpu = next(t for t in sysprov["topics"] if t["topic"] == "system.cpu")
    assert cpu["interval"] == 1.0
    assert cpu["last_value"] == {"percent": 12.0}
    assert cpu["last_ts"] == 100.0
    assert cpu["last_error"] is None


def test_list_providers_signals_status_request():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "r3", "action": "list_providers"})
    # Hub 不直接建完整 status(缺 port/clients/uptime),只signal server 用 id 回 status
    assert reply.status_request_id == "r3"
    assert reply.direct == []


def test_unauthed_non_hello_rejected():
    h = make_hub()
    conn = Conn(authed=False)
    reply = h.handle(conn, {"id": "a", "action": "subscribe", "topics": ["system.cpu"]})
    assert reply.direct[0]["type"] == "error"
    assert reply.direct[0]["code"] == "unauthorized"
    assert reply.close is True
    assert "system.cpu" not in conn.subscriptions


def test_hello_wrong_token_rejected():
    h = make_hub()
    conn = Conn(authed=False)
    reply = h.handle(conn, {"id": "h", "action": "hello", "token": "WRONG"})
    assert reply.direct[0]["code"] == "unauthorized"
    assert reply.close is True
    assert conn.authed is False


def test_hello_correct_token_authes():
    h = make_hub()
    conn = Conn(authed=False)
    reply = h.handle(conn, {"id": "h", "action": "hello", "token": "secret"})
    assert conn.authed is True
    assert reply.direct[0] == {"type": "ok", "id": "h"}


def test_set_provider_disables_and_broadcasts():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "s", "action": "set_provider",
                                         "provider": "system", "enabled": False})
    assert reply.direct[0] == {"type": "ok", "id": "s"}
    assert reply.broadcast_status is True
    assert h.is_active("system.cpu") is False


def test_set_provider_unknown():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"action": "set_provider", "provider": "ghost", "enabled": True})
    assert reply.direct[0]["code"] == "unknown_provider"


def test_set_interval_valid_repolls():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "i", "action": "set_interval",
                                         "topic": "system.cpu", "interval": 3.0})
    assert reply.direct[0] == {"type": "ok", "id": "i"}
    assert h.interval("system.cpu") == 3.0
    assert reply.reset_timer == ["system.cpu"]
    assert reply.broadcast_status is True


def test_set_interval_out_of_range():
    h = make_hub()
    for bad in [0.1, 99999, "x", -1, True, False]:
        reply = h.handle(Conn(authed=True), {"action": "set_interval",
                                             "topic": "system.cpu", "interval": bad})
        assert reply.direct[0]["code"] == "invalid_interval"
    assert h.interval("system.cpu") == 1.0                # 未被改动


def test_set_interval_unknown_topic():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"action": "set_interval", "topic": "no.x", "interval": 2})
    assert reply.direct[0]["code"] == "unknown_topic"


def test_shutdown():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "q", "action": "shutdown"})
    assert reply.direct[0] == {"type": "ok", "id": "q"}
    assert reply.shutdown is True


def test_bad_request_missing_action():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "b"})
    assert reply.direct[0]["code"] == "bad_request"


def test_set_provider_and_interval_persist_via_on_change():
    from core.config import Config
    saved = []
    cfg = Config.default()
    h = Hub([SystemProvider(), TimeProvider()], cfg, token="secret",
            on_change=lambda c: saved.append((dict(c.providers_enabled), dict(c.intervals))))
    h.handle(Conn(authed=True), {"action": "set_provider", "provider": "system", "enabled": False})
    h.handle(Conn(authed=True), {"action": "set_interval", "topic": "system.cpu", "interval": 4.0})
    assert len(saved) == 2                                 # 每次改动都触发持久化
    assert cfg.providers_enabled["system"] is False        # 同步回了 config 对象
    assert cfg.intervals["system.cpu"] == 4.0
    assert saved[-1][0]["system"] is False and saved[-1][1]["system.cpu"] == 4.0
