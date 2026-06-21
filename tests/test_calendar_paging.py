"""日历月份翻页:prevMonth/nextMonth 跨年回绕,goToday 复位到当前月。"""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]

from PySide6.QtCore import QMetaObject, QObject, QUrl, Slot  # noqa: E402
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
    return QGuiApplication.instance() or QGuiApplication(sys.argv[:1])


@pytest.fixture
def root(app):
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("layout", _MockLayout())
    engine.load(QUrl.fromLocalFile(str(ROOT / "widgets" / "Calendar" / "Calendar.qml")))
    roots = engine.rootObjects()
    assert roots, "Calendar.qml 加载失败"
    r = roots[0]
    yield r
    r.setProperty("visible", False)


def test_prev_month_wraps_year(root):
    root.setProperty("viewYear", 2026)
    root.setProperty("viewMonth", 0)  # January
    QMetaObject.invokeMethod(root, "prevMonth")
    assert root.property("viewMonth") == 11
    assert root.property("viewYear") == 2025


def test_next_month_wraps_year(root):
    root.setProperty("viewYear", 2026)
    root.setProperty("viewMonth", 11)  # December
    QMetaObject.invokeMethod(root, "nextMonth")
    assert root.property("viewMonth") == 0
    assert root.property("viewYear") == 2027


def test_go_today_resets_view_to_current_month(root):
    root.setProperty("viewYear", 2000)
    root.setProperty("viewMonth", 3)
    QMetaObject.invokeMethod(root, "goToday")
    assert root.property("viewYear") == root.property("curYear")
    assert root.property("viewMonth") == root.property("curMonth")
    assert root.property("selectedDay") == root.property("curToday")
