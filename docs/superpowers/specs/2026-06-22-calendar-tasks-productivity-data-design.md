# 日历:任务 + 效率 改为真实本地数据 — 设计

日期:2026-06-22

## 目标

去掉日历仪表盘里写死的「任务」和「效率统计」demo 数据,改为真实、可编辑、本地持久化的数据。

## 现状(已查清)

| 卡片 | 现状 |
|---|---|
| 天气 / 农历 / 日程事件 | **已是真实数据**(Open-Meteo / 历法计算 / `event_store` 持久化),不动 |
| TasksCard 今日待办 + 本周 | **写死**:`demoTasks`(Calendar.qml)+ `Demo.TASKS_WEEK` |
| ProductivityCard 会议/完成/专注/进度 | **写死**:`Demo.PRODUCTIVITY` |

## 决策

- 数据源:**本地持久化**,完全照搬现有 `event_store`/`event_bridge` 架构。
- 第三个效率统计位:「专注时长」无真实数据源 → 换成「本周待办」(本周未完成任务数)。
- 初始:**空库**,用户用 `+` 自行添加;空状态显示「暂无待办」。

## 架构

新增两个文件,镜像事件那套(同样落盘 `~/.config/deepin-widgets/`、同样 `changed` 信号):

### `src/manager/task_store.py`

持久化 `tasks.json`,结构 `{"tasks": [<task>]}`。

任务:`{id, text, cat, due:"YYYY-MM-DD", done:bool, done_at:"YYYY-MM-DD"|""}`
- `cat` 复用 `event_store.CAT_COLORS`(work/personal/meeting/important/holiday),默认 `work`。
- 校验/规范化复用 `_valid_date`/`_norm_cat`(从 event_store 复用或并置)。

方法:
- `add(text, cat, due) -> id`(`due` 非法 → 抛 ValueError;`text` 空由桥层拦截)
- `toggle(id)`(翻转 `done`,同步写/清 `done_at`)
- `remove(id)`
- `today(today_iso) -> [task...]`:`due == today_iso`,未完成在前
- `week(today_iso) -> [task...]`:`today < due <= 本周日`,按 `due` 升序;每项附 `label`(如「本周五」)
- `done_in_week(today_iso) -> int`、`active_in_week(today_iso) -> int`(本周 = 周一~周日,含今天)

周边界:`weekday()`(Mon=0),`week_end = today + (6 - weekday)`,`week_start = today - weekday`。

### `src/manager/task_bridge.py`

`QObject`,`changed = Signal()`,Slots:
- `today(str) -> QVariantList`、`week(str) -> QVariantList`(每项含 `id/text/cat/color/done/label`)
- `toggle(str)`、`add(str text, str cat, str due)`、`remove(str)` —— 写后 `changed.emit()`
- `doneThisWeek(str) -> int`、`activeThisWeek(str) -> int`、`totalThisWeek(str) -> int`
- `catColor(str) -> str`(复用 CAT_COLORS)

### 注入

`app.py`:实例化 `TaskBridge()`,传入 `WidgetRuntime`;`runtime.py`:`setContextProperty("tasks", task_bridge)`(与 `events` 并列,同样的 None 守卫)。

## QML 改动

### TasksCard.qml
- 删 `import DemoData`、`todayModel` 改为读 `tasks` 桥。新增属性 `todayIso`(根传入)。
- 今日待办 = `tasks.today(todayIso)`;勾选 → `tasks.toggle(id)`;计数 = 未完成数。
- 本周 = `tasks.week(todayIso)`,行内显示 `label`(本周五),**也可勾选**(统一为任务行)。
- 右上 `+` → 内联添加表单(复刻 AgendaCard:文本框 + 分类选择,`due` 默认 `todayIso`)→ `tasks.add(...)`。
- `tasks.changed` 信号触发列表重算(`rev++` 模式,与现有 AgendaCard 一致)。
- 空状态:无今日待办时显示「暂无待办」。

### ProductivityCard.qml
- 删 `import DemoData`。新增属性:`todayIso`、`eventsSource`(events 桥)、`tasksSource`(tasks 桥)。
- 会议·今日 = `eventsSource.dayEvents(y,m,d)` 中 `cat=="meeting"` 计数(在 QML 算);
- 完成·本周 = `tasksSource.doneThisWeek(todayIso)`;
- 本周待办 = `tasksSource.activeThisWeek(todayIso)`;
- 进度条 = `doneThisWeek / max(1, totalThisWeek)`;
- 鼓励语:QML 内按进度计算(≥0.7「进展不错,继续保持!」否则「继续加油 💪」),非数据。

### Calendar.qml
- 删 `demoTasks` / `taskStore` / `Component.onCompleted` 里填充 taskStore 的循环。
- Dashboard 透传 `tasks` 桥 + `todayIso` 给 TasksCard / ProductivityCard(Dashboard.qml 增对应属性转发,events 桥已可用)。

### DemoData.js
- `TASKS_WEEK`、`PRODUCTIVITY` 删除(不再被引用)。
- `LEGEND`/`CAT` 保留(分类定义);`WEATHER`/`LUNAR` 保留(离线兜底)。

## 测试

- `tests/test_task_store.py`:add/toggle/remove、today/week 过滤、周边界、done/active 计数、空库、非法日期 —— 镜像 `test_event_store.py`,用临时文件。
- `tests/test_task_bridge.py`:Slots 透传、`changed` 信号发射、空 text 不写入 —— 镜像 `test_*` 桥测试风格。

## 不做(YAGNI)

- 不接第三方/云端;不做专注计时器;不做任务跨设备同步;不动天气/农历/事件。
