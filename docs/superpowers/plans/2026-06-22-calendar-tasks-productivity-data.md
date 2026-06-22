# Calendar Tasks + Productivity Real Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the calendar dashboard's hardcoded task list and productivity stats with real, editable, locally-persisted data.

**Architecture:** Mirror the existing `event_store`/`event_bridge` pattern — a `TaskStore` (JSON at `~/.config/deepin-widgets/tasks.json`) + a `TaskBridge` QObject injected into QML as context property `tasks`. TasksCard reads/writes it; ProductivityCard derives all three stats from real data (today's meeting events + this-week task counts).

**Tech Stack:** Python 3.12, PySide6 (QObject/Slot/Signal), Qt Quick/QML, pytest.

## Global Constraints

- Persist under `~/.config/deepin-widgets/` (same dir as `events.json`), JSON with `indent=2, ensure_ascii=False`.
- Category keys/colors reuse `event_store.CAT_COLORS` (work/personal/meeting/important/holiday), default `work`.
- QML cards access context properties defensively: `typeof tasks !== "undefined"` guard (cards must still load when the bridge is absent, e.g. in offscreen tests).
- No emoji icons in expanded cards (existing test `test_expanded_calendar_qml_avoids_emoji_icons`).
- Task = `{id, text, cat, due:"YYYY-MM-DD", done:bool}`. No `done_at` (unused → YAGNI).
- Week = Monday–Sunday containing `today`; `week_start = today - weekday()`, `week_end = today + (6 - weekday())` (Mon=0).

---

### Task 1: TaskStore (persistence)

**Files:**
- Create: `src/manager/task_store.py`
- Test: `tests/test_task_store.py`

**Interfaces:**
- Consumes: `event_store.CAT_COLORS`, `event_store._DEFAULT_CAT`, `event_store._norm_cat`, `event_store._valid_date`.
- Produces: `TaskStore(path=None)` with `add(text, cat, due)->id`, `toggle(id)`, `remove(id)`, `today(today_iso)->list`, `week(today_iso)->list` (each item gains `label`), `done_in_week(today_iso)->int`, `active_in_week(today_iso)->int`. Task dict keys: `id,text,cat,due,done`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_task_store.py
from pathlib import Path

import pytest

from manager.task_store import TaskStore


@pytest.fixture
def store(tmp_path):
    return TaskStore(path=tmp_path / "tasks.json")


def test_add_then_today_lists_it(store):
    store.add("写周报", cat="work", due="2026-06-22")
    items = store.today("2026-06-22")
    assert len(items) == 1
    assert items[0]["text"] == "写周报"
    assert items[0]["cat"] == "work"
    assert items[0]["done"] is False
    assert items[0]["id"]


def test_today_filters_by_due_date(store):
    store.add("今天", due="2026-06-22")
    store.add("明天", due="2026-06-23")
    assert [t["text"] for t in store.today("2026-06-22")] == ["今天"]


def test_toggle_flips_done_and_persists(store):
    tid = store.add("a", due="2026-06-22")
    store.toggle(tid)
    assert store.today("2026-06-22")[0]["done"] is True
    # 重新打开同一文件,done 应持久
    again = TaskStore(path=store.path)
    assert again.today("2026-06-22")[0]["done"] is True
    store.toggle(tid)
    assert store.today("2026-06-22")[0]["done"] is False


def test_remove(store):
    tid = store.add("a", due="2026-06-22")
    store.remove(tid)
    assert store.today("2026-06-22") == []


def test_week_excludes_today_includes_rest_of_week_with_label(store):
    # 2026-06-22 是周一 → 本周 06-22(一)~06-28(日)
    store.add("今天", due="2026-06-22")
    store.add("周五", due="2026-06-26")
    store.add("下周一", due="2026-06-29")
    wk = store.week("2026-06-22")
    assert [t["text"] for t in wk] == ["周五"]      # 不含今天、不含下周
    assert wk[0]["label"] == "本周五"


def test_week_counts_done_and_active_include_today(store):
    store.add("今天-未完成", due="2026-06-22")
    t2 = store.add("今天-已完成", due="2026-06-22")
    store.add("周三-未完成", due="2026-06-24")
    store.toggle(t2)
    assert store.done_in_week("2026-06-22") == 1
    assert store.active_in_week("2026-06-22") == 2


def test_empty_store_returns_empty(store):
    assert store.today("2026-06-22") == []
    assert store.week("2026-06-22") == []
    assert store.done_in_week("2026-06-22") == 0
    assert store.active_in_week("2026-06-22") == 0


def test_invalid_due_raises(store):
    with pytest.raises(ValueError):
        store.add("x", due="not-a-date")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_task_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'manager.task_store'`
(Note: `tests/conftest.py` already puts `src/` on `sys.path`; `manager.*` imports work as in `test_event_store.py`.)

- [ ] **Step 3: Write the implementation**

```python
# src/manager/task_store.py
import json
import uuid
from datetime import date, timedelta
from pathlib import Path

from .event_store import CAT_COLORS, _DEFAULT_CAT, _norm_cat, _valid_date  # noqa: F401

# 周几简称(Mon=0),供"本周X"标签
_WEEK_SHORT = ["一", "二", "三", "四", "五", "六", "日"]


def _week_bounds(today_iso):
    """返回 (week_start_iso, week_end_iso),周一~周日(含今天所在周)。"""
    d = date.fromisoformat(str(today_iso))
    start = d - timedelta(days=d.weekday())
    end = d + timedelta(days=6 - d.weekday())
    return start.isoformat(), end.isoformat()


class TaskStore:
    """本地可编辑任务库,持久化到 ~/.config/deepin-widgets/tasks.json。

    结构: {"tasks": [{"id","text","cat","due":"YYYY-MM-DD","done":bool}]}
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else (
            Path.home() / ".config" / "deepin-widgets" / "tasks.json")

    # ---- 持久化 ----
    def _load(self):
        if not self.path.exists():
            return {"tasks": []}
        try:
            d = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"tasks": []}
        if not isinstance(d, dict) or not isinstance(d.get("tasks"), list):
            return {"tasks": []}
        return d

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _all(self):
        out = []
        for t in self._load()["tasks"]:
            if not isinstance(t, dict) or "due" not in t:
                continue
            out.append({
                "id": str(t.get("id", "")),
                "text": str(t.get("text", "")),
                "cat": _norm_cat(t.get("cat", _DEFAULT_CAT)),
                "due": str(t["due"]),
                "done": bool(t.get("done", False)),
            })
        return out

    # ---- 写 ----
    def add(self, text, cat=_DEFAULT_CAT, due=""):
        due = str(due)
        if not _valid_date(due):
            raise ValueError(f"invalid due: {due!r}")
        d = self._load()
        tid = uuid.uuid4().hex[:8]
        d["tasks"].append({
            "id": tid,
            "text": str(text),
            "cat": _norm_cat(cat),
            "due": due,
            "done": False,
        })
        self._save(d)
        return tid

    def toggle(self, tid):
        d = self._load()
        for t in d["tasks"]:
            if str(t.get("id", "")) == str(tid):
                t["done"] = not bool(t.get("done", False))
                break
        self._save(d)

    def remove(self, tid):
        d = self._load()
        d["tasks"] = [t for t in d["tasks"] if str(t.get("id", "")) != str(tid)]
        self._save(d)

    # ---- 读 ----
    def today(self, today_iso):
        items = [t for t in self._all() if t["due"] == str(today_iso)]
        items.sort(key=lambda t: (t["done"], t["text"]))
        return items

    def week(self, today_iso):
        _, end = _week_bounds(today_iso)
        items = [t for t in self._all() if str(today_iso) < t["due"] <= end]
        items.sort(key=lambda t: (t["due"], t["done"]))
        for t in items:
            wd = date.fromisoformat(t["due"]).weekday()
            t["label"] = "本周" + _WEEK_SHORT[wd]
        return items

    def done_in_week(self, today_iso):
        start, end = _week_bounds(today_iso)
        return sum(1 for t in self._all() if start <= t["due"] <= end and t["done"])

    def active_in_week(self, today_iso):
        start, end = _week_bounds(today_iso)
        return sum(1 for t in self._all() if start <= t["due"] <= end and not t["done"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_task_store.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/manager/task_store.py tests/test_task_store.py
git commit -m "feat(calendar): TaskStore 本地任务持久化"
```

---

### Task 2: TaskBridge (QML bridge)

**Files:**
- Create: `src/manager/task_bridge.py`
- Test: `tests/test_task_bridge.py`

**Interfaces:**
- Consumes: `TaskStore` (Task 1), `event_store.CAT_COLORS`.
- Produces: `TaskBridge(store=None)` QObject. Slots: `today(str)->QVariantList`, `week(str)->QVariantList` (items decorated with `color`), `toggle(str)`, `add(str text, str cat, str due)`, `remove(str)`, `doneThisWeek(str)->int`, `activeThisWeek(str)->int`, `totalThisWeek(str)->int`, `catColor(str)->str`. Signal: `changed`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_task_bridge.py
import pytest

from manager.task_bridge import TaskBridge
from manager.task_store import TaskStore


@pytest.fixture
def bridge(tmp_path):
    return TaskBridge(store=TaskStore(path=tmp_path / "tasks.json"))


def test_add_emits_changed_and_today_returns_colored(bridge, qtbot=None):
    fired = []
    bridge.changed.connect(lambda: fired.append(1))
    bridge.add("写周报", "meeting", "2026-06-22")
    assert fired, "add 应发 changed"
    items = bridge.today("2026-06-22")
    assert len(items) == 1
    assert items[0]["text"] == "写周报"
    assert items[0]["color"] == "#7c3aed"   # meeting 色


def test_blank_text_not_added(bridge):
    bridge.add("   ", "work", "2026-06-22")
    assert bridge.today("2026-06-22") == []


def test_invalid_due_swallowed(bridge):
    bridge.add("x", "work", "bad-date")      # 不抛、不写入
    assert bridge.today("2026-06-22") == []


def test_toggle_and_week_counts(bridge):
    bridge.add("a", "work", "2026-06-22")
    tid = bridge.add("b", "work", "2026-06-22")
    bridge.toggle(tid)
    assert bridge.doneThisWeek("2026-06-22") == 1
    assert bridge.activeThisWeek("2026-06-22") == 1
    assert bridge.totalThisWeek("2026-06-22") == 2


def test_week_items_have_label_and_color(bridge):
    bridge.add("周五", "personal", "2026-06-26")
    wk = bridge.week("2026-06-22")
    assert wk[0]["label"] == "本周五"
    assert wk[0]["color"] == "#16a34a"


def test_catColor(bridge):
    assert bridge.catColor("important") == "#d97706"
    assert bridge.catColor("nope") == "#2f6bff"   # 回落 work
```

(The `qtbot=None` default keeps the test runnable without pytest-qt; signals are plain Python connects.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_task_bridge.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'manager.task_bridge'`

- [ ] **Step 3: Write the implementation**

```python
# src/manager/task_bridge.py
from PySide6.QtCore import QObject, Signal, Slot

from .event_store import CAT_COLORS
from .task_store import TaskStore


class TaskBridge(QObject):
    """QML 与 TaskStore 之间的桥(注入为 context property `tasks`)。变更后发 changed。"""

    changed = Signal()

    def __init__(self, store=None):
        super().__init__()
        self._s = store or TaskStore()

    def _deco(self, t):
        t = dict(t)
        t["color"] = CAT_COLORS.get(t["cat"], CAT_COLORS["work"])
        return t

    @Slot(str, result="QVariantList")
    def today(self, today_iso):
        return [self._deco(t) for t in self._s.today(today_iso)]

    @Slot(str, result="QVariantList")
    def week(self, today_iso):
        return [self._deco(t) for t in self._s.week(today_iso)]

    @Slot(str)
    def toggle(self, tid):
        self._s.toggle(tid)
        self.changed.emit()

    @Slot(str, str, str)
    def add(self, text, cat, due):
        text = (text or "").strip()
        if not text:
            return
        try:
            self._s.add(text, cat=cat or "work", due=due)
        except ValueError:
            return
        self.changed.emit()

    @Slot(str)
    def remove(self, tid):
        self._s.remove(tid)
        self.changed.emit()

    @Slot(str, result=int)
    def doneThisWeek(self, today_iso):
        return self._s.done_in_week(today_iso)

    @Slot(str, result=int)
    def activeThisWeek(self, today_iso):
        return self._s.active_in_week(today_iso)

    @Slot(str, result=int)
    def totalThisWeek(self, today_iso):
        return self._s.done_in_week(today_iso) + self._s.active_in_week(today_iso)

    @Slot(str, result=str)
    def catColor(self, cat):
        return CAT_COLORS.get(cat, CAT_COLORS["work"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_task_bridge.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/manager/task_bridge.py tests/test_task_bridge.py
git commit -m "feat(calendar): TaskBridge 桥接 + 派生周统计"
```

---

### Task 3: Wire `tasks` bridge into the runtime

**Files:**
- Modify: `src/manager/runtime.py` (constructor + `show_widget`)
- Modify: `src/manager/app.py` (instantiate + pass)
- Test: `tests/test_task_wiring.py`

**Interfaces:**
- Consumes: `TaskBridge` (Task 2), existing `WidgetRuntime`.
- Produces: `WidgetRuntime(..., task_bridge=None)`; widget engines get context property `tasks`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_task_wiring.py
import inspect

from manager.runtime import WidgetRuntime


def test_runtime_accepts_task_bridge_param():
    sig = inspect.signature(WidgetRuntime.__init__)
    assert "task_bridge" in sig.parameters


def test_runtime_sets_tasks_context_property():
    src = inspect.getsource(WidgetRuntime.show_widget)
    assert 'setContextProperty("tasks"' in src


def test_app_constructs_and_passes_task_bridge():
    import manager.app as app_mod
    src = inspect.getsource(app_mod)
    assert "TaskBridge" in src
    assert "task_bridge" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_task_wiring.py -q`
Expected: FAIL (`task_bridge` not in signature)

- [ ] **Step 3: Edit `runtime.py`**

In `WidgetRuntime.__init__`, change the signature line and add storage:

```python
    def __init__(self, app, widgets, config, layout_bridge, event_bridge=None,
                 weather_bridge=None, calendar_info_bridge=None, task_bridge=None):
        self.app = app
        self.widgets = widgets
        self.config = config
        self.bridge = layout_bridge
        self.event_bridge = event_bridge
        self.weather_bridge = weather_bridge
        self.calendar_info_bridge = calendar_info_bridge
        self.task_bridge = task_bridge
        self.engines = {}
```

In `show_widget`, after the `calendarInfo` context property block, add:

```python
        if self.calendar_info_bridge is not None:
            eng.rootContext().setContextProperty("calendarInfo", self.calendar_info_bridge)
        if self.task_bridge is not None:
            eng.rootContext().setContextProperty("tasks", self.task_bridge)
```

- [ ] **Step 4: Edit `app.py`**

Add the import near the other bridge imports (`from .event_bridge import EventBridge` block):

```python
        from .task_bridge import TaskBridge
```

Instantiate it next to the other bridges (after `self.calendar_info_bridge = CalendarInfoBridge()`):

```python
        self.task_bridge = TaskBridge()
```

Pass it into `WidgetRuntime(...)` as a keyword arg:

```python
        self.runtime = WidgetRuntime(self.app, self.widgets, self.config,
                                     self.layout_bridge, self.event_bridge,
                                     self.weather_bridge,
                                     self.calendar_info_bridge,
                                     task_bridge=self.task_bridge)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_task_wiring.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/manager/runtime.py src/manager/app.py tests/test_task_wiring.py
git commit -m "feat(calendar): 注入 tasks 桥到挂件运行时"
```

---

### Task 4: TasksCard → real tasks (read + toggle + add form)

**Files:**
- Modify: `widgets/Calendar/TasksCard.qml` (full rewrite)
- Modify: `widgets/Calendar/Dashboard.qml` (TasksCard instantiation)
- Modify: `widgets/Calendar/Calendar.qml` (drop demoTasks/taskStore; Dashboard no longer takes tasksModel)
- Test: `tests/test_calendar_tasks_wiring.py`

**Interfaces:**
- Consumes: context property `tasks` (Task 3) with `today/week/toggle/add`; `Dashboard.todayIso` (already exists).
- Produces: `TasksCard { todayIso; accent }` (no more `todayModel`/`tasksModel`).

- [ ] **Step 1: Write the failing source test**

```python
# tests/test_calendar_tasks_wiring.py
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
    assert "暂无待办" in qml                       # 空状态


def test_calendar_root_drops_demo_tasks():
    qml = _read("Calendar.qml")
    assert "demoTasks" not in qml
    assert "ListModel { id: taskStore }" not in qml


def test_dashboard_passes_todayiso_to_tasks_card():
    qml = _read("Dashboard.qml")
    assert "TasksCard" in qml
    assert "tasksModel" not in qml
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_calendar_tasks_wiring.py -q`
Expected: FAIL (Demo still imported / demoTasks present)

- [ ] **Step 3: Rewrite `widgets/Calendar/TasksCard.qml`**

```qml
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

// 任务卡(grid-area:tasks):读写本地任务库(context property `tasks`)。
Rectangle {
    id: card
    property string todayIso: ""
    property color accent: "#2f6bff"
    property int rev: 0
    property bool adding: false
    property string newCat: "work"

    readonly property var cats: [
        { key: "work",      label: "工作", color: "#2f6bff" },
        { key: "personal",  label: "个人", color: "#16a34a" },
        { key: "meeting",   label: "会议", color: "#7c3aed" },
        { key: "important", label: "重要", color: "#d97706" },
        { key: "holiday",   label: "假期", color: "#ec4899" }
    ]
    function _has() { return typeof tasks !== "undefined" && tasks }
    function todayList() { return (card.rev, card._has() && card.todayIso) ? tasks.today(card.todayIso) : [] }
    function weekList()  { return (card.rev, card._has() && card.todayIso) ? tasks.week(card.todayIso)  : [] }
    function _catLabel(key) {
        var c = card.cats.filter(function (x) { return x.key === key })
        return c.length ? c[0].label : key
    }

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    Connections {
        target: card._has() ? tasks : null
        ignoreUnknownSignals: true
        function onChanged() { card.rev++ }
    }

    component TaskRow: RowLayout {
        property string tid: ""
        property bool done: false
        property string text_: ""
        property string rightText: ""
        property color rightColor: "#9aa3b8"
        property bool isTag: false
        Layout.fillWidth: true
        spacing: 9
        Rectangle {
            Layout.preferredWidth: 17; Layout.preferredHeight: 17; Layout.alignment: Qt.AlignTop
            radius: 5
            color: done ? card.accent : "transparent"
            border.width: 1.8; border.color: done ? card.accent : "#c2c9d8"
            Text { anchors.centerIn: parent; visible: done; text: "✓"; color: "white"; font.pixelSize: 11; font.weight: Font.Bold }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                onClicked: if (card._has()) tasks.toggle(tid) }
        }
        Text {
            Layout.fillWidth: true; text: text_
            font.pixelSize: 13; wrapMode: Text.WordWrap
            color: done ? "#aeb4c4" : "#2a3350"; font.strikeout: done
        }
        Item {
            visible: isTag; Layout.alignment: Qt.AlignTop
            implicitWidth: tagT.implicitWidth + 14; implicitHeight: tagT.implicitHeight + 4
            Rectangle { anchors.fill: parent; radius: 6; color: rightColor; opacity: 0.13 }
            Text { id: tagT; anchors.centerIn: parent; text: rightText; font.pixelSize: 11; font.weight: Font.Bold; color: rightColor }
        }
        Text { visible: !isTag; Layout.alignment: Qt.AlignTop; text: rightText; font.pixelSize: 12; color: "#9aa3b8" }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16; anchors.rightMargin: 16
        anchors.topMargin: 15; anchors.bottomMargin: 15
        spacing: 0

        // 标题 + 添加
        RowLayout {
            Layout.fillWidth: true
            Text { text: "任务与提醒"; font.pixelSize: 15; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: 24; height: 24; radius: 7
                color: addMA.containsMouse ? "#eef2fb" : "transparent"
                Text { anchors.centerIn: parent; text: card.adding ? "×" : "+"; font.pixelSize: 18; font.weight: Font.Bold; color: card.accent }
                MouseArea { id: addMA; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: card.adding = !card.adding }
            }
        }

        // 添加表单
        ColumnLayout {
            Layout.fillWidth: true; Layout.topMargin: card.adding ? 10 : 0; spacing: 8
            visible: card.adding
            TextField {
                id: titleField
                Layout.fillWidth: true; placeholderText: "任务内容"; font.pixelSize: 13; color: "#1c2440"
                background: Rectangle { radius: 8; color: "#f4f6fb"; border.width: 1; border.color: "#e3e8f2" }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Repeater {
                    model: card.cats
                    delegate: Rectangle {
                        width: 18; height: 18; radius: 9; color: modelData.color
                        opacity: card.newCat === modelData.key ? 1.0 : 0.32
                        border.width: card.newCat === modelData.key ? 2 : 0; border.color: "#1c2440"
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: card.newCat = modelData.key }
                    }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    width: okT.implicitWidth + 22; height: 26; radius: 8; color: card.accent
                    Text { id: okT; anchors.centerIn: parent; text: "添加"; font.pixelSize: 12; font.weight: Font.Bold; color: "white" }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (card._has() && titleField.text.trim().length) {
                                tasks.add(titleField.text, card.newCat, card.todayIso)
                                titleField.text = ""; card.adding = false
                            }
                        }
                    }
                }
            }
        }

        // 今日待办
        RowLayout {
            Layout.topMargin: 12; Layout.bottomMargin: 6; spacing: 7
            Text { text: "今日待办"; font.pixelSize: 13; font.weight: Font.Bold; color: card.accent }
            Text { text: card.todayList().length; font.pixelSize: 11; color: "#9aa3b8" }
        }
        Repeater {
            model: card.todayList()
            delegate: TaskRow {
                Layout.topMargin: 4; Layout.bottomMargin: 4
                tid: modelData.id; done: modelData.done; text_: modelData.text
                isTag: true; rightText: card._catLabel(modelData.cat); rightColor: modelData.color
            }
        }
        Text { visible: card.todayList().length === 0; Layout.topMargin: 2
               text: "暂无待办"; font.pixelSize: 12; color: "#aab2c0" }

        // 本周
        RowLayout {
            Layout.topMargin: 10; Layout.bottomMargin: 4; spacing: 7
            Text { text: "本周"; font.pixelSize: 13; font.weight: Font.Bold; color: "#6471a8" }
            Text { text: card.weekList().length; font.pixelSize: 11; color: "#9aa3b8" }
        }
        Repeater {
            model: card.weekList()
            delegate: TaskRow {
                Layout.topMargin: 4; Layout.bottomMargin: 4
                tid: modelData.id; done: modelData.done; text_: modelData.text
                isTag: false; rightText: modelData.label
            }
        }

        Item { Layout.fillHeight: true }
        Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(120/255,130/255,160/255,0.16) }
        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 10
            Text { text: "查看全部"; font.pixelSize: 13; font.weight: Font.Bold; color: "#2a3350" }
            Item { Layout.fillWidth: true }
            Text { text: "›"; font.pixelSize: 16; font.weight: Font.Bold; color: card.accent }
        }
    }
}
```

- [ ] **Step 4: Edit `widgets/Calendar/Dashboard.qml`**

Remove the `tasksModel` property declaration (line `property var tasksModel`), and change the TasksCard instantiation (inside its `Rising`) from:

```qml
                TasksCard { anchors.fill: parent; todayModel: root.tasksModel; accent: root.accent }
```

to:

```qml
                TasksCard { anchors.fill: parent; todayIso: root.todayIso; accent: root.accent }
```

- [ ] **Step 5: Edit `widgets/Calendar/Calendar.qml`**

Delete the `ListModel { id: taskStore }` line, the entire `QtObject { id: demoTasks ... }` block, and the `Component.onCompleted` loop that fills `taskStore` (the `var T = demoTasks.list ... taskStore.append(...)` lines — keep the layout-restore lines). In the Dashboard instantiation remove the `tasksModel: taskStore` line.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_calendar_tasks_wiring.py tests/test_calendar_zoom.py -q`
Expected: PASS (Calendar.qml still loads under offscreen with only the `layout` mock; `tasks` guarded by `typeof`).

- [ ] **Step 7: Commit**

```bash
git add widgets/Calendar/TasksCard.qml widgets/Calendar/Dashboard.qml widgets/Calendar/Calendar.qml tests/test_calendar_tasks_wiring.py
git commit -m "feat(calendar): TasksCard 接真实任务库 + 内联添加"
```

---

### Task 5: ProductivityCard → derived stats

**Files:**
- Modify: `widgets/Calendar/ProductivityCard.qml` (full rewrite)
- Modify: `widgets/Calendar/Dashboard.qml` (ProductivityCard instantiation)
- Test: `tests/test_calendar_productivity_wiring.py`

**Interfaces:**
- Consumes: context properties `tasks` (`doneThisWeek/activeThisWeek/totalThisWeek`) and `events` (`dayEvents`); `Dashboard.year/month/today/todayIso` (already exist).
- Produces: `ProductivityCard { accent; todayIso; year; month; today }`.

- [ ] **Step 1: Write the failing source test**

```python
# tests/test_calendar_productivity_wiring.py
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
    assert '"meeting"' in qml          # 会议派生自事件分类


def test_productivity_has_no_focus_hours_stat():
    qml = _read("ProductivityCard.qml")
    assert "专注时长" not in qml         # 改成了"待办"
    assert "待办" in qml


def test_dashboard_passes_dates_to_productivity():
    qml = _read("Dashboard.qml")
    assert "ProductivityCard" in qml
    # 传 today/todayIso 供派生
    assert "todayIso: root.todayIso" in qml
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_calendar_productivity_wiring.py -q`
Expected: FAIL (Demo.PRODUCTIVITY still present)

- [ ] **Step 3: Rewrite `widgets/Calendar/ProductivityCard.qml`**

```qml
import QtQuick
import QtQuick.Layouts

// 效率卡(grid-area:prod):三项统计全部派生自真实数据(events + tasks 桥)。
Rectangle {
    id: card
    property color accent: "#2f6bff"
    property string todayIso: ""
    property int year: 2026
    property int month: 5      // 0-11
    property int today: 1      // 当月日;-1 表示非当月
    property int rev: 0

    function _hasTasks()  { return typeof tasks  !== "undefined" && tasks }
    function _hasEvents() { return typeof events !== "undefined" && events }
    function meetingsToday() {
        if (!card._hasEvents() || card.today < 1) return 0
        var evs = (card.rev, events.dayEvents(card.year, card.month, card.today))
        var n = 0
        for (var i = 0; i < evs.length; i++) if (evs[i].cat === "meeting") n++
        return n
    }
    function doneWeek()   { return (card.rev, card._hasTasks() && card.todayIso) ? tasks.doneThisWeek(card.todayIso)   : 0 }
    function activeWeek() { return (card.rev, card._hasTasks() && card.todayIso) ? tasks.activeThisWeek(card.todayIso) : 0 }
    function totalWeek()  { return (card.rev, card._hasTasks() && card.todayIso) ? tasks.totalThisWeek(card.todayIso)  : 0 }
    function progress()   { var t = totalWeek(); return t > 0 ? doneWeek() / t : 0 }

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    Connections { target: card._hasTasks()  ? tasks  : null; ignoreUnknownSignals: true; function onChanged() { card.rev++ } }
    Connections { target: card._hasEvents() ? events : null; ignoreUnknownSignals: true; function onChanged() { card.rev++ } }

    component Stat: ColumnLayout {
        property string label: ""
        property string value: ""
        property string sub: ""
        spacing: 0
        Text { text: label; font.pixelSize: 11; color: "#9aa3b8" }
        Text { text: value; font.pixelSize: 26; font.weight: Font.Bold; color: "#1c2440" }
        Text { text: sub; font.pixelSize: 10; color: "#b3bacb" }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 15; anchors.rightMargin: 15
        anchors.topMargin: 14; anchors.bottomMargin: 14
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Text { text: "效率"; font.pixelSize: 13; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Text { text: "⋮"; font.pixelSize: 14; color: "#9aa3b8" }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 14
            Stat { label: "会议";    value: "" + card.meetingsToday(); sub: "今日" }
            Item { Layout.fillWidth: true }
            Stat { label: "完成任务"; value: "" + card.doneWeek();      sub: "本周" }
            Item { Layout.fillWidth: true }
            Stat { label: "待办";    value: "" + card.activeWeek();    sub: "本周" }
        }

        Item { Layout.fillHeight: true }
        Rectangle {
            Layout.fillWidth: true; height: 6; radius: 3
            color: Qt.rgba(120/255, 130/255, 160/255, 0.18)
            Rectangle { width: parent.width * card.progress(); height: parent.height; radius: 3; color: card.accent }
        }
        Text {
            text: card.progress() >= 0.7 ? "进展不错,继续保持!" : "继续加油!"
            font.pixelSize: 12; color: "#6471a8"; Layout.topMargin: 7
        }
    }
}
```

- [ ] **Step 4: Edit `widgets/Calendar/Dashboard.qml`**

Change the ProductivityCard instantiation (inside its `Rising`) from:

```qml
                ProductivityCard { anchors.fill: parent; accent: root.accent }
```

to:

```qml
                ProductivityCard {
                    anchors.fill: parent; accent: root.accent
                    todayIso: root.todayIso; year: root.year; month: root.month; today: root.today
                }
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_calendar_productivity_wiring.py tests/test_calendar_expanded_style.py -q`
Expected: PASS (no emoji introduced; `专注时长` removed)

- [ ] **Step 6: Commit**

```bash
git add widgets/Calendar/ProductivityCard.qml widgets/Calendar/Dashboard.qml tests/test_calendar_productivity_wiring.py
git commit -m "feat(calendar): ProductivityCard 三项统计派生自真实数据"
```

---

### Task 6: Remove dead demo data + full-suite green

**Files:**
- Modify: `widgets/Calendar/DemoData.js` (delete `TASKS_WEEK`, `PRODUCTIVITY`)
- Test: `tests/test_calendar_demo_data_trimmed.py`

**Interfaces:**
- Consumes: nothing.
- Produces: leaner `DemoData.js` (keeps `CAT`, `LEGEND`, `WEATHER`, `LUNAR`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_calendar_demo_data_trimmed.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_data_drops_task_and_productivity():
    js = (ROOT / "widgets" / "Calendar" / "DemoData.js").read_text(encoding="utf-8")
    assert "TASKS_WEEK" not in js
    assert "PRODUCTIVITY" not in js
    # 兜底/配置仍保留
    assert "WEATHER" in js and "LUNAR" in js and "LEGEND" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_calendar_demo_data_trimmed.py -q`
Expected: FAIL (TASKS_WEEK/PRODUCTIVITY still present)

- [ ] **Step 3: Edit `widgets/Calendar/DemoData.js`**

Delete the `var TASKS_WEEK = [...]` block (with its `// 本周(演示)` comment) and the `var PRODUCTIVITY = {...}` block (with its `// 效率(演示)` comment). Leave `CAT`, `LEGEND`, `WEATHER`, `LUNAR` intact.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (all green — new task tests + existing suite)

- [ ] **Step 5: Commit**

```bash
git add widgets/Calendar/DemoData.js tests/test_calendar_demo_data_trimmed.py
git commit -m "chore(calendar): 删除任务/效率的写死 demo 数据"
```

---

## Self-Review

**Spec coverage:** task_store (T1) ✓, task_bridge + derived week stats (T2) ✓, injection as `tasks` (T3) ✓, TasksCard today/week/toggle/add/empty-state (T4) ✓, ProductivityCard meetings-from-events + done/active week + progress + note (T5) ✓, Calendar/Dashboard cleanup (T4/T5) ✓, DemoData trim (T6) ✓, tests for store+bridge (T1/T2) ✓. "会议·今日" via events `cat=meeting` ✓. Third stat = 「待办」 ✓. Empty store ✓.

**Placeholder scan:** none — every step has full code or exact edit instructions.

**Type consistency:** Task dict keys `id,text,cat,due,done` consistent across store/bridge; bridge adds `color`; `week()` adds `label`. QML reads `modelData.id/text/done/cat/color/label`. Bridge slot names (`today/week/toggle/add/remove/doneThisWeek/activeThisWeek/totalThisWeek/catColor`) match QML call sites. `WidgetRuntime(..., task_bridge=...)` matches app.py call.
