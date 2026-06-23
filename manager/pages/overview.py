import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class OverviewPage(Gtk.Box):
    def __init__(self, on_start, on_stop):
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

    def set_connection(self, state):
        self._conn.set_text({"connected": "已连接", "disconnected": "未连接",
                             "error": "鉴权失败"}.get(state, state))

    def update(self, status):
        core = status.get("core", {})
        self._info.set_text(
            f"端口:{core.get('port', '-')} | 客户端:{core.get('clients', '-')} "
            f"| 运行时长:{core.get('uptime', 0):.0f}s")
        notices = core.get("notices", [])
        self._notices.set_text("；".join(n.get("message", "") for n in notices))
