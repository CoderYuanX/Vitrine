import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class OverviewPage(Gtk.Box):
    def __init__(self, on_start, on_stop, on_autostart):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_border_width(20)
        self._conn = Gtk.Label(label="未连接", xalign=0)
        self._info = Gtk.Label(label="端口:- | 客户端:- | 运行时长:-", xalign=0)
        self._notices = Gtk.Label(label="", xalign=0)
        self._notices.get_style_context().add_class("error")
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        start_btn = Gtk.Button(label="启动底座")
        stop_btn = Gtk.Button(label="停止底座")
        start_btn.connect("clicked", lambda *_: on_start())
        stop_btn.connect("clicked", lambda *_: on_stop())
        btns.pack_start(start_btn, False, False, 0)
        btns.pack_start(stop_btn, False, False, 0)
        for w in (self._conn, self._info, self._notices, btns):
            self.pack_start(w, False, False, 0)
        self._autostart = Gtk.Switch()
        from core.autostart import is_autostart_enabled
        self._autostart.set_active(is_autostart_enabled())
        self._autostart_handler = self._autostart.connect(
            "notify::active", lambda s, _p: on_autostart(s.get_active()))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.pack_start(Gtk.Label(label="开机自启", xalign=0), False, False, 0)
        row.pack_start(self._autostart, False, False, 0)
        self.pack_start(row, False, False, 0)

    def set_autostart_active(self, enabled):
        # 与托盘项联动:程序化同步,阻塞信号避免回环触发 on_autostart
        self._autostart.handler_block(self._autostart_handler)
        self._autostart.set_active(bool(enabled))
        self._autostart.handler_unblock(self._autostart_handler)

    def set_connection(self, state):
        self._conn.set_text({"connected": "已连接", "disconnected": "未连接",
                             "error": "鉴权失败",
                             "start_failed": "底座启动失败"}.get(state, state))

    def update(self, status):
        core = status.get("core", {})
        self._info.set_text(
            f"端口:{core.get('port', '-')} | 客户端:{core.get('clients', '-')} "
            f"| 运行时长:{core.get('uptime', 0):.0f}s")
        notices = core.get("notices", [])
        self._notices.set_text("；".join(n.get("message", "") for n in notices))
