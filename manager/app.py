import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from manager import theme
from manager.pages.datasources import DataSourcesPage
from manager.pages.overview import OverviewPage
from manager.pages.widgets import WidgetsPage
from manager.shell import MainShell
from manager.settings import (
    autostart_exec_cmd,
    decide_close,
    load_close_to_tray,
    save_close_to_tray,
)
from manager.supervisor import CoreSupervisor


class ManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.managewidgets.Manager")
        self._win = None
        self._tray = None
        self._held = False
        self._last_port = None
        # 底座进程/连接的生命周期交给 supervisor;UI 仅通过 on_state/on_event 被通知
        self._sup = CoreSupervisor(on_state=self._on_state, on_event=self._on_event,
                                   idle_add=GLib.idle_add, timeout_add=GLib.timeout_add)

    # ---- 生命周期 ----
    def do_activate(self):
        if self._win is not None:                         # 单实例:再次激活只唤出(可能已最小化到托盘的)窗口
            self._win.show_all()
            self._win.present()
            if self._tray:
                self._tray.refresh_window_item(True)
            return
        theme.apply()                                     # Soft Admin Blue 主题 + 随包字体
        win = Gtk.ApplicationWindow(application=self, title="小组件管理器")
        self._win = win
        win.set_default_size(1040, 680)
        self._overview = OverviewPage(on_start=self._sup.start_core, on_stop=self._sup.stop_core,
                                      on_autostart=self._on_overview_autostart)
        self._datasources = DataSourcesPage(on_set_provider=self._sup.set_provider,
                                            on_set_interval=self._sup.set_interval)
        self._shell = MainShell({"overview": self._overview, "sources": self._datasources,
                                 "widgets": WidgetsPage()})
        win.add(self._shell)
        win.connect("delete-event", self._on_close)       # 接管 ×,不直接销毁
        win.connect("window-state-event", self._on_window_state)  # 最小化 → 收进托盘,不留 dock 条目
        win.show_all()

        self._tray = self._build_tray()                   # 缺库 → None(降级)
        if self._tray is not None:
            self.hold()                                   # 仅有托盘时 hold,隐藏窗口不退出
            self._held = True
            self._tray.refresh_window_item(True)          # 窗口已 show_all → 菜单初始即「隐藏面板」

        self._sup.connect()
        GLib.timeout_add(2000, self._sup.maybe_autostart)  # 宽限期:~2s 未连上则拉核

    def _build_tray(self):
        try:
            from core.autostart import is_autostart_enabled
            from manager.tray import TrayIndicator
            return TrayIndicator(
                on_toggle_window=self._toggle_window,
                on_start_core=self._sup.start_core,
                on_stop_core=self._sup.stop_core,
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
        self._sup.stop_client()
        if self._win:
            self._win.destroy()
        self.quit()

    # ---- 状态/事件回调(由 supervisor 触发,已切回主线程)----
    def _on_state(self, state):
        self._shell.set_connection(state)                 # 顶栏 chip + 侧栏状态 + 概览横幅
        if self._tray:
            self._tray.set_connection(state, self._last_port)
        return False

    def _on_event(self, msg):
        if msg.get("type") == "data":
            self._datasources.apply_data(msg["topic"], msg["data"])
        elif msg.get("type") == "status":
            self._last_port = msg["status"].get("core", {}).get("port")
            self._shell.update_status(msg["status"])      # 概览指标 + 数据源 + 侧栏 provider 计数
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

    # ---- 自启(自启面板 -m manager;概览与托盘联动)----
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
