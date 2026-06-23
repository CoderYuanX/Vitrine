"""概览页:状态横幅 + 配置告警 + 4 张指标卡 + 设置卡(原型 OVERVIEW 视图,设计规格 §4)。

保留对外 API:OverviewPage(on_start,on_stop,on_autostart) / set_connection / update / set_autostart_active。
连接态决定横幅外观、主按钮、指标是否显「—」。
"""
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from manager.widgets.draw import PillSwitch

# 连接态 → 横幅外观(原型 JS banner*)。
_BANNER = {
    "connected":    ("is-success", "network-transmit-receive-symbolic",
                     "数据底座运行中", "系统数据正通过本地 WebSocket 持续供出。", "停止底座", "danger"),
    "reconnecting": ("is-warning", "content-loading-symbolic",
                     "正在启动底座…", "正在建立 WebSocket 连接并初始化 provider。", "启动中…", "primary"),
    "disconnected": ("is-neutral", "media-playback-stop-symbolic",
                     "数据底座未运行", "点击启动以拉起底座并开始供出系统数据。", "启动底座", "primary"),
}


def _fmt_uptime(t):
    t = int(t)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m {s:02d}s"


class OverviewPage(Gtk.Box):
    def __init__(self, on_start, on_stop, on_autostart, on_tray_close=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.set_margin_top(24); self.set_margin_bottom(24)
        self.set_margin_start(24); self.set_margin_end(24)
        self._on_start, self._on_stop = on_start, on_stop

        self._state = "disconnected"

        self._build_banner()
        self._build_alert()
        self._build_metrics()
        self._build_settings(on_autostart, on_tray_close)
        self._refresh_banner()

    # ---- 状态横幅 ----
    def _build_banner(self):
        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        banner.get_style_context().add_class("mw-banner")
        self._banner = banner
        tile = Gtk.Box(); tile.set_size_request(42, 42)
        tile.get_style_context().add_class("mw-icon-tile")
        self._banner_tile = tile
        tile.set_valign(Gtk.Align.CENTER)
        self._banner_icon = Gtk.Image()
        tile.pack_start(self._banner_icon, True, True, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_valign(Gtk.Align.CENTER)
        self._banner_title = Gtk.Label(xalign=0); self._banner_title.get_style_context().add_class("mw-banner-title")
        self._banner_desc = Gtk.Label(xalign=0); self._banner_desc.get_style_context().add_class("mw-banner-desc")
        self._banner_desc.set_line_wrap(True)
        text.pack_start(self._banner_title, False, False, 0)
        text.pack_start(self._banner_desc, False, False, 0)
        self._action = Gtk.Button()
        self._action.set_valign(Gtk.Align.CENTER)
        self._action.set_size_request(-1, 38)
        self._action.connect("clicked", self._on_action)
        banner.pack_start(tile, False, False, 0)
        banner.pack_start(text, True, True, 0)
        banner.pack_end(self._action, False, False, 0)
        self.pack_start(banner, False, False, 0)

    def _on_action(self, _b):
        if self._state == "connected":
            self._on_stop()
        elif self._state != "reconnecting":
            self._on_start()

    def _refresh_banner(self):
        key = self._state if self._state in _BANNER else "disconnected"
        cls, icon, title, desc, btn_label, btn_kind = _BANNER[key]
        for c in ("is-success", "is-warning", "is-neutral", "is-danger"):
            self._banner.get_style_context().remove_class(c)
        self._banner.get_style_context().add_class(cls)
        tile_ctx = self._banner_tile.get_style_context()
        for c in ("is-success", "is-warning", "is-neutral", "is-brand"):
            tile_ctx.remove_class(c)
        tile_ctx.add_class("is-success" if key == "connected" else (
            "is-warning" if key == "reconnecting" else "is-neutral"))
        self._banner_icon.set_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR)
        ttl_ctx = self._banner_title.get_style_context()
        (ttl_ctx.add_class if key == "connected" else ttl_ctx.remove_class)("is-success")
        self._banner_title.set_text(title)
        self._banner_desc.set_text(desc)
        self._action.set_label(btn_label)
        bctx = self._action.get_style_context()
        for c in ("mw-btn-primary", "mw-btn-danger"):
            bctx.remove_class(c)
        bctx.add_class("mw-btn-danger" if btn_kind == "danger" else "mw-btn-primary")
        self._action.set_sensitive(self._state != "reconnecting")

    # ---- 配置告警(由 notices 驱动) ----
    def _build_alert(self):
        self._alert = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._alert.get_style_context().add_class("mw-alert")
        for m in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
            getattr(self._alert, m)(13)
        ico = Gtk.Image.new_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.BUTTON)
        ico.set_valign(Gtk.Align.START)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._alert_title = Gtk.Label(xalign=0); self._alert_title.get_style_context().add_class("mw-alert-title")
        self._alert_desc = Gtk.Label(xalign=0); self._alert_desc.get_style_context().add_class("mw-alert-desc")
        self._alert_desc.set_line_wrap(True)
        box.pack_start(self._alert_title, False, False, 0)
        box.pack_start(self._alert_desc, False, False, 0)
        close = Gtk.Button(); close.get_style_context().add_class("mw-iconbtn")
        close.set_valign(Gtk.Align.START)
        close.add(Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON))
        close.connect("clicked", lambda *_: self._alert.hide())
        self._alert.pack_start(ico, False, False, 0)
        self._alert.pack_start(box, True, True, 0)
        self._alert.pack_end(close, False, False, 0)
        self.pack_start(self._alert, False, False, 0)
        # 先 show_all 让子节点标记为可见,再 no_show_all + hide;此后 show()/hide() 即可整体切换
        self._alert.show_all()
        self._alert.set_no_show_all(True)
        self._alert.hide()

    # ---- 4 指标卡 ----
    def _build_metrics(self):
        grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        grid.set_homogeneous(True)
        grid.set_hexpand(True)
        grid.set_halign(Gtk.Align.FILL)
        self._metric_grid = grid
        self._metric = {}
        self._metric_cards = []
        self._metric_widgets = {}
        specs = [("port", "监听端口", "ws://127.0.0.1"),
                 ("clients", "已连接客户端", "WebView 订阅者"),
                 ("uptime", "运行时长", "自上次启动"),
                 ("version", "底座版本", "data-base")]
        for key, label, foot in specs:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.get_style_context().add_class("mw-card")
            card.get_style_context().add_class("mw-metric-card")   # 内边距 16(CSS),高度随内容
            card.set_hexpand(True)
            card.set_halign(Gtk.Align.FILL)
            card.set_valign(Gtk.Align.START)                       # 卡片不被纵向拉伸
            l = Gtk.Label(label=label, xalign=0); l.get_style_context().add_class("mw-metric-label")
            v = Gtk.Label(label="—", xalign=0); v.get_style_context().add_class("mw-metric-value")
            f = Gtk.Label(label=foot, xalign=0); f.get_style_context().add_class("mw-metric-foot")
            v.set_margin_top(6)
            f.set_margin_top(4)
            card.pack_start(l, False, False, 0)
            card.pack_start(v, False, False, 0)
            card.pack_start(f, False, False, 0)
            self._metric[key] = v
            self._metric_widgets[key] = (l, v, f)
            self._metric_cards.append(card)
            grid.pack_start(card, True, True, 0)
        self._metric["version"].set_text("v0.1.0")        # 静态
        self.pack_start(grid, False, True, 0)

    # ---- 设置卡 ----
    def _build_settings(self, on_autostart, on_tray_close=None):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.get_style_context().add_class("mw-card")

        def row(title, desc, trailing, divider):
            r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            for m in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
                getattr(r, m)(16)
            tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            t = Gtk.Label(label=title, xalign=0); t.get_style_context().add_class("mw-h-14-600")
            d = Gtk.Label(label=desc, xalign=0); d.get_style_context().add_class("mw-sub-12")
            d.set_line_wrap(True)
            tb.pack_start(t, False, False, 0); tb.pack_start(d, False, False, 0)
            r.pack_start(tb, True, True, 0)
            trailing.set_valign(Gtk.Align.CENTER)
            r.pack_end(trailing, False, False, 0)
            wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            wrap.pack_start(r, False, False, 0)
            if divider:
                sep = Gtk.Box(); sep.get_style_context().add_class("mw-row-divider")
                sep.set_size_request(-1, 1)
                wrap.pack_start(sep, False, False, 0)
            card.pack_start(wrap, False, False, 0)

        from core.autostart import is_autostart_enabled
        self._autostart = PillSwitch(active=is_autostart_enabled())
        self._autostart_handler = self._autostart.connect("toggled", lambda _s, v: on_autostart(v))
        row("开机自启", "登录桌面时自动启动数据底座（写入 autostart desktop 文件）",
            self._autostart, divider=True)

        # 托盘行为:接 close_to_tray 偏好。开=关窗静默隐藏到托盘;关=关窗时直接退出。
        # 偏好未设过(None)默认开(与关窗对话框的推荐项一致)。无托盘时由 set_tray_available 置灰。
        from manager.settings import load_close_to_tray
        self._on_tray_close = on_tray_close
        self._tray_close = PillSwitch(active=load_close_to_tray() is not False)
        self._tray_close_handler = self._tray_close.connect(
            "toggled", lambda _s, v: self._on_tray_close(v) if self._on_tray_close else None)
        row("托盘行为", "开启后关闭窗口仅隐藏到托盘、底座继续后台运行;关闭则点 × 时直接退出。",
            self._tray_close, divider=False)
        self.pack_start(card, False, False, 0)

    # ---- 对外 API ----
    def set_autostart_active(self, enabled):
        self._autostart.handler_block(self._autostart_handler)
        self._autostart.set_active(bool(enabled))
        self._autostart.handler_unblock(self._autostart_handler)

    def set_tray_close_active(self, enabled):
        # 与关窗对话框「记住我的选择」联动:程序化同步,阻塞信号防回环
        self._tray_close.handler_block(self._tray_close_handler)
        self._tray_close.set_active(bool(enabled))
        self._tray_close.handler_unblock(self._tray_close_handler)

    def set_tray_available(self, available):
        # 无托盘(缺 AyatanaAppIndicator3 降级)时,关窗只能退出,托盘开关无意义 → 置灰
        self._tray_close.set_switch_sensitive(bool(available))

    def set_connection(self, state):
        self._state = state if state in _BANNER else (
            "connected" if state == "connected" else "disconnected")
        self._refresh_banner()
        if self._state != "connected":                    # 断开 → 指标显 —
            for k in ("port", "clients", "uptime"):
                self._metric[k].set_text("—")
                self._metric[k].get_style_context().add_class("is-off")

    def update(self, status):
        core = status.get("core", {})
        if core.get("port") is not None:                  # 有端口即已连上,填指标(不依赖 set_connection 顺序)
            for k in ("port", "clients", "uptime"):
                self._metric[k].get_style_context().remove_class("is-off")
            self._metric["port"].set_text(str(core.get("port", "—")))
            self._metric["clients"].set_text(str(core.get("clients", "—")))
            self._metric["uptime"].set_text(_fmt_uptime(core.get("uptime", 0)))
        notices = core.get("notices", [])
        if notices:
            first = notices[0]
            self._alert_title.set_text(first.get("message", "配置异常"))
            self._alert_desc.set_text(first.get("detail",
                "检测到配置解析失败，已生成新配置并备份原文件。所有刷新间隔已恢复默认。"))
            self._alert.show()                            # 子节点已在 build 时标记可见
        else:
            self._alert.hide()
