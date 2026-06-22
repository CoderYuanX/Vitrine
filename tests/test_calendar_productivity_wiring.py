from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / "widgets" / "Calendar" / name).read_text(encoding="utf-8")


def test_productivity_derives_from_real_sources():
    qml = _read("ProductivityCard.qml")
    assert 'import "DemoData.js"' not in qml
    assert "Demo.PRODUCTIVITY" not in qml
    assert "tasks.doneThisWeek(" in qml
    assert "tasks.activeThisWeek(" in qml
    assert "events.dayEvents(" in qml
    assert '"meeting"' in qml


def test_productivity_has_no_focus_hours_stat():
    qml = _read("ProductivityCard.qml")
    assert "专注时长" not in qml
    assert "待办" in qml


def test_dashboard_passes_dates_to_productivity():
    qml = _read("Dashboard.qml")
    assert "ProductivityCard" in qml
    assert "todayIso: root.todayIso" in qml
