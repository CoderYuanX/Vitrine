import os
import signal
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from core.config import default_config_path
from core.state import default_state_dir, pid_is_core, read_runtime
from manager.discovery import discover
from manager.pages.datasources import DataSourcesPage
from manager.pages.overview import OverviewPage
from manager.pages.widgets_placeholder import WidgetsPlaceholderPage
from manager.ws_client import CoreClient


class ManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.managewidgets.Manager")
        self._client = None

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self, title="小组件管理器")
        win.set_default_size(560, 460)
        nb = Gtk.Notebook()
        self._overview = OverviewPage(on_start=self._start_core, on_stop=self._stop_core)
        self._datasources = DataSourcesPage(on_set_provider=self._set_provider,
                                            on_set_interval=self._set_interval)
        nb.append_page(self._overview, Gtk.Label(label="概览"))
        nb.append_page(self._datasources, Gtk.Label(label="数据源"))
        nb.append_page(WidgetsPlaceholderPage(), Gtk.Label(label="小组件"))
        win.add(nb)
        win.connect("destroy", lambda *_: self._shutdown_client())
        win.show_all()
        self._connect_client()

    def _runtime_path(self):
        return default_state_dir() / "core.json"

    def _connect_client(self):
        host, port, token = discover(self._runtime_path(), default_config_path())
        self._client = CoreClient(host, port, token,
                                  on_event=lambda m: GLib.idle_add(self._on_event, m),
                                  on_state=lambda s: GLib.idle_add(self._overview.set_connection, s))
        self._client.start()
        self._client.subscribe(["system.cpu", "system.mem", "time.now"])
        self._client.send({"id": "ls", "action": "list_providers"})

    def _on_event(self, msg):
        if msg.get("type") == "data":
            self._datasources.apply_data(msg["topic"], msg["data"])
        elif msg.get("type") == "status":
            self._overview.update(msg["status"])
            self._datasources.update(msg["status"])
        return False

    def _start_core(self):
        # 拉起底座子进程后,轮询 runtime 文件出现 → 用新 token 重建客户端真正接上
        if getattr(self, "_start_polls_active", False):
            return                                        # 防重入:已有启动/轮询周期在跑
        self._start_polls_active = True
        subprocess.Popen([sys.executable, "-m", "core"])
        self._start_polls = 0
        GLib.timeout_add(500, self._reconnect_when_ready)

    def _reconnect_when_ready(self):
        self._start_polls += 1
        if self._runtime_path().exists():
            self._start_polls_active = False
            self._reconnect()
            return False                                  # 停止轮询
        if self._start_polls >= 20:                       # 最多 ~10s,耗尽也清标志
            self._start_polls_active = False
            return False
        return True

    def _reconnect(self):
        if self._client:
            self._client.stop()
        self._connect_client()                            # 重新 discover(拿到新 token)再连

    def _stop_core(self):
        # 首选 WS shutdown(与谁拉起无关);WS 不可用→校验可信 pid 后 SIGTERM 兜底(spec §3.7)
        if self._client and self._client.is_connected():
            self._client.send({"action": "shutdown"})
            return
        rt = read_runtime(self._runtime_path())
        if rt and rt.get("pid") and pid_is_core(rt["pid"]):
            try:
                os.kill(rt["pid"], signal.SIGTERM)
            except OSError:
                pass

    def _set_provider(self, pid, enabled):
        if self._client:
            self._client.send({"action": "set_provider", "provider": pid, "enabled": enabled})

    def _set_interval(self, topic, interval):
        if self._client:
            self._client.send({"action": "set_interval", "topic": topic, "interval": interval})

    def _shutdown_client(self):
        if self._client:
            self._client.stop()


def main(argv=None) -> int:
    app = ManagerApp()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
