from dataclasses import dataclass, field

from core.config import Config
from core.providers.base import Provider


@dataclass
class Conn:
    authed: bool = False
    subscriptions: set = field(default_factory=set)


@dataclass
class Reply:
    direct: list = field(default_factory=list)
    broadcast_status: bool = False
    repoll: list = field(default_factory=list)
    reset_timer: list = field(default_factory=list)
    shutdown: bool = False
    close: bool = False
    status_request_id: object = None                      # 非 None 时 server 据该 id 回完整 status


class Hub:
    def __init__(self, providers: list[Provider], config: Config, token: str, on_change=None):
        self._providers = {p.id: p for p in providers}
        self._config = config
        self._token = token
        self._on_change = on_change            # 配置变更回调:on_change(config) -> None(用于持久化)
        self._topic_provider = {}
        self._defaults = {}
        for p in providers:
            for t in p.topics():
                self._topic_provider[t] = p.id
                self._defaults[t] = p.default_interval(t)
        self._enabled = {pid: config.providers_enabled.get(pid, True) for pid in self._providers}
        self._last = {t: {"value": None, "ts": None, "error": None} for t in self._topic_provider}

    def _persist(self) -> None:
        if self._on_change:
            self._on_change(self._config)

    # ---- 查询 ----
    def topics(self) -> list[str]:
        return list(self._topic_provider)

    def provider_id_of(self, topic: str):
        return self._topic_provider.get(topic)

    def is_active(self, topic: str) -> bool:
        pid = self._topic_provider.get(topic)
        return bool(pid) and self._enabled.get(pid, False)

    def interval(self, topic: str) -> float:
        return float(self._config.intervals.get(topic, self._defaults[topic]))

    def poll(self, topic: str) -> dict:
        return self._providers[self._topic_provider[topic]].poll(topic)

    def record(self, topic: str, value, ts: float, error=None) -> None:
        if topic in self._last:
            self._last[topic] = {"value": value, "ts": ts, "error": error}

    # ---- providers 快照(纯逻辑;core 实时段由 server 组装)----
    def providers_snapshot(self) -> list:
        providers = []
        for pid, p in self._providers.items():
            topics = []
            has_error = False
            for t in p.topics():
                last = self._last[t]
                if last["error"]:
                    has_error = True
                topics.append({
                    "topic": t, "interval": self.interval(t),
                    "last_value": last["value"], "last_ts": last["ts"],
                    "last_error": last["error"],
                })
            if not self._enabled[pid]:
                status = "disabled"
            elif has_error:
                status = "error"
            else:
                status = "running"
            providers.append({"id": pid, "enabled": self._enabled[pid],
                              "status": status, "topics": topics})
        return providers

    # ---- 请求处理(鉴权 + 控制动作 + 校验 + 数据类动作)----
    def handle(self, conn: Conn, msg: dict) -> Reply:
        from core.config import INTERVAL_MAX, INTERVAL_MIN
        if not isinstance(msg, dict) or "action" not in msg:
            return Reply(direct=[{"type": "error", "id": (msg or {}).get("id") if isinstance(msg, dict) else None,
                                  "code": "bad_request", "message": "missing action"}])
        action = msg.get("action")
        rid = msg.get("id")

        # 鉴权门:未鉴权时只允许 hello
        if not conn.authed:
            if action != "hello":
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unauthorized", "message": "must authenticate first"}],
                             close=True)
            if msg.get("token") != self._token:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unauthorized", "message": "bad token"}], close=True)
            conn.authed = True
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "hello":
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "subscribe":
            unknown = [t for t in msg.get("topics", []) if t not in self._topic_provider]
            if unknown:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unknown_topic", "message": f"unknown topic: {unknown[0]}"}])
            conn.subscriptions.update(msg.get("topics", []))
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "unsubscribe":
            conn.subscriptions.difference_update(msg.get("topics", []))
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "list_providers":
            return Reply(status_request_id=rid)            # server 据 id 回完整 status

        if action == "set_provider":
            pid = msg.get("provider")
            if pid not in self._providers:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unknown_provider", "message": f"unknown provider: {pid}"}])
            enabled = bool(msg.get("enabled", True))
            self._enabled[pid] = enabled
            self._config.providers_enabled[pid] = enabled    # 同步回 config
            self._persist()                                  # 持久化(运行中改动写回)
            return Reply(direct=[{"type": "ok", "id": rid}], broadcast_status=True)

        if action == "set_interval":
            topic = msg.get("topic")
            if topic not in self._topic_provider:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unknown_topic", "message": f"unknown topic: {topic}"}])
            iv = msg.get("interval")
            if not isinstance(iv, (int, float)) or isinstance(iv, bool) or not (INTERVAL_MIN <= iv <= INTERVAL_MAX):
                return Reply(direct=[{"type": "error", "id": rid, "code": "invalid_interval",
                                      "message": f"interval must be in [{INTERVAL_MIN}, {INTERVAL_MAX}]"}])
            self._config.intervals[topic] = float(iv)
            self._persist()                                  # 持久化(运行中改动写回)
            return Reply(direct=[{"type": "ok", "id": rid}], broadcast_status=True,
                         repoll=[topic], reset_timer=[topic])

        if action == "shutdown":
            return Reply(direct=[{"type": "ok", "id": rid}], shutdown=True)

        return Reply(direct=[{"type": "error", "id": rid,
                              "code": "bad_request", "message": f"unknown action: {action}"}])
