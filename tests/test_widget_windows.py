"""桌面挂件窗口必须用 Qt.Tool,以保证不进任务栏(只有管理器在任务栏)。

回归保护:Qt.Tool 让窗口在 X11 下被标为 _NET_WM_WINDOW_TYPE_UTILITY,映射即
排除出任务栏,无需等运行时 xlib 设置 skip-taskbar(那有 200ms 缺口)。
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

WIDGET_WINDOWS = [
    "widgets/Clock/Clock.qml",
    "widgets/Calendar/Calendar.qml",
]


@pytest.mark.parametrize("rel", WIDGET_WINDOWS)
def test_widget_window_uses_qt_tool(rel):
    qml = (ROOT / rel).read_text(encoding="utf-8")
    # 必须有一行 flags 同时含 FramelessWindowHint 与 Tool
    flag_lines = [ln for ln in qml.splitlines() if "flags:" in ln and "Qt.FramelessWindowHint" in ln]
    assert flag_lines, f"{rel} 未找到 flags 行"
    assert any("Qt.Tool" in ln for ln in flag_lines), f"{rel} 的窗口 flags 缺少 Qt.Tool(会进任务栏)"


def test_manager_window_is_not_tool():
    # 管理器应保留普通窗口(进任务栏),不要 Qt.Tool
    qml = (ROOT / "ui" / "Manager.qml").read_text(encoding="utf-8")
    flag_lines = [ln for ln in qml.splitlines() if "flags:" in ln]
    assert flag_lines, "Manager.qml 未找到 flags 行"
    assert not any("Qt.Tool" in ln for ln in flag_lines), "管理器不应是 Qt.Tool(它需要在任务栏)"
