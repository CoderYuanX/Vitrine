"""小组件页:空状态 + 未来组件库预览(原型 WIDGETS 视图,设计规格 §4)。

纯展示,无数据依赖。预览卡为静态占位,标注「即将支持」。
"""
import math
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from manager.theme import rgba
from manager.widgets.draw import MeterBar


class _Gauge(Gtk.DrawingArea):
    """CPU 仪表预览:半环 + 指针感的弧。"""

    def __init__(self, percent=37):
        super().__init__()
        self._p = percent
        self.set_size_request(72, 46)
        self.connect("draw", self._on_draw)

    def _on_draw(self, _w, cr):
        a = self.get_allocation()
        cx, cy, r = a.width / 2, a.height - 6, min(a.width / 2 - 4, a.height - 10)
        cr.set_line_width(6)
        cr.set_line_cap(1)  # ROUND
        cr.set_source_rgba(*rgba("neutral_200"))
        cr.arc(cx, cy, r, math.pi, 2 * math.pi)
        cr.stroke()
        cr.set_source_rgba(*rgba("brand_primary"))
        cr.arc(cx, cy, r, math.pi, math.pi + math.pi * self._p / 100.0)
        cr.stroke()
        return False


class WidgetsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.set_margin_top(24); self.set_margin_bottom(24)
        self.set_margin_start(24); self.set_margin_end(24)

        # ---- 空状态(居中) ----
        self._empty_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._empty_card.get_style_context().add_class("mw-card")
        self._empty_card.get_style_context().add_class("mw-empty-card")
        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        empty.set_halign(Gtk.Align.CENTER)
        tile = Gtk.Box(); tile.set_size_request(54, 54)
        tile.get_style_context().add_class("mw-icon-tile")
        tile.get_style_context().add_class("is-brand")
        self._empty_tile = tile
        tile.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.DND)
        tile.pack_start(icon, True, True, 0)
        empty.pack_start(tile, False, False, 0)
        title = Gtk.Label(label="小组件渲染功能开发中")
        title.get_style_context().add_class("mw-h-15-700")
        title.set_markup('<span size="x-large" weight="bold">小组件渲染功能开发中</span>')
        empty.pack_start(title, False, False, 4)
        desc = Gtk.Label(label="后续版本将支持把小组件贴到桌面、使用 HTML / CSS / JS 编写 Web 小组件，并直接订阅数据底座的实时数据。")
        desc.get_style_context().add_class("mw-sub-13")
        desc.set_line_wrap(True); desc.set_justify(Gtk.Justification.CENTER)
        desc.set_max_width_chars(46)
        empty.pack_start(desc, False, False, 0)
        chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        chips.set_halign(Gtk.Align.CENTER); chips.set_margin_top(12)
        for t in ("贴到桌面", "Web 小组件", "订阅底座数据"):
            c = Gtk.Label(label=t); c.get_style_context().add_class("mw-chip")
            chips.pack_start(c, False, False, 0)
        empty.pack_start(chips, False, False, 0)
        self._empty_card.pack_start(empty, False, False, 0)
        self.pack_start(self._empty_card, False, False, 8)

        # ---- 未来组件库预览 ----
        lib = Gtk.Label(label="未来组件库预览", xalign=0)
        lib.get_style_context().add_class("mw-h-13-600")
        self.pack_start(lib, False, False, 0)

        grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        grid.set_homogeneous(True)
        grid.pack_start(self._preview_card(self._gauge_body, "CPU 仪表"), True, True, 0)
        grid.pack_start(self._preview_card(self._membar_body, "内存条"), True, True, 0)
        grid.pack_start(self._preview_card(self._clock_body, "时钟"), True, True, 0)
        self.pack_start(grid, False, False, 0)

    def _preview_card(self, body_fn, caption):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.get_style_context().add_class("mw-preview-card")
        card.set_size_request(-1, 148)
        overlay = Gtk.Overlay()
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.set_valign(Gtk.Align.CENTER); inner.set_halign(Gtk.Align.CENTER)
        body_fn(inner)
        cap = Gtk.Label(label=caption); cap.get_style_context().add_class("mw-metric-foot")
        inner.pack_start(cap, False, False, 0)
        overlay.add(inner)
        corner = Gtk.Label(label="即将支持")
        corner.get_style_context().add_class("mw-soon-corner")
        corner.set_halign(Gtk.Align.END); corner.set_valign(Gtk.Align.START)
        corner.set_margin_top(12); corner.set_margin_end(12)
        overlay.add_overlay(corner)
        card.pack_start(overlay, True, True, 0)
        return card

    def _gauge_body(self, box):
        box.pack_start(_Gauge(37), False, False, 0)
        v = Gtk.Label(label="37%"); v.get_style_context().add_class("mw-val-mono")
        box.pack_start(v, False, False, 0)

    def _membar_body(self, box):
        bars = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        bars.set_size_request(120, -1)
        for pct in (58, 42, 71):
            mb = MeterBar(pct, "purple"); mb.set_size_request(120, 9)
            bars.pack_start(mb, False, False, 0)
        box.pack_start(bars, False, False, 0)

    def _clock_body(self, box):
        t = datetime.now().strftime("%H:%M")
        v = Gtk.Label()
        v.set_markup(f'<span font_family="JetBrains Mono" size="xx-large" weight="bold">{t}</span>')
        box.pack_start(v, False, False, 0)
