import os
import signal
import subprocess
import sys

from core.config import default_config_path
from core.state import default_state_dir, pid_is_core, read_runtime
from manager.discovery import discover
from manager.ws_client import CoreClient

_SUBSCRIPTIONS = ["system.cpu", "system.mem", "time.now"]


class CoreSupervisor:
    """底座(core)进程与 WS 连接的生命周期管理:发现/连接、拉起/停止、就绪重连、控制下发。

    与 GTK 解耦:把切回主线程的 idle_add 与定时轮询的 timeout_add 作为依赖注入,
    UI 仅通过 on_state(状态字符串)/ on_event(数据/状态/错误帧)两个回调被通知。
    """

    def __init__(self, on_state, on_event, *, idle_add, timeout_add,
                 client_factory=CoreClient, runtime_path=None):
        self._on_state = on_state          # 状态回调(connected/disconnected/error/start_failed)
        self._on_event = on_event          # 事件回调(data/status/error 帧)
        self._idle_add = idle_add          # 把 ws 线程回调切回 GTK 主线程:idle_add(fn, *args)
        self._timeout_add = timeout_add    # 定时轮询:timeout_add(ms, fn),fn 返回 True 续期
        self._client_factory = client_factory
        self._runtime_path = runtime_path or (default_state_dir() / "core.json")
        self._client = None
        self._request_seq = 0
        self._start_polls_active = False   # start_core 防重入
        self._prev_started_at = None       # 拉核前记下的旧实例时间戳(就绪判定基准)
        self._start_polls = 0

    # ---- 连接 ----
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected())

    def connect(self):
        host, port, token = discover(self._runtime_path, default_config_path())
        self._client = self._client_factory(
            host, port, token,
            on_event=lambda m: self._idle_add(self._on_event, m),
            on_state=lambda s: self._idle_add(self._on_state, s))
        self._client.start()
        self._client.subscribe(list(_SUBSCRIPTIONS))
        self._client.send({"id": "ls", "action": "list_providers"})

    def reconnect(self):
        if self._client:
            self._client.stop()
        self.connect()

    def stop_client(self):
        if self._client:
            self._client.stop()

    # ---- 启停底座 ----
    def maybe_autostart(self):
        if not self.is_connected():
            self.start_core()
        return False

    def start_core(self):
        if self._start_polls_active:
            return
        self._start_polls_active = True
        rt = read_runtime(self._runtime_path)
        self._prev_started_at = rt.get("started_at") if rt else None   # 记旧实例时间戳
        try:
            subprocess.Popen([sys.executable, "-m", "core"])
        except OSError as exc:                            # 拉起失败:回滚防重入标志,否则后续启动被永久挡住
            print(f"[manager] 启动底座失败: {exc}", file=sys.stderr)
            self._start_polls_active = False
            self._on_state("disconnected")               # 未连上(非鉴权失败),概览/托盘置灰
            return
        self._start_polls = 0
        self._timeout_add(500, self._reconnect_when_ready)

    def _reconnect_when_ready(self):
        # 以"runtime 的 started_at 变成新值"为就绪判定:跳过陈旧 runtime,拿到新 token 再连
        self._start_polls += 1
        rt = read_runtime(self._runtime_path)
        if rt and rt.get("started_at") != self._prev_started_at:
            self._start_polls_active = False
            self.reconnect()
            return False
        if self._start_polls >= 20:                       # ~10s 仍无新实例 → 放弃
            self._start_polls_active = False
            self._on_state("start_failed")               # 不再静默失败
            return False
        return True

    def stop_core(self):
        if self.is_connected():
            self._client.send({"action": "shutdown"})
            return
        rt = read_runtime(self._runtime_path)
        if rt and rt.get("pid") and pid_is_core(rt["pid"]):
            try:
                os.kill(rt["pid"], signal.SIGTERM)
            except OSError:
                pass

    # ---- provider/interval 控制(带 id + on_reply,失败回显并刷新权威状态)----
    def _next_request_id(self, prefix):
        self._request_seq += 1
        return f"{prefix}-{self._request_seq}"

    def _request_status_refresh(self):
        if self._client:
            self._client.send({"id": "refresh", "action": "list_providers"})

    def _handle_control_reply(self, reply):
        if reply.get("type") == "error":
            self._on_event(reply)                         # 经 on_event 的 error 分支回显
            self._request_status_refresh()
        return False

    def _send_control(self, msg):
        if not self._client:
            return
        self._client.send(msg, on_reply=lambda reply: self._idle_add(self._handle_control_reply, reply))

    def set_provider(self, pid, enabled):
        self._send_control({"id": self._next_request_id("set-provider"),
                            "action": "set_provider", "provider": pid, "enabled": enabled})

    def set_interval(self, topic, interval):
        self._send_control({"id": self._next_request_id("set-interval"),
                            "action": "set_interval", "topic": topic, "interval": interval})
