import sys
import signal
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtQml import QQmlApplicationEngine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ON = {"clock"}   # 首次运行默认启用的组件


class WidgetHost:
    def __init__(self):
        fmt = QSurfaceFormat.defaultFormat()
        fmt.setAlphaBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
        self.app = QApplication(sys.argv)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.app.setApplicationName("deepin-widgets")
        self.app.setQuitOnLastWindowClosed(False)   # 关组件不退程序,托盘常驻

        from .registry import WidgetRegistry
        from .config_store import ConfigStore
        from .layout_bridge import LayoutBridge
        self.registry = WidgetRegistry(PROJECT_ROOT / "widgets")
        self.config = ConfigStore()
        self.bridge = LayoutBridge(self.config)
        self.widgets = self.registry.discover()
        self.engines = {}

    def run(self):
        self._bootstrap()
        return self.app.exec()

    def _bootstrap(self):
        for w in self.widgets:
            if self.config.is_enabled(w["id"], default=(w["id"] in DEFAULT_ON)):
                self._show_widget(w["id"])
        from .tray import build_tray
        self.tray = build_tray(self)

    def _meta(self, wid):
        return next((w for w in self.widgets if w["id"] == wid), None)

    def is_shown(self, wid):
        return wid in self.engines

    def _show_widget(self, wid):
        if wid in self.engines:
            return
        meta = self._meta(wid)
        if not meta:
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

    def _hide_widget(self, wid):
        eng = self.engines.pop(wid, None)
        if eng:
            for obj in eng.rootObjects():
                obj.close()
            eng.deleteLater()

    def set_widget_enabled(self, wid, enabled):
        self.config.set_enabled(wid, enabled)
        if enabled:
            self._show_widget(wid)
        else:
            self._hide_widget(wid)
        act = getattr(self, "_toggle_actions", {}).get(wid)
        if act and act.isChecked() != enabled:
            act.setChecked(enabled)

    def _apply_desktop_states(self, window):
        def apply():
            try:
                from .x11 import set_desktop_widget_states
                set_desktop_widget_states(int(window.winId()))
            except Exception as exc:
                print(f"[x11] {exc}", file=sys.stderr)
        QTimer.singleShot(200, apply)
