"""数据源页:provider section 卡 + topic 行(值/进度条/折线/徽章/开关/档位步进/最近更新)。

原型 DATA SOURCES 视图,设计规格 §4/§5。保留对外 API 与防回环:
  DataSourcesPage(on_set_provider, on_set_interval) / update / apply_data / has_topic_row
  + 新增 set_connection(state)(断连置灰,由 shell 转发)。
间隔控件从连续 SpinButton 改为原型档位步进器 IntervalStepper(规格 §4)。
"""
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from manager.theme import metric_color
from manager.widgets.draw import IntervalStepper, MeterBar, PillSwitch, Sparkline

# provider 展示元信息;未知 provider 回退用 id。
_PROVIDER_META = {
    "system": ("System", "computer-symbolic", "provider · system"),
    "time": ("Time", "alarm-symbolic", "provider · time"),
}
# topic → (中文名, 渲染类型)。kind: cpu/mem=百分比+进度条+折线;time=时钟;raw=原值。
_TOPIC_META = {
    "system.cpu": ("CPU 占用", "cpu"),
    "system.mem": ("内存使用", "mem"),
    "time.now": ("当前时间", "time"),
}


class DataSourcesPage(Gtk.Box):
    def __init__(self, on_set_provider, on_set_interval):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_margin_top(24); self.set_margin_bottom(24)
        self.set_margin_start(24); self.set_margin_end(24)
        self._on_set_provider = on_set_provider
        self._on_set_interval = on_set_interval
        self._connected = False
        self._enabled = {}                                # pid -> bool
        self._rows = {}                                   # topic -> {...}
        self._groups = {}                                 # pid -> section 卡 Box
        self._sections = {}                               # pid -> {"box","badge","badge_lbl","switch","handler","pid"}
        self._switches = {}                               # pid -> {"switch","handler"}(兼容旧测试键)

        self._build_disconnected_banner()
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.pack_start(self._container, False, False, 0)
        note = Gtk.Label(label="刷新间隔范围 0.5s – 3600s，修改后立即生效。", xalign=0)
        note.get_style_context().add_class("mw-sub-12")
        note.set_margin_top(4)
        self.pack_start(note, False, False, 0)

    # ---- 断连横幅 ----
    def _build_disconnected_banner(self):
        b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        b.get_style_context().add_class("mw-banner")
        b.get_style_context().add_class("is-danger")
        for m in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
            getattr(b, m)(16)
        b.set_margin_bottom(16)
        ico = Gtk.Image.new_from_icon_name("network-offline-symbolic", Gtk.IconSize.BUTTON)
        ico.set_valign(Gtk.Align.CENTER)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        t = Gtk.Label(label="未连接到数据底座", xalign=0); t.get_style_context().add_class("mw-alert-title")
        d = Gtk.Label(label="控件已禁用。启动底座后将自动恢复数据刷新。", xalign=0)
        d.get_style_context().add_class("mw-sub-12")
        txt.pack_start(t, False, False, 0); txt.pack_start(d, False, False, 0)
        b.pack_start(ico, False, False, 0)
        b.pack_start(txt, True, True, 0)
        self._disc_banner = b
        self.pack_start(b, False, False, 0)
        b.show_all(); b.set_no_show_all(True); b.hide()

    # ---- 动态构建 ----
    def has_topic_row(self, topic):
        return topic in self._rows

    def _ensure_group(self, pid, enabled):
        if pid in self._groups:
            return self._groups[pid]
        title, icon, sub = _PROVIDER_META.get(pid, (pid.capitalize(), "drive-harddisk-symbolic", f"provider · {pid}"))
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        section.get_style_context().add_class("mw-section")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        for m in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
            getattr(header, m)(14)
        tile = Gtk.Box(); tile.set_size_request(34, 34)
        tile.get_style_context().add_class("mw-icon-tile")
        tile.get_style_context().add_class("is-brand")
        tile.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON), True, True, 0)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        n = Gtk.Label(label=title, xalign=0); n.get_style_context().add_class("mw-h-15-700")
        s = Gtk.Label(label=sub, xalign=0); s.get_style_context().add_class("mw-key-mono")
        names.pack_start(n, False, False, 0); names.pack_start(s, False, False, 0)
        badge = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        badge.get_style_context().add_class("mw-badge")
        badge.set_valign(Gtk.Align.CENTER)
        badge_lbl = Gtk.Label(label="运行中")
        badge.pack_start(badge_lbl, False, False, 0)
        sw = PillSwitch(active=enabled)
        sw.set_valign(Gtk.Align.CENTER)
        handler = sw.connect("toggled", lambda _s, v, p=pid: self._on_set_provider(p, v))
        header.pack_start(tile, False, False, 0)
        header.pack_start(names, True, True, 0)
        header.pack_start(badge, False, False, 0)
        header.pack_start(sw, False, False, 0)
        section.pack_start(header, False, False, 0)

        self._container.pack_start(section, False, False, 0)
        section.show_all()
        self._groups[pid] = section
        self._sections[pid] = {"box": section, "badge": badge, "badge_lbl": badge_lbl,
                               "switch": sw, "handler": handler, "tile": tile}
        self._switches[pid] = {"switch": sw, "handler": handler}
        return section

    def _ensure_row(self, pid, topic, interval):
        if topic in self._rows:
            return
        section = self._groups[pid]
        name_cn, kind = _TOPIC_META.get(topic, (topic, "raw"))
        # 行上分隔线(非首行)
        if any(r["pid"] == pid for r in self._rows.values()):
            sep = Gtk.Box(); sep.get_style_context().add_class("mw-row-divider"); sep.set_size_request(-1, 1)
            section.pack_start(sep, False, False, 0)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        for m in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
            getattr(row, m)(16)

        # 左:名称 + key
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1); left.set_size_request(150, -1)
        nm = Gtk.Label(label=name_cn, xalign=0); nm.get_style_context().add_class("mw-h-13-600")
        key = Gtk.Label(label=topic, xalign=0); key.get_style_context().add_class("mw-key-mono")
        left.pack_start(nm, False, False, 0); left.pack_start(key, False, False, 0)
        row.pack_start(left, False, False, 0)

        value = Gtk.Label(label="—", xalign=0); value.get_style_context().add_class("mw-val-mono")
        meter = spark = None
        if kind in ("cpu", "mem"):
            mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); mid.set_size_request(150, -1)
            mid.set_valign(Gtk.Align.CENTER)
            meter = MeterBar(0, "brand_primary")
            mid.pack_start(value, False, False, 0)
            mid.pack_start(meter, False, False, 0)
            row.pack_start(mid, False, False, 0)
            spark = Sparkline("brand_primary"); spark.set_size_request(120, 30)
            spark.set_valign(Gtk.Align.CENTER)
            row.pack_start(spark, False, False, 0)
        else:
            value.set_valign(Gtk.Align.CENTER)
            row.pack_start(value, True, True, 0)

        # 右:刷新间隔步进 + 最近更新
        right = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        right.set_halign(Gtk.Align.END); right.set_valign(Gtk.Align.CENTER)
        iv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        iv_cap = Gtk.Label(label="刷新间隔", xalign=1); iv_cap.get_style_context().add_class("mw-cap-11")
        stepper = IntervalStepper(interval)
        stepper.connect("changed", lambda _s, v, t=topic: self._on_set_interval(t, v))
        iv_box.pack_start(iv_cap, False, False, 0); iv_box.pack_start(stepper, False, False, 0)
        upd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); upd_box.set_size_request(74, -1)
        upd_cap = Gtk.Label(label="最近更新", xalign=1); upd_cap.get_style_context().add_class("mw-cap-11")
        updated = Gtk.Label(label="—", xalign=1); updated.get_style_context().add_class("mw-sub-13")
        upd_box.pack_start(upd_cap, False, False, 0); upd_box.pack_start(updated, False, False, 0)
        right.pack_start(iv_box, False, False, 0); right.pack_start(upd_box, False, False, 0)
        if kind in ("cpu", "mem"):
            row.pack_end(right, False, False, 0)
        else:
            row.pack_start(right, False, False, 0)

        section.pack_start(row, False, False, 0)
        section.show_all()
        self._rows[topic] = {"pid": pid, "kind": kind, "value": value, "meter": meter,
                             "spark": spark, "stepper": stepper, "updated": updated,
                             "hist": [], "last_text": None}

    # ---- 同步(防回环) ----
    def _sync_switch(self, pid, enabled):
        entry = self._switches.get(pid)
        if entry is None or entry["switch"].get_active() == enabled:
            return
        sw, handler = entry["switch"], entry["handler"]
        sw.handler_block(handler)
        sw.set_active(enabled)
        sw.handler_unblock(handler)

    def _sync_interval(self, topic, interval):
        r = self._rows.get(topic)
        if r is None or r["stepper"].get_value() == interval:
            return
        r["stepper"].set_value(interval)                  # set_value 不发 "changed",天然不回环

    # ---- 数据流 ----
    def update(self, status):
        for prov in status.get("providers", []):
            pid = prov["id"]
            self._enabled[pid] = prov["enabled"]
            self._ensure_group(pid, prov["enabled"])
            self._sync_switch(pid, prov["enabled"])
            for t in prov["topics"]:
                self._ensure_row(pid, t["topic"], t["interval"])
                self._sync_interval(t["topic"], t["interval"])
                if t["last_value"] is not None:
                    self.apply_data(t["topic"], t["last_value"])
        # 连接态由 set_connection 单一来源决定(状态事件总在 on_state(connected) 之后到达),
        # 这里不臆断,避免覆盖显式断连置灰。
        self._refresh_all_active()

    def apply_data(self, topic, value):
        r = self._rows.get(topic)
        if r is None:
            return False
        text, percent = self._render(r["kind"], value)
        if r["last_text"] == text:
            return False
        r["last_text"] = text
        r["value"].set_text(text)
        if r["meter"] is not None and percent is not None:
            color = metric_color(percent, r["kind"])
            r["meter"].set_value(percent, color)
            r["hist"] = (r["hist"] + [percent])[-24:]
            if r["spark"] is not None:
                r["spark"].set_history(r["hist"], color)
        if self._provider_active(r["pid"]):
            r["updated"].set_text("刚刚")
        return True

    @staticmethod
    def _render(kind, value):
        """→ (显示文本, 百分比 or None)。"""
        if kind in ("cpu", "mem"):
            pct = value.get("percent") if isinstance(value, dict) else float(value)
            return f"{pct:.1f}%", float(pct)
        if kind == "time":
            iso = value.get("iso") if isinstance(value, dict) else str(value)
            try:
                return datetime.fromisoformat(iso).strftime("%H:%M:%S"), None
            except (ValueError, TypeError):
                return str(iso), None
        return str(value), None

    # ---- 连接态 / 置灰 ----
    def set_connection(self, state):
        self._connected = (state == "connected")
        if self._connected:
            self._disc_banner.hide()
        else:
            self._disc_banner.show()
        self._refresh_all_active()

    def _provider_active(self, pid):
        return self._connected and self._enabled.get(pid, False)

    def _refresh_all_active(self):
        for pid in self._groups:
            self._refresh_section(pid)

    def _refresh_section(self, pid):
        active = self._provider_active(pid)
        sec = self._sections[pid]
        ctx = sec["box"].get_style_context()
        (ctx.remove_class if active else ctx.add_class)("is-dim")
        # 徽章:运行中 / 已停用(provider 关) ;断连整体也视为停用态
        enabled = self._enabled.get(pid, False)
        bctx = sec["badge"].get_style_context()
        for c in ("is-running", "is-disabled", "is-error"):
            bctx.remove_class(c)
        if enabled and self._connected:
            bctx.add_class("is-running"); sec["badge_lbl"].set_text("运行中")
        else:
            bctx.add_class("is-disabled"); sec["badge_lbl"].set_text("已停用")
        sec["switch"].set_switch_sensitive(self._connected)
        for topic, r in self._rows.items():
            if r["pid"] != pid:
                continue
            r["stepper"].set_stepper_sensitive(self._connected)
            if active:
                r["updated"].set_text("刚刚" if r["last_text"] not in (None, "—") else "—")
            else:
                r["value"].set_text("—"); r["last_text"] = "—"
                r["updated"].set_text("已暂停")
                if r["meter"] is not None:
                    r["meter"].set_value(0)
