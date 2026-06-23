import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class DataSourcesPage(Gtk.Box):
    def __init__(self, on_set_provider, on_set_interval):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_border_width(16)
        self._on_set_provider = on_set_provider
        self._on_set_interval = on_set_interval
        self._rows = {}                                   # topic -> {"value": Label, "spin": SpinButton, "spin_handler"}
        self._groups = {}                                 # provider -> Gtk.Box
        self._switches = {}                               # provider -> {"switch": Gtk.Switch, "handler": int}
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.pack_start(self._container, True, True, 0)

    def has_topic_row(self, topic):
        return topic in self._rows

    def _ensure_group(self, pid, enabled):
        if pid in self._groups:
            return self._groups[pid]
        frame = Gtk.Frame(label=pid)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(8)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sw = Gtk.Switch()
        sw.set_active(enabled)
        handler = sw.connect("notify::active", lambda s, _p: self._on_set_provider(pid, s.get_active()))
        header.pack_start(Gtk.Label(label="启用", xalign=0), False, False, 0)
        header.pack_start(sw, False, False, 0)
        box.pack_start(header, False, False, 0)
        frame.add(box)
        self._container.pack_start(frame, False, False, 0)
        self._groups[pid] = box
        self._switches[pid] = {"switch": sw, "handler": handler}
        return box

    def _sync_switch(self, pid, enabled):
        # 后续 status 同步开关状态(可能被别的客户端改过);阻塞 notify 信号,避免回写又触发 set_provider 形成回环
        entry = self._switches.get(pid)
        if entry is None or entry["switch"].get_active() == enabled:
            return
        sw, handler = entry["switch"], entry["handler"]
        sw.handler_block(handler)
        sw.set_active(enabled)
        sw.handler_unblock(handler)

    def _ensure_row(self, box, topic, interval):
        if topic in self._rows:
            return
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=topic, xalign=0)
        value = Gtk.Label(label="-", xalign=0)
        spin = Gtk.SpinButton.new_with_range(0.5, 3600, 0.5)
        spin.set_value(interval)
        spin_handler = spin.connect("value-changed", lambda s: self._on_set_interval(topic, s.get_value()))
        row.pack_start(name, True, True, 0)
        row.pack_start(value, False, False, 0)
        row.pack_start(spin, False, False, 0)
        box.pack_start(row, False, False, 0)
        self._rows[topic] = {"value": value, "spin": spin, "spin_handler": spin_handler}
        row.show_all()

    def _sync_interval(self, topic, interval):
        # 后续 status 同步间隔(可能被别的客户端改过);阻塞 value-changed,避免回写又触发 set_interval 形成回环
        r = self._rows.get(topic)
        if r is None or r["spin"].get_value() == interval:
            return
        r["spin"].handler_block(r["spin_handler"])
        r["spin"].set_value(interval)
        r["spin"].handler_unblock(r["spin_handler"])

    def update(self, status):
        for prov in status.get("providers", []):
            box = self._ensure_group(prov["id"], prov["enabled"])
            self._sync_switch(prov["id"], prov["enabled"])
            for t in prov["topics"]:
                self._ensure_row(box, t["topic"], t["interval"])
                self._sync_interval(t["topic"], t["interval"])
                if t["last_value"] is not None:
                    self.apply_data(t["topic"], t["last_value"])

    def apply_data(self, topic, value):
        if topic in self._rows:
            self._rows[topic]["value"].set_text(str(value))
