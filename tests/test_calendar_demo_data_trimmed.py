from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_data_drops_task_and_productivity():
    js = (ROOT / "widgets" / "Calendar" / "DemoData.js").read_text(encoding="utf-8")
    assert "TASKS_WEEK" not in js
    assert "PRODUCTIVITY" not in js
    # 兜底/配置仍保留
    assert "WEATHER" in js and "LUNAR" in js and "LEGEND" in js
