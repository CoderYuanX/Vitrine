import os
import sys
import signal
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat, QFont

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ON = {"clock"}


def _strip_dxcb(value):
    """从 QT_QPA_PLATFORM 列表里去掉 dxcb。

    Deepin 注入 'dxcb;xcb',但 PySide6 不带 dxcb 插件,Qt 会先试 dxcb 打印
    告警再回退。去掉后保留其余回退;全空则用 xcb。非 dxcb 取值原样返回。
    """
    parts = [p for p in value.split(";") if p]
    if "dxcb" not in parts:
        return value
    kept = [p for p in parts if p != "dxcb"]
    return ";".join(kept) if kept else "xcb"
# 字体优先级回退:QML 的 font.families 在本机 PySide6 不可用,改在应用级用 QFont.setFamilies 设置,
# QML Text 继承此族(各自仍可覆盖 pixelSize/weight)。Deepin 上解析到 Noto Sans CJK SC。
UI_FONT_FAMILIES = ["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC"]


class ManagerApp:
    def __init__(self):
        # 必须在 QApplication 之前清洗:去掉 Deepin 的 dxcb,消除平台插件告警
        _plat = os.environ.get("QT_QPA_PLATFORM")
        if _plat:
            os.environ["QT_QPA_PLATFORM"] = _strip_dxcb(_plat)
        fmt = QSurfaceFormat.defaultFormat()
        fmt.setAlphaBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
        self.app = QApplication(sys.argv)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.app.setApplicationName("deepin-widgets")
        self.app.setQuitOnLastWindowClosed(False)
        _font = QFont()
        _font.setFamilies(UI_FONT_FAMILIES)
        self.app.setFont(_font)

        from .registry import WidgetRegistry
        from .config_store import ConfigStore
        from .layout_bridge import LayoutBridge
        from .event_bridge import EventBridge
        from .weather_bridge import WeatherBridge
        from .calendar_info import CalendarInfoBridge
        from .task_bridge import TaskBridge
        from .runtime import WidgetRuntime
        self.registry = WidgetRegistry(PROJECT_ROOT / "widgets")
        self.config = ConfigStore()
        self.layout_bridge = LayoutBridge(self.config)
        self.event_bridge = EventBridge()
        self.weather_bridge = WeatherBridge(config=self.config)
        self.weather_bridge.start()
        self.calendar_info_bridge = CalendarInfoBridge()
        self.task_bridge = TaskBridge()
        self.widgets = self.registry.discover()
        self.runtime = WidgetRuntime(self.app, self.widgets, self.config,
                                     self.layout_bridge, self.event_bridge,
                                     self.weather_bridge,
                                     self.calendar_info_bridge,
                                     task_bridge=self.task_bridge)
        self.manager_engine = None   # Task 7 填充

        from .catalog_bridge import CatalogBridge
        self.catalog = CatalogBridge(self.runtime, self.widgets, quit_fn=self.app.quit)

    def run(self):
        self.runtime.bootstrap(DEFAULT_ON)
        from .tray import build_tray
        self.tray = build_tray(self)
        return self.app.exec()

    def open_manager(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        if self.manager_engine is None:
            eng = QQmlApplicationEngine()
            eng.rootContext().setContextProperty("catalog", self.catalog)
            eng.rootContext().setContextProperty("weather", self.weather_bridge)
            eng.rootContext().setContextProperty("calendarInfo", self.calendar_info_bridge)
            eng.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "Manager.qml")))
            if not eng.rootObjects():
                return
            self.manager_engine = eng
        win = self.manager_engine.rootObjects()[0]
        win.show(); win.raise_(); win.requestActivate()
