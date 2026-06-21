import sys
import signal
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ON = {"clock"}


class ManagerApp:
    def __init__(self):
        fmt = QSurfaceFormat.defaultFormat()
        fmt.setAlphaBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
        self.app = QApplication(sys.argv)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.app.setApplicationName("deepin-widgets")
        self.app.setQuitOnLastWindowClosed(False)

        from .registry import WidgetRegistry
        from .config_store import ConfigStore
        from .layout_bridge import LayoutBridge
        from .runtime import WidgetRuntime
        self.registry = WidgetRegistry(PROJECT_ROOT / "widgets")
        self.config = ConfigStore()
        self.layout_bridge = LayoutBridge(self.config)
        self.widgets = self.registry.discover()
        self.runtime = WidgetRuntime(self.app, self.widgets, self.config, self.layout_bridge)
        self.manager_engine = None   # Task 7 填充

    def run(self):
        self.runtime.bootstrap(DEFAULT_ON)
        from .tray import build_tray
        self.tray = build_tray(self)
        return self.app.exec()

    def open_manager(self):
        # Task 7 实现:创建/显示管理窗口
        pass
