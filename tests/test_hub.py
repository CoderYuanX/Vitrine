from core.config import Config
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
