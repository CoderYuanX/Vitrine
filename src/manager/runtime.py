import sys
from pathlib import Path
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtQml import QQmlApplicationEngine


class WidgetRuntime:
    """管理桌面小组件卡片窗口:按 id 显示/隐藏,每卡片一个独立 QML engine。"""

    def __init__(self, app, widgets, config, layout_bridge):
        self.app = app
        self.widgets = widgets
        self.config = config
        self.bridge = layout_bridge
        self.engines = {}

    def bootstrap(self, default_on):
        for w in self.widgets:
            if not w.get("implemented", True):
                continue
            if self.config.is_enabled(w["id"], default=(w["id"] in default_on)):
                self.show_widget(w["id"])

    def _meta(self, wid):
        return next((w for w in self.widgets if w["id"] == wid), None)

    def is_shown(self, wid):
        return wid in self.engines

    def show_widget(self, wid):
        if wid in self.engines:
            return
        meta = self._meta(wid)
        if not meta or not meta.get("implemented", True):
            return
        eng = QQmlApplicationEngine()
        eng.rootContext().setContextProperty("layout", self.bridge)
        eng.load(QUrl.fromLocalFile(meta["qml"]))
        roots = eng.rootObjects()
        if not roots:
            return
        if self.app.platformName() == "xcb":
            self._apply_desktop_states(roots[0])
        self.engines[wid] = eng

    def hide_widget(self, wid):
        eng = self.engines.pop(wid, None)
        if eng:
            for obj in eng.rootObjects():
                obj.close()
            eng.deleteLater()

    def set_enabled(self, wid, enabled):
        self.config.set_enabled(wid, enabled)
        if enabled:
            self.show_widget(wid)
        else:
            self.hide_widget(wid)

    def _apply_desktop_states(self, window):
        def apply():
            try:
                from .x11 import set_desktop_widget_states
                set_desktop_widget_states(int(window.winId()))
            except Exception as exc:
                print(f"[x11] {exc}", file=sys.stderr)
        QTimer.singleShot(200, apply)
