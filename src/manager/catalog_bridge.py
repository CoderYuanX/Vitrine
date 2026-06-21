from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, Property

_CATEGORIES = [
    {"key": "all", "label": "全部"},
    {"key": "clock", "label": "时钟"},
    {"key": "weather", "label": "天气"},
    {"key": "calendar", "label": "日历"},
    {"key": "system", "label": "系统"},
    {"key": "note", "label": "便签"},
]


class CatalogBridge(QObject):
    changed = Signal()

    def __init__(self, runtime, widgets, quit_fn=None):
        super().__init__()
        self._runtime = runtime
        self._widgets = widgets
        self._quit_fn = quit_fn
        self._active = "all"

    def _preview_qml(self, w):
        if not w.get("implemented", True):
            return ""
        p = Path(w["dir"]) / "Preview.qml"
        return str(p) if p.is_file() else ""

    def _visible(self):
        out = []
        for w in self._widgets:
            if self._active == "all" or w["category"] == self._active:
                out.append({
                    "id": w["id"], "name": w["name"], "category": w["category"],
                    "enabled": self._runtime.is_shown(w["id"]),
                    "implemented": w.get("implemented", True),
                    "previewQml": self._preview_qml(w),
                })
        return out

    @Slot(str)
    def setCategory(self, key):
        if key != self._active:
            self._active = key
            self.changed.emit()

    @Slot(str, bool)
    def toggle(self, wid, on):
        self._runtime.set_enabled(wid, on)
        self.changed.emit()

    @Slot()
    def showAll(self):
        for w in self._widgets:
            if w.get("implemented", True):
                self._runtime.set_enabled(w["id"], True)
        self.changed.emit()

    @Slot()
    def hideAll(self):
        for w in self._widgets:
            if self._runtime.is_shown(w["id"]):
                self._runtime.set_enabled(w["id"], False)
        self.changed.emit()

    @Slot()
    def quitApp(self):
        if self._quit_fn:
            self._quit_fn()

    @Slot(bool)
    def setAutostart(self, on):
        from . import autostart
        import sys
        from pathlib import Path
        main = Path(__file__).resolve().parents[2] / "main.py"
        autostart.set_enabled(on, f"{sys.executable} {main}")
        self.changed.emit()

    def _get_autostart(self):
        from . import autostart
        return autostart.is_enabled()

    def _get_active(self):
        return self._active

    activeCategory = Property(str, _get_active, notify=changed)
    autostartEnabled = Property(bool, _get_autostart, notify=changed)
    categories = Property("QVariantList", lambda self: _CATEGORIES, constant=True)
    visibleWidgets = Property("QVariantList", lambda self: self._visible(), notify=changed)
