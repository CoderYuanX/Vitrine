"""日历组件:折叠态可滚轮缩放,展开态禁止缩放(展开=固定仪表盘)。

无显示环境下用 offscreen 平台离屏加载 Calendar.qml,直接读取
zoom WheelHandler 的 enabled 绑定,验证其随 expanded 切换。
"""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]

from PySide6.QtCore import QObject, QUrl, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402


class _MockLayout(QObject):
    """复刻 LayoutBridge 接口的最小桩:getState 返回 'x,y,zoom'。"""

    @Slot(str, result=str)
    def getState(self, wid):
        return "80,80,1.0"

    @Slot(str, int, int, float)
    def saveState(self, wid, x, y, zoom):
        pass


@pytest.fixture(scope="module")
def app():
    application = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    yield application


@pytest.fixture
def calendar_root(app):
    engine = QQmlApplicationEngine()
    layout = _MockLayout()
    engine.rootContext().setContextProperty("layout", layout)
    engine.load(QUrl.fromLocalFile(str(ROOT / "widgets" / "Calendar" / "Calendar.qml")))
    roots = engine.rootObjects()
    assert roots, "Calendar.qml 加载失败"
    root = roots[0]
    yield root
    # 防止 Window 在后续测试间残留
    root.setProperty("visible", False)


def _zoom_wheel(root):
    wh = root.findChild(QObject, "zoomWheel")
    assert wh is not None, "未找到 zoom WheelHandler(objectName=zoomWheel)"
    return wh


def test_zoom_enabled_when_collapsed(calendar_root):
    calendar_root.setProperty("expanded", False)
    assert _zoom_wheel(calendar_root).property("enabled") is True


def test_zoom_disabled_when_expanded(calendar_root):
    calendar_root.setProperty("expanded", True)
    assert _zoom_wheel(calendar_root).property("enabled") is False
