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
from manager.settings import (
    autostart_exec_cmd,
    decide_close,
    load_close_to_tray,
    save_close_to_tray,
)
from manager.ws_client import CoreClient


class ManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.managewidgets.Manager")
        self._client = None
        self._win = None
        self._tray = None
        self._held = False
        self._last_port = None
        self._request_seq = 0

    # ---- 生命周期 ----
    def do_activate(self):
        if self._win is not None:                         # 单实例:再次激活只唤出(可能已最小化到托盘的)窗口
            self._win.show_all()
            self._win.present()
            if self._tray:
                self._tray.refresh_window_item(True)
            return
        win = Gtk.ApplicationWindow(application=self, title="小组件管理器")
        self._win = win
        win.set_default_size(560, 460)
        nb = Gtk.Notebook()
        self._overview = OverviewPage(on_start=self._start_core, on_stop=self._stop_core,
                                      on_autostart=self._on_overview_autostart)
        self._datasources = DataSourcesPage(on_set_provider=self._set_provider,
                                            on_set_interval=self._set_interval)
        nb.append_page(self._overview, Gtk.Label(label="概览"))
        nb.append_page(self._datasources, Gtk.Label(label="数据源"))
        nb.append_page(WidgetsPlaceholderPage(), Gtk.Label(label="小组件"))
        win.add(nb)
        win.connect("delete-event", self._on_close)       # 接管 ×,不直接销毁
        win.connect("window-state-event", self._on_window_state)  # 最小化 → 收进托盘,不留 dock 条目
        win.show_all()

        self._tray = self._build_tray()                   # 缺库 → None(降级)
        if self._tray is not None:
            self.hold()                                   # 仅有托盘时 hold,隐藏窗口不退出
            self._held = True
            self._tray.refresh_window_item(True)          # 窗口已 show_all → 菜单初始即「隐藏面板」

        self._connect_client()
        GLib.timeout_add(2000, self._maybe_autostart_core)  # 宽限期:~2s 未连上则拉核

    def _build_tray(self):
        try:
            from core.autostart import is_autostart_enabled
            from manager.tray import TrayIndicator
            return TrayIndicator(
                on_toggle_window=self._toggle_window,
                on_start_core=self._start_core,
                on_stop_core=self._stop_core,
                on_set_autostart=self._on_tray_autostart,
                on_quit=self._quit,
                autostart_enabled=is_autostart_enabled(),
            )
        except Exception as exc:                          # 缺 AyatanaAppIndicator3 等 → 降级(任何托盘初始化失败都不该拖垮面板)
            # 仍保留 catch-all 以兑现「缺库优雅降级」,但打全栈,避免把真实编程错误静默吞成「无托盘」
            import traceback
            print(f"[manager] 托盘不可用,降级为普通窗口: {exc}", file=sys.stderr)
            traceback.print_exc()
            return None

    def _on_close(self, *args):
        action = decide_close(load_close_to_tray())
        if self._tray is None:                            # 无托盘:只能退出
            self._quit()
            return True
        if action == "tray":
            self._hide_window()
            return True
        if action == "quit":
            self._quit()
            return True
        return self._ask_close()                          # "ask"

    def _ask_close(self):
        dlg = Gtk.MessageDialog(transient_for=self._win, modal=True,
                                message_type=Gtk.MessageType.QUESTION, text="关闭窗口")
        dlg.format_secondary_text("最小化到托盘后台继续运行,还是直接退出?")
        dlg.add_button("最小化到托盘", Gtk.ResponseType.YES)
        dlg.add_button("退出", Gtk.ResponseType.NO)
        dlg.set_default_response(Gtk.ResponseType.YES)    # 默认推荐:最小化到托盘
        check = Gtk.CheckButton(label="记住我的选择")
        dlg.get_content_area().pack_start(check, False, False, 6)
        check.show()
        resp = dlg.run()
        remember = check.get_active()
        dlg.destroy()
        if resp == Gtk.ResponseType.YES:
            if remember:
                save_close_to_tray(True)
            self._hide_window()
        elif resp == Gtk.ResponseType.NO:
            if remember:
                save_close_to_tray(False)
            self._quit()
        # 其它(关掉对话框)→ 窗口保持,不动作
        return True

    def _minimize_should_hide(self, iconified):
        # 托盘存在时,最小化(iconify)应改为收进托盘(hide 才能从 dock/任务栏移除条目);
        # 无托盘(降级)时保持系统默认最小化,否则窗口最小化即消失且无处可唤回。
        return bool(iconified) and self._tray is not None

    def _on_window_state(self, win, event):
        from gi.repository import Gdk
        iconified = bool(event.new_window_state & Gdk.WindowState.ICONIFIED)
        if (event.changed_mask & Gdk.WindowState.ICONIFIED) and self._minimize_should_hide(iconified):
            win.deiconify()                                # 清掉 iconified 态,下次唤出才干净
            self._hide_window()                            # hide():从 dock/任务栏彻底移除条目
        return False

    def _hide_window(self):
        self._win.hide()
        if self._tray:
            self._tray.refresh_window_item(False)

    def _toggle_window(self):
        if self._win.get_visible():
            self._win.hide()
            visible = False
        else:
            self._win.show_all()
            self._win.present()
            visible = True
        if self._tray:
            self._tray.refresh_window_item(visible)

    def _quit(self):
        if self._held:
            self.release()
            self._held = False
        if self._client:
            self._client.stop()
        if self._win:
            self._win.destroy()
        self.quit()

    # ---- 连接 / 状态 ----
    def _runtime_path(self):
        return default_state_dir() / "core.json"

    def _connect_client(self):
        host, port, token = discover(self._runtime_path(), default_config_path())
        self._client = CoreClient(host, port, token,
                                  on_event=lambda m: GLib.idle_add(self._on_event, m),
                                  on_state=lambda s: GLib.idle_add(self._on_state, s))
        self._client.start()
        self._client.subscribe(["system.cpu", "system.mem", "time.now"])
        self._client.send({"id": "ls", "action": "list_providers"})

    def _on_state(self, state):
        self._overview.set_connection(state)
        if self._tray:
            self._tray.set_connection(state, self._last_port)
        return False

    def _on_event(self, msg):
        if msg.get("type") == "data":
            self._datasources.apply_data(msg["topic"], msg["data"])
        elif msg.get("type") == "status":
            self._last_port = msg["status"].get("core", {}).get("port")
            self._overview.update(msg["status"])
            self._datasources.update(msg["status"])
            if self._tray:
                self._tray.set_connection("connected", self._last_port)
        elif msg.get("type") == "error":
            self._show_error(msg.get("message") or msg.get("code") or "操作失败")
        return False

    def _show_error(self, message):
        if self._win is None:
            print(f"[manager] {message}", file=sys.stderr)
            return
        dlg = Gtk.MessageDialog(transient_for=self._win, modal=True,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.OK,
                                text="操作失败")
        dlg.format_secondary_text(str(message))
        dlg.run()
        dlg.destroy()

    def _next_request_id(self, prefix):
        self._request_seq += 1
        return f"{prefix}-{self._request_seq}"

    def _request_status_refresh(self):
        if self._client:
            self._client.send({"id": "refresh", "action": "list_providers"})

    def _handle_control_reply(self, reply):
        if reply.get("type") == "error":
            self._show_error(reply.get("message") or reply.get("code") or "操作失败")
            self._request_status_refresh()
        return False

    def _send_control(self, msg):
        if not self._client:
            return
        self._client.send(msg, on_reply=lambda reply: GLib.idle_add(self._handle_control_reply, reply))

    # ---- 启停底座 ----
    def _maybe_autostart_core(self):
        if not (self._client and self._client.is_connected()):
            self._start_core()
        return False

    def _start_core(self):
        if getattr(self, "_start_polls_active", False):
            return
        self._start_polls_active = True
        rt = read_runtime(self._runtime_path())
        self._prev_started_at = rt.get("started_at") if rt else None   # 记旧实例时间戳
        try:
            subprocess.Popen([sys.executable, "-m", "core"])
        except OSError as exc:                            # 拉起失败:回滚防重入标志,否则后续「启动底座」被永久挡住
            print(f"[manager] 启动底座失败: {exc}", file=sys.stderr)
            self._start_polls_active = False
            self._on_state("disconnected")               # 未连上(非鉴权失败),概览/托盘置灰
            return
        self._start_polls = 0
        GLib.timeout_add(500, self._reconnect_when_ready)

    def _reconnect_when_ready(self):
        # 以"runtime 的 started_at 变成新值"为就绪判定:跳过陈旧 runtime,拿到新 token 再连
        self._start_polls += 1
        rt = read_runtime(self._runtime_path())
        if rt and rt.get("started_at") != self._prev_started_at:
            self._start_polls_active = False
            self._reconnect()
            return False
        if self._start_polls >= 20:                       # ~10s 仍无新实例 → 放弃
            self._start_polls_active = False
            self._on_state("start_failed")
            return False
        return True

    def _reconnect(self):
        if self._client:
            self._client.stop()
        self._connect_client()

    def _stop_core(self):
        if self._client and self._client.is_connected():
            self._client.send({"action": "shutdown"})
            return
        rt = read_runtime(self._runtime_path())
        if rt and rt.get("pid") and pid_is_core(rt["pid"]):
            try:
                os.kill(rt["pid"], signal.SIGTERM)
            except OSError:
                pass

    # ---- provider/interval ----
    def _set_provider(self, pid, enabled):
        self._send_control({"id": self._next_request_id("set-provider"),
                            "action": "set_provider", "provider": pid, "enabled": enabled})

    def _set_interval(self, topic, interval):
        self._send_control({"id": self._next_request_id("set-interval"),
                            "action": "set_interval", "topic": topic, "interval": interval})

    # ---- 自启(改为自启面板 -m manager;概览与托盘联动)----
    def _set_autostart(self, enabled):
        from core.autostart import disable_autostart, enable_autostart
        if enabled:
            enable_autostart(autostart_exec_cmd())        # Exec=… -m manager
        else:
            disable_autostart()

    def _on_overview_autostart(self, enabled):
        self._set_autostart(enabled)
        if self._tray:
            self._tray.set_autostart_active(enabled)

    def _on_tray_autostart(self, enabled):
        self._set_autostart(enabled)
        self._overview.set_autostart_active(enabled)


def main(argv=None) -> int:
    app = ManagerApp()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
