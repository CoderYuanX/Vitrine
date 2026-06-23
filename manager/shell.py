"""主窗外壳:侧栏(品牌 + 导航 + 状态)+ 顶栏(标题/副标题 + 连接 chip)+ Gtk.Stack 内容区。

取代旧的 Gtk.Notebook 顶部标签。设计契约见 docs/design-specs/2026-06-23-widget-manager-ui.md §1/§4。
外壳只协调展示;数据/生命周期仍由 supervisor 经 app 回调驱动。
"""
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from manager.widgets.draw import PulseDot

# 页 key → (标题, 副标题)。来源:原型 JS titles。
_TITLES = {
    "overview": ("概览", "查看数据底座运行状态并控制其生命周期"),
    "sources": ("数据源", "管理 provider、查看实时数据、调整刷新间隔"),
    "widgets": ("小组件", "桌面 Web 小组件 — 即将推出"),
}
# 连接态 → (chip 文案, chip 样式类, 圆点 token, 脉冲?, 侧栏文案, 侧栏点 token)
_CONN = {
    "connected":    ("已连接", "is-connected", "success_primary", False, "底座运行中", "success_primary"),
    "reconnecting": ("重连中…", "is-reconnecting", "warning_primary", True, "正在连接…", "warning_primary"),
    "disconnected": ("未连接", "is-disconnected", "neutral_400", False, "底座未运行", "neutral_400"),
    "error":        ("鉴权失败", "is-disconnected", "danger_primary", False, "鉴权失败", "danger_primary"),
    "start_failed": ("启动失败", "is-disconnected", "danger_primary", False, "底座启动失败", "danger_primary"),
}


class _NavButton(Gtk.Button):
    def __init__(self, key, label, on_click, icon_name=None, trailing=None):
        super().__init__()
        self.key = key
        self.get_style_context().add_class("mw-nav-btn")
        self.set_relief(Gtk.ReliefStyle.NONE)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=11)
        if icon_name:
            row.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU), False, False, 0)
        row.pack_start(Gtk.Label(label=label, xalign=0), False, False, 0)
        if trailing is not None:
            row.pack_end(trailing, False, False, 0)
        self.add(row)
        self.connect("clicked", lambda *_: on_click(key))


class Sidebar(Gtk.Box):
    def __init__(self, on_nav):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class("mw-sidebar")
        self.set_size_request(220, -1)

        # 品牌行
        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        brand.set_margin_top(18); brand.set_margin_bottom(8)
        brand.set_margin_start(18); brand.set_margin_end(18)
        logo = Gtk.Label(label="W")
        logo.get_style_context().add_class("mw-brand-logo")
        logo.set_size_request(30, 30)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        n1 = Gtk.Label(label="WidgetHub", xalign=0); n1.get_style_context().add_class("mw-brand-name")
        n2 = Gtk.Label(label="小组件管理器", xalign=0); n2.get_style_context().add_class("mw-brand-sub")
        names.pack_start(n1, False, False, 0); names.pack_start(n2, False, False, 0)
        brand.pack_start(logo, False, False, 0); brand.pack_start(names, False, False, 0)
        self.pack_start(brand, False, False, 0)

        # 导航
        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        nav.set_margin_start(12); nav.set_margin_end(12); nav.set_margin_top(6); nav.set_margin_bottom(6)
        self._count = Gtk.Label(label="0")
        self._count.get_style_context().add_class("mw-nav-count")
        soon = Gtk.Label(label="即将"); soon.get_style_context().add_class("mw-nav-soon")
        self._btns = {
            "overview": _NavButton("overview", "概览", on_nav, "view-grid-symbolic"),
            "sources": _NavButton("sources", "数据源", on_nav, "network-server-symbolic", self._count),
            "widgets": _NavButton("widgets", "小组件", on_nav, "view-app-grid-symbolic", soon),
        }
        for b in self._btns.values():
            nav.pack_start(b, False, False, 0)
        self.pack_start(nav, False, False, 0)

        # 底部状态
        foot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        foot.get_style_context().add_class("mw-sidebar-foot")
        foot.set_halign(Gtk.Align.FILL)
        foot.set_size_request(-1, 52)
        self._foot = foot
        foot_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        foot_row.set_margin_start(18); foot_row.set_margin_end(18)
        foot_row.set_valign(Gtk.Align.CENTER)
        self._foot_row = foot_row
        self._dot = PulseDot("neutral_400", 4)
        self._status = Gtk.Label(label="底座未运行", xalign=0)
        self._status.get_style_context().add_class("mw-sidebar-status")
        foot_row.pack_start(self._dot, False, False, 0)
        foot_row.pack_start(self._status, False, False, 0)
        foot.pack_start(foot_row, True, True, 0)
        spacer = Gtk.Box(); self.pack_start(spacer, True, True, 0)
        self.pack_start(foot, False, True, 0)

    def set_selected(self, key):
        for k, b in self._btns.items():
            ctx = b.get_style_context()
            (ctx.add_class if k == key else ctx.remove_class)("selected")

    def set_count(self, n):
        self._count.set_text(str(n))

    def set_status(self, text, dot_token, pulsing=False):
        self._status.set_text(text)
        self._dot.configure(dot_token, pulsing)


class TopBar(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.get_style_context().add_class("mw-topbar")
        self.set_size_request(-1, 64)
        self.set_margin_start(24); self.set_margin_end(24)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        titles.set_valign(Gtk.Align.CENTER)
        self._title = Gtk.Label(label="", xalign=0); self._title.get_style_context().add_class("mw-page-title")
        self._sub = Gtk.Label(label="", xalign=0); self._sub.get_style_context().add_class("mw-page-sub")
        titles.pack_start(self._title, False, False, 0)
        titles.pack_start(self._sub, False, False, 0)
        self.pack_start(titles, True, True, 0)

        chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chip.get_style_context().add_class("mw-conn-chip")
        chip.set_valign(Gtk.Align.CENTER)
        self._chip = chip
        self._chip_dot = PulseDot("neutral_400", 4)
        self._chip_label = Gtk.Label(label="未连接")
        chip.pack_start(self._chip_dot, False, False, 0)
        chip.pack_start(self._chip_label, False, False, 0)
        self.pack_end(chip, False, False, 0)

    def set_page(self, title, subtitle):
        self._title.set_text(title)
        self._sub.set_text(subtitle)

    def set_connection(self, label, style_class, dot_token, pulsing):
        for c in ("is-connected", "is-reconnecting", "is-disconnected"):
            self._chip.get_style_context().remove_class(c)
        self._chip.get_style_context().add_class(style_class)
        self._chip_label.set_text(label)
        self._chip_dot.configure(dot_token, pulsing)


class MainShell(Gtk.Box):
    """组合外壳。app 经 pages 字典注入三页;对外暴露 set_connection / update_status / apply_data。"""

    def __init__(self, pages):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.get_style_context().add_class("mw-root")
        self._pages = pages
        self._sidebar = Sidebar(self._go)
        self.pack_start(self._sidebar, False, False, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._topbar = TopBar()
        main.pack_start(self._topbar, False, False, 0)
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        for key, w in pages.items():
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroller.get_style_context().add_class("mw-content")
            scroller.add(w)
            self._stack.add_named(scroller, key)
        main.pack_start(self._stack, True, True, 0)
        self.pack_start(main, True, True, 0)
        self._go("overview")

    def _go(self, key):
        self._stack.set_visible_child_name(key)
        self._sidebar.set_selected(key)
        title, sub = _TITLES[key]
        self._topbar.set_page(title, sub)

    # ---- 对外协调 ----
    def set_connection(self, state):
        label, cls, dot, pulse, side_text, side_dot = _CONN.get(state, _CONN["disconnected"])
        self._topbar.set_connection(label, cls, dot, pulse)
        self._sidebar.set_status(side_text, side_dot, pulse)
        for key in ("overview", "sources"):
            page = self._pages.get(key)
            if hasattr(page, "set_connection"):
                page.set_connection(state)

    def update_status(self, status):
        providers = status.get("providers", [])
        self._sidebar.set_count(sum(1 for p in providers if p.get("enabled")))
        if hasattr(self._pages["overview"], "update"):
            self._pages["overview"].update(status)
        if hasattr(self._pages["sources"], "update"):
            self._pages["sources"].update(status)

    def apply_data(self, topic, value):
        return self._pages["sources"].apply_data(topic, value)
