"""冒烟:用真实 TaskBridge/EventBridge 注入,加载 Calendar 并展开,
确认 TasksCard/ProductivityCard 的绑定路径(tasks.today/week/doneThisWeek、events.dayEvents)
不抛 QML 错误(捕捉 slot 名拼错这类问题)。
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

from manager.event_bridge import EventBridge  # noqa: E402
from manager.event_store import EventStore  # noqa: E402
from manager.task_bridge import TaskBridge  # noqa: E402
from manager.task_store import TaskStore  # noqa: E402


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


def test_dashboard_loads_and_expands_with_real_bridges(app, tmp_path):
    tasks = TaskBridge(store=TaskStore(path=tmp_path / "tasks.json"))
    events = EventBridge(store=EventStore(path=tmp_path / "events.json"))
    # 注意:任务/事件用根 Window 的 todayIso(curToday),这里只验证绑定路径不报错。
    tasks.add("冒烟任务", "meeting", "2026-06-22")

    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    layout = _MockLayout()   # 持引用,防 GC
    ctx = engine.rootContext()
    ctx.setContextProperty("layout", layout)
    ctx.setContextProperty("tasks", tasks)
    ctx.setContextProperty("events", events)
    engine.load(QUrl.fromLocalFile(str(ROOT / "widgets" / "Calendar" / "Calendar.qml")))
    roots = engine.rootObjects()
    assert roots, "Calendar.qml 加载失败"
    root = roots[0]
    root.setProperty("expanded", True)   # 实例化 Dashboard → TasksCard/ProductivityCard
    app.processEvents()

    bad = [w for w in warnings
           if "TypeError" in w or "is not a function" in w or "undefined" in w]
    assert not bad, "展开后出现 QML 绑定错误:\n" + "\n".join(bad)
    root.setProperty("visible", False)
