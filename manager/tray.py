from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk
from gi.repository import AyatanaAppIndicator3 as AppIndicator

_ICON_DIR = str(Path(__file__).resolve().parent / "assets" / "icons")
_ICON_CONNECTED = "managewidgets-connected"
_ICON_DISCONNECTED = "managewidgets-disconnected"


class TrayIndicator:
    """封装 AyatanaAppIndicator3:托盘图标 + 菜单 + 状态更新。业务逻辑全部经回调注入。"""

    def __init__(self, *, on_toggle_window, on_start_core, on_stop_core,
                 on_set_autostart, on_quit, autostart_enabled=False):
        self._on_set_autostart = on_set_autostart
        self._last_port = None

        # 用 icon theme path + 图标名(标准 GtkIconTheme 解析,跨 dock 比绝对路径稳)
        self._ind = AppIndicator.Indicator.new_with_path(
            "org.managewidgets.Manager",
            _ICON_DISCONNECTED,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
            _ICON_DIR,
        )
        self._ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._ind.set_title("小组件管理器")

        menu = Gtk.Menu()

        self._item_window = Gtk.MenuItem(label="显示面板")
        self._item_window.connect("activate", lambda *_: on_toggle_window())
        menu.append(self._item_window)

        menu.append(Gtk.SeparatorMenuItem())

        self._item_status = Gtk.MenuItem(label="未连接")
        self._item_status.set_sensitive(False)
        menu.append(self._item_status)

        self._item_start = Gtk.MenuItem(label="启动底座")
        self._item_start.connect("activate", lambda *_: on_start_core())
        menu.append(self._item_start)
        self._item_stop = Gtk.MenuItem(label="停止底座")
        self._item_stop.connect("activate", lambda *_: on_stop_core())
        menu.append(self._item_stop)

        self._item_autostart = Gtk.CheckMenuItem(label="开机自启")
        self._item_autostart.set_active(bool(autostart_enabled))
        self._autostart_handler = self._item_autostart.connect(
            "toggled", lambda w: self._on_set_autostart(w.get_active()))
        menu.append(self._item_autostart)

        menu.append(Gtk.SeparatorMenuItem())

        self._item_quit = Gtk.MenuItem(label="退出")
        self._item_quit.connect("activate", lambda *_: on_quit())
        menu.append(self._item_quit)

        menu.show_all()
        self._ind.set_menu(menu)
        self._menu = menu

    def set_connection(self, state, port=None):
        if port is not None:
            self._last_port = port
        if state == "connected":
            text = f"已连接 · 端口 {self._last_port}" if self._last_port else "已连接"
            self._item_status.set_label(text)
            self._ind.set_icon_full(_ICON_CONNECTED, "已连接")
        else:
            label = {"error": "鉴权失败"}.get(state, "未连接")
            self._item_status.set_label(label)
            self._ind.set_icon_full(_ICON_DISCONNECTED, label)

    def set_autostart_active(self, enabled):
        # 同步勾选状态;阻塞 toggled 信号,避免回写又触发 on_set_autostart
        self._item_autostart.handler_block(self._autostart_handler)
        self._item_autostart.set_active(bool(enabled))
        self._item_autostart.handler_unblock(self._autostart_handler)

    def refresh_window_item(self, visible):
        self._item_window.set_label("隐藏面板" if visible else "显示面板")
