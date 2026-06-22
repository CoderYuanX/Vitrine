"""日历展开/折叠:瞬时切换(无逐帧动画 → KWin/X11 下不闪),但保留三处真修复:

1. 居中正确:用 expandedW/expandedH 直接算,绕开滞后的 baseW/baseH 绑定(否则展开右下偏);
2. 无"先居中再展开"跳变:单次定位,无 Qt.callLater 二次居中;
3. 无空白填充:Dashboard 的 Loader 常驻预热(active: true),不每次展开重建。

并确认:无窗口几何动画(Behavior)——逐帧 resize 透明顶层窗口在 KWin 下会闪。
"""
import os
import re
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
CAL_QML = ROOT / "widgets" / "Calendar" / "Calendar.qml"

from PySide6.QtCore import QObject, QUrl, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402


class _MockLayout(QObject):
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
    engine.load(QUrl.fromLocalFile(str(CAL_QML)))
    roots = engine.rootObjects()
    assert roots, "Calendar.qml 加载失败"
    root = roots[0]
    yield root
    root.setProperty("visible", False)


def _src():
    return CAL_QML.read_text(encoding="utf-8")


def test_expand_collapse_toggle_immediately(calendar_root):
    # 瞬时切换:无动画,expand()/collapse() 同步翻转 expanded。
    calendar_root.setProperty("expanded", False)
    calendar_root.metaObject().invokeMethod(calendar_root, "expand")
    assert calendar_root.property("expanded") is True
    calendar_root.metaObject().invokeMethod(calendar_root, "collapse")
    assert calendar_root.property("expanded") is False


def test_no_second_centering_jump():
    # "先居中再展开"跳变之源:onExpandedChanged 内 Qt.callLater 二次居中。必须没有。
    src = _src()
    assert "Qt.callLater(applyPosition)" not in src
    assert "Qt.callLater(applyGeom)" not in src


def test_expanded_centering_uses_nonlagging_dimensions():
    # 居中必须用 expandedW/expandedH 直接推,不能用滞后一帧的 baseW/baseH 绑定(否则展开右下偏)。
    src = _src()
    m = re.search(r"function applyGeom\(\)\s*\{.*?\n    \}", src, re.S)
    assert m, "未找到 applyGeom"
    body = m.group(0)
    assert "expandedW * zoom" in body and "expandedH * zoom" in body, "居中应使用 expandedW/expandedH"
    assert "baseW * zoom" not in body and "baseH * zoom" not in body, "居中不得依赖滞后的 baseW/baseH 绑定"


def test_no_window_geometry_animation_to_avoid_kwin_flicker():
    # 逐帧 resize 透明顶层窗口在 KWin 下会闪;窗口几何必须瞬时,不得加 Behavior 动画。
    src = _src()
    for prop in ("Behavior on x", "Behavior on y", "Behavior on width", "Behavior on height"):
        assert prop not in src, f"窗口几何不应有动画:{prop}"
    # 也不应残留 morph/飞入动画状态机
    assert "_morphing" not in src
    assert 'property: "_morph"' not in src


def test_dashboard_loader_stays_warm_to_avoid_blank_fill():
    # Dashboard Loader 常驻(active: true),避免每次展开重建 → Rising 错峰淡入重放造成"空白后逐张填充"。
    src = _src()
    assert "active: true" in src
    assert "active: root.expanded" not in src
