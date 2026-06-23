"""Cairo 自绘的高保真组件:iOS 风开关、进度条、迷你折线、脉冲连接点。

均按原型 prototype/小组件管理器.html 的几何/配色还原(见设计规格 §4/§6)。
取色统一走 manager.theme.rgba(),与 style.css 同源。
"""
import math

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, GObject, Gtk

from manager.theme import rgba


def _rounded_rect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class PillSwitch(Gtk.DrawingArea):
    """iOS 风开关(原型 trackStyle/knobStyle):track 40×22 pill,knob 18×18 白,left 2↔20,.18s 缓动。

    API 对齐 Gtk.Switch:get_active/set_active + "toggled" 信号。
    set_active 也发 "toggled",调用方用 handler_block 包住程序化同步以防回环(沿用现有模式)。
    """
    __gsignals__ = {"toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool,))}

    def __init__(self, active=False):
        super().__init__()
        self._active = bool(active)
        self._sensitive = True
        self._pos = 1.0 if active else 0.0           # 0=关 1=开,动画插值
        self._anim_id = 0
        self.set_size_request(40, 22)
        self.add_events(0x100 | 0x200)               # BUTTON_PRESS | BUTTON_RELEASE 掩码(占位)
        from gi.repository import Gdk
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK)
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_click)

    # ---- 状态 ----
    def get_active(self):
        return self._active

    def set_active(self, value):
        value = bool(value)
        if value == self._active:
            return
        self._active = value
        self._animate_to(1.0 if value else 0.0)
        self.emit("toggled", value)

    def set_switch_sensitive(self, sensitive):
        self._sensitive = bool(sensitive)
        self.queue_draw()

    # ---- 交互 ----
    def _on_click(self, _w, _e):
        if not self._sensitive:
            return False
        self.set_active(not self._active)
        return True

    def _animate_to(self, target):
        if self._anim_id:
            GLib.source_remove(self._anim_id)
        start = self._pos
        steps = {"n": 0}
        total = 9                                    # ~.18s @ 20ms

        def tick():
            steps["n"] += 1
            t = steps["n"] / total
            e = 1 - (1 - t) * (1 - t)                # ease-out
            self._pos = start + (target - start) * e
            self.queue_draw()
            if steps["n"] >= total:
                self._pos = target
                self._anim_id = 0
                return False
            return True

        self._anim_id = GLib.timeout_add(20, tick)

    # ---- 绘制 ----
    def _on_draw(self, _w, cr):
        a = self.get_allocation()
        w, h = 40, 22
        ox, oy = (a.width - w) / 2, (a.height - h) / 2
        alpha = 1.0 if self._sensitive else 0.5
        # track
        on = self._pos
        tr = [(1 - on) * c1 + on * c2 for c1, c2 in zip(rgba("neutral_300"), rgba("brand_primary"))]
        cr.set_source_rgba(tr[0], tr[1], tr[2], alpha)
        _rounded_rect(cr, ox, oy, w, h, h / 2)
        cr.fill()
        # knob
        kx = ox + 2 + self._pos * 18
        ky = oy + 2
        cr.set_source_rgba(0, 0, 0, 0.22 * alpha)    # 阴影
        cr.arc(kx + 9, ky + 9 + 1, 9, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, alpha)
        cr.arc(kx + 9, ky + 9, 9, 0, 2 * math.pi)
        cr.fill()
        return False


class MeterBar(Gtk.DrawingArea):
    """细圆角进度条(原型 topic 行):高 5,radius 3,track neutral_200,fill 阈值色。"""

    def __init__(self, percent=0.0, color_token="brand_primary"):
        super().__init__()
        self._p = max(0.0, min(100.0, percent))
        self._color = color_token
        self.set_size_request(-1, 5)
        self.set_hexpand(True)
        self.connect("draw", self._on_draw)

    def set_value(self, percent, color_token=None):
        self._p = max(0.0, min(100.0, percent))
        if color_token:
            self._color = color_token
        self.queue_draw()

    def _on_draw(self, _w, cr):
        a = self.get_allocation()
        w, h = a.width, 5
        y = (a.height - h) / 2
        cr.set_source_rgba(*rgba("neutral_200"))
        _rounded_rect(cr, 0, y, w, h, h / 2)
        cr.fill()
        fw = w * self._p / 100.0
        if fw > 0:
            cr.set_source_rgba(*rgba(self._color))
            _rounded_rect(cr, 0, y, max(fw, h), h, h / 2)
            cr.fill()
        return False


class Sparkline(Gtk.DrawingArea):
    """迷你折线(原型 spark()):历史值序列 → 平滑折线 + 浅色填充。视口约 118×30。"""

    def __init__(self, color_token="brand_primary", vmin=0.0, vmax=100.0):
        super().__init__()
        self._hist = []
        self._color = color_token
        self._min, self._max = vmin, vmax
        self.set_size_request(120, 30)
        self.connect("draw", self._on_draw)

    def set_history(self, hist, color_token=None):
        self._hist = list(hist)
        if color_token:
            self._color = color_token
        self.queue_draw()

    def _on_draw(self, _w, cr):
        a = self.get_allocation()
        w, h = a.width, a.height
        n = len(self._hist)
        if n < 2:
            return False
        pad = 2
        span = (self._max - self._min) or 1

        def pt(i, v):
            x = pad + (i / (n - 1)) * (w - 2 * pad)
            y = (h - pad) - ((v - self._min) / span) * (h - 2 * pad)
            return x, max(pad, min(h - pad, y))

        pts = [pt(i, v) for i, v in enumerate(self._hist)]
        # 填充
        cr.move_to(pts[0][0], h)
        for x, y in pts:
            cr.line_to(x, y)
        cr.line_to(pts[-1][0], h)
        cr.close_path()
        cr.set_source_rgba(*rgba(self._color, 0.12))
        cr.fill()
        # 折线
        cr.set_line_width(1.6)
        cr.set_line_join(1)                          # ROUND
        cr.set_source_rgba(*rgba(self._color))
        cr.move_to(*pts[0])
        for x, y in pts[1:]:
            cr.line_to(x, y)
        cr.stroke()
        return False


class IntervalStepper(Gtk.Box):
    """刷新间隔档位步进器(原型 − 值 +)。档位见 bumpIv;set_value 程序化不发信号,− / + 用户操作发 "changed"。"""
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, (float,))}
    STEPS = [0.5, 1, 2, 3, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600]

    def __init__(self, seconds=1.0):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._value = float(seconds)
        self._sensitive = True
        self._down = self._mk_btn("−", -1)
        self._label = Gtk.Label(label=self._fmt(self._value))
        self._label.get_style_context().add_class("mw-iv-mono")
        self._up = self._mk_btn("+", +1)
        self.pack_start(self._down, False, False, 0)
        self.pack_start(self._label, False, False, 0)
        self.pack_start(self._up, False, False, 0)

    def _mk_btn(self, text, direction):
        b = Gtk.Button(label=text)
        b.get_style_context().add_class("mw-step-btn")
        b.set_relief(Gtk.ReliefStyle.NONE)
        b.connect("clicked", lambda *_: self._bump(direction))
        return b

    @staticmethod
    def _fmt(v):
        return (f"{v:.1f}" if v < 10 else f"{int(round(v))}") + "s"

    def _nearest_idx(self):
        try:
            return self.STEPS.index(self._value)
        except ValueError:
            return min(range(len(self.STEPS)), key=lambda i: abs(self.STEPS[i] - self._value))

    def _bump(self, direction):
        if not self._sensitive:
            return
        idx = max(0, min(len(self.STEPS) - 1, self._nearest_idx() + direction))
        new = self.STEPS[idx]
        if new != self._value:
            self._value = new
            self._label.set_text(self._fmt(new))
            self.emit("changed", new)

    # 对齐 SpinButton 的取/设值;set_value 不发 "changed"(防同步回环)
    def get_value(self):
        return self._value

    def set_value(self, seconds):
        seconds = float(seconds)
        if seconds != self._value:
            self._value = seconds
            self._label.set_text(self._fmt(seconds))

    def set_stepper_sensitive(self, sensitive):
        self._sensitive = bool(sensitive)
        self._down.set_sensitive(sensitive)
        self._up.set_sensitive(sensitive)


class PulseDot(Gtk.DrawingArea):
    """状态圆点;reconnecting 时画外扩脉冲环(原型 livePulse 1s)。"""

    def __init__(self, color_token="success_primary", radius=4, pulsing=False):
        super().__init__()
        self._color = color_token
        self._r = radius
        self._pulsing = pulsing
        self._phase = 0.0
        self._timer = 0
        self.set_size_request(radius * 2 + 8, radius * 2 + 8)
        self.connect("draw", self._on_draw)
        self.connect("unrealize", lambda *_: self._stop())
        if pulsing:
            self._start()

    def configure(self, color_token, pulsing=False):
        self._color = color_token
        if pulsing and not self._pulsing:
            self._pulsing = True
            self._start()
        elif not pulsing and self._pulsing:
            self._pulsing = False
            self._stop()
        self.queue_draw()

    def _start(self):
        if not self._timer:
            self._timer = GLib.timeout_add(40, self._tick)

    def _stop(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _tick(self):
        self._phase = (self._phase + 0.04) % 1.0
        self.queue_draw()
        return True

    def _on_draw(self, _w, cr):
        a = self.get_allocation()
        cx, cy = a.width / 2, a.height / 2
        if self._pulsing:
            ring = self._r + self._phase * (self._r + 4)
            cr.set_source_rgba(*rgba(self._color, max(0.0, 0.35 * (1 - self._phase))))
            cr.arc(cx, cy, ring, 0, 2 * math.pi)
            cr.fill()
        cr.set_source_rgba(*rgba(self._color))
        cr.arc(cx, cy, self._r, 0, 2 * math.pi)
        cr.fill()
        return False
