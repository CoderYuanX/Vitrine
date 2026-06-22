from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / "widgets" / "Calendar" / name).read_text(encoding="utf-8")


def test_tasks_card_uses_tasks_bridge_not_demo():
    qml = _read("TasksCard.qml")
    assert 'import "DemoData.js"' not in qml
    assert "Demo.TASKS_WEEK" not in qml
    assert "tasks.today(" in qml and "tasks.week(" in qml
    assert "tasks.toggle(" in qml and "tasks.add(" in qml
    assert "暂无待办" in qml


def test_calendar_root_drops_demo_tasks():
    qml = _read("Calendar.qml")
    assert "demoTasks" not in qml
    assert "ListModel { id: taskStore }" not in qml


def test_dashboard_passes_todayiso_to_tasks_card():
    qml = _read("Dashboard.qml")
    assert "TasksCard" in qml
    assert "tasksModel" not in qml
