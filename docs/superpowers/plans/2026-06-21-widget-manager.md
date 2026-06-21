# 桌面小组件管理器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `~/Desktop/managewidgets` 建一个 PySide6+QML 顶层桌面应用:既渲染 macOS 风管理界面(复刻 web 原型),又拥有/管理桌面小组件卡片,单进程内存直调实时联动。

**Architecture:** 一个进程。`ManagerApp` 持有 `QApplication`、`WidgetRuntime`(管理桌面卡片窗口,吸收原 widgets_host)、`CatalogBridge`(管理界面唯一数据源)、托盘、管理窗口。管理界面改 enabled 直接调运行时显隐卡片 + 落 config,无需 IPC/文件监听。

**Tech Stack:** PySide6 6.8 / Qt Quick(QML)/ psutil / python-xlib;pytest 测 Python 逻辑;QML 用运行+截图比对原型验证。

## Global Constraints

- Python 3.12;`PySide6>=6.6`(本机 Qt6.8)、`psutil>=5.9`、`requests>=2.31`、`python-xlib>=0.33`(linux)。
- 平台 Deepin 25 / X11;桌面卡片无边框,EWMH 跳过任务栏(沿用既有 x11.py)。
- 配置文件:`~/.config/deepin-widgets/config.json`,结构 `{"widgets":{"<id>":{"enabled":bool,"x":int,"y":int,"zoom":float}}}`。
- 单实例锁:`~/.config/deepin-widgets/.deepin-widgets.lock`(flock)。
- 管理窗口固定 `920×624`,无边框自绘标题栏,圆角 18,主投影 `0 24px 70px rgba(40,78,160,0.22), 0 2px 8px rgba(40,78,160,0.08)`。
- 字体族:`"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif`。
- 设计真相:`docs/design-specs/2026-06-21-widget-manager-ui.md`(像素契约)+ `docs/superpowers/specs/2026-06-21-widget-manager-design.md`(架构)。所有颜色/字号/间距以 UI 规格为准。
- 仓库已 `git init`,设计文档已在 commit `edda9b1`。原 `~/Desktop/widgets` 保留不动。
- 测试可见性:Python 逻辑全 TDD;运行时显隐与全部 QML 走"运行 + 截图与原型逐区比对"。

### 关键设计决策(实现者必读)
1. **画廊预览**:用户选"实时 QML 缩略"。但桌面 `Clock.qml` 是深色卡,与原型画廊里的浅色时钟预览不一致。**按设计源(UI 规格)优先级,画廊卡身用专门的浅色 `Preview.qml`(复刻原型样式)+ 实时数据**,而非把深色桌面卡塞进画廊。v1 仅时钟有真实预览,其余 5 类为"即将推出"占位。
2. **6 类组件来源**:registry 扫 `widgets/*/widget.json`。给 weather/calendar/system/note/launcher 各建 `implemented:false` 的桩 `widget.json`(无 qml),让画廊"列全部、灰显占位"。
3. **运行时不创建 QApplication**:由 ManagerApp 创建并注入,便于职责分离。
4. **CatalogBridge 用假运行时单测**(运行时本身靠跑 App 验证)。

### 文件结构(实现后)
```
managewidgets/
├── main.py
├── requirements.txt
├── src/manager/{__init__,app,runtime,registry,config_store,catalog_bridge,layout_bridge,tray,single_instance,x11,autostart}.py
├── ui/{Manager,TitleBar,Sidebar,NavItem,GalleryCard}.qml
├── widgets/Clock/{widget.json,Clock.qml,Preview.qml}
├── widgets/{Weather,Calendar,System,Note,Launcher}/widget.json   # 桩 implemented:false
├── tools/preview_manager.py                                       # 截图用:假数据加载 Manager.qml
└── tests/{test_config_store,test_registry,test_catalog_bridge,test_autostart}.py
```

---

## Task 1: 脚手架 + 迁移 widgets_host → manager(纯搬运,行为不变)

**Files:**
- Create: `requirements.txt`, `src/manager/__init__.py`, `src/manager/{app,registry,config_store,bridge→layout_bridge,tray,single_instance,x11}.py`, `main.py`
- Create: `widgets/Clock/{widget.json,Clock.qml}`
- Create: `tests/{test_config_store,test_registry}.py`, `tests/conftest.py`
- Source: 从 `~/Desktop/widgets` 拷贝同名文件

**Interfaces:**
- Produces: 包 `manager`(原 `widgets_host`);`manager.config_store.ConfigStore`、`manager.registry.WidgetRegistry`、`manager.layout_bridge.LayoutBridge`、`manager.app.WidgetHost`(本任务后仍叫 WidgetHost,Task 3 再拆)、`manager.single_instance.acquire`、`manager.x11.set_desktop_widget_states`。

- [ ] **Step 1: 拷贝并重命名包**

```bash
cd /home/coderyuan/Desktop/managewidgets
mkdir -p src/manager widgets/Clock tests
W=/home/coderyuan/Desktop/widgets
cp $W/requirements.txt requirements.txt
cp $W/src/widgets_host/__init__.py src/manager/__init__.py
cp $W/src/widgets_host/registry.py src/manager/registry.py
cp $W/src/widgets_host/config_store.py src/manager/config_store.py
cp $W/src/widgets_host/bridge.py src/manager/layout_bridge.py
cp $W/src/widgets_host/app.py src/manager/app.py
cp $W/src/widgets_host/tray.py src/manager/tray.py
cp $W/src/widgets_host/single_instance.py src/manager/single_instance.py
cp $W/src/widgets_host/x11.py src/manager/x11.py
cp $W/widgets/Clock/widget.json widgets/Clock/widget.json
cp $W/widgets/Clock/Clock.qml widgets/Clock/Clock.qml
cp $W/tests/test_config_store.py tests/test_config_store.py
cp $W/tests/test_registry.py tests/test_registry.py
```

- [ ] **Step 2: 修正 import**（`app.py` 内 `from .registry`/`.config_store` 已对；将 `from .bridge import LayoutBridge` 改为 `from .layout_bridge import LayoutBridge`）

在 `src/manager/app.py` 中：
```python
        from .layout_bridge import LayoutBridge
```
（替换原 `from .bridge import LayoutBridge`）

- [ ] **Step 3: 写 main.py**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from manager.single_instance import acquire  # noqa: E402
from manager.app import WidgetHost  # noqa: E402

if __name__ == "__main__":
    if not acquire():
        print("桌面小组件已在运行(单实例),不重复启动。", file=sys.stderr)
        sys.exit(0)
    sys.exit(WidgetHost().run())
```

- [ ] **Step 4: 测试可发现包 — 写 conftest.py**

`tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
```

测试文件里的 `from widgets_host.config_store import ConfigStore` 改成 `from manager.config_store import ConfigStore`；`from widgets_host.registry import WidgetRegistry` 改成 `from manager.registry import WidgetRegistry`。

- [ ] **Step 5: 跑现有测试,确认全绿**

Run: `cd /home/coderyuan/Desktop/managewidgets && python -m pytest tests/ -v`
Expected: PASS（test_config_store 5 项 + test_registry 4 项）

- [ ] **Step 6: 提交**

```bash
git add -A && git commit -m "feat: 迁移 widgets_host 运行时代码到 manager 包"
```

---

## Task 2: 扩展 Registry(category + implemented),建组件桩

**Files:**
- Modify: `src/manager/registry.py`
- Modify: `widgets/Clock/widget.json`
- Create: `widgets/{Weather,Calendar,System,Note,Launcher}/widget.json`
- Test: `tests/test_registry.py`

**Interfaces:**
- Produces: `WidgetRegistry.discover()` 返回的 dict 新增 `"category": str`(默认=id)、`"implemented": bool`(默认 True)。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_registry.py`）

```python
def test_category_and_implemented_defaults(tmp_path):
    d = tmp_path / "Clock"; d.mkdir()
    (d / "widget.json").write_text(json.dumps({"id": "clock", "name": "时钟"}))
    r = WidgetRegistry(tmp_path).discover()[0]
    assert r["category"] == "clock"      # 默认 = id
    assert r["implemented"] is True       # 默认 True


def test_category_and_implemented_explicit(tmp_path):
    d = tmp_path / "Weather"; d.mkdir()
    (d / "widget.json").write_text(json.dumps(
        {"id": "weather", "name": "天气", "category": "weather", "implemented": False}))
    r = WidgetRegistry(tmp_path).discover()[0]
    assert r["category"] == "weather"
    assert r["implemented"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_registry.py::test_category_and_implemented_defaults -v`
Expected: FAIL（KeyError: 'category'）

- [ ] **Step 3: 改 registry.py discover() 的 append 块**

```python
            found.append({
                "id": wid,
                "name": data.get("name", wid),
                "qml": str(sub / qml),
                "dir": str(sub),
                "default_size": data.get("defaultSize", [320, 210]),
                "category": data.get("category", wid),
                "implemented": bool(data.get("implemented", True)),
            })
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS（全部）

- [ ] **Step 5: 更新 Clock + 建 5 个桩**

`widgets/Clock/widget.json`:
```json
{"id": "clock", "name": "时钟", "qml": "Clock.qml", "category": "clock", "implemented": true, "defaultSize": [320, 210]}
```
建桩（每个目录一个 widget.json,无 qml）：
```bash
cd /home/coderyuan/Desktop/managewidgets
for spec in "Weather weather 天气" "Calendar calendar 日历" "System system 系统状态" "Note note 便签" "Launcher launcher 快捷启动"; do
  set -- $spec; mkdir -p "widgets/$1"
done
```
`widgets/Weather/widget.json`: `{"id":"weather","name":"天气","category":"weather","implemented":false}`
`widgets/Calendar/widget.json`: `{"id":"calendar","name":"日历","category":"calendar","implemented":false}`
`widgets/System/widget.json`: `{"id":"system","name":"系统状态","category":"system","implemented":false}`
`widgets/Note/widget.json`: `{"id":"note","name":"便签","category":"note","implemented":false}`
`widgets/Launcher/widget.json`: `{"id":"launcher","name":"快捷启动","category":"launcher","implemented":false}`

- [ ] **Step 6: 提交**

```bash
git add -A && git commit -m "feat(registry): 支持 category/implemented 字段 + 建 5 个组件桩"
```

---

## Task 3: 拆 WidgetHost → ManagerApp + WidgetRuntime(重构,行为不变)

**Files:**
- Create: `src/manager/runtime.py`
- Rewrite: `src/manager/app.py`
- Modify: `main.py`（入口改为 ManagerApp）

**Interfaces:**
- Produces:
  - `WidgetRuntime(app, widgets, config, layout_bridge)`;方法 `bootstrap(default_on:set)`、`is_shown(wid)->bool`、`show_widget(wid)`、`hide_widget(wid)`、`set_enabled(wid, enabled:bool)`。
  - `ManagerApp()`;`run()->int`;属性 `app, runtime, config, registry, widgets`;方法 `open_manager()`(Task 7 用)。
- Consumes: Task 1/2 的 registry、config、layout_bridge、x11、tray。

- [ ] **Step 1: 写 runtime.py**

```python
import sys
from pathlib import Path
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtQml import QQmlApplicationEngine


class WidgetRuntime:
    """管理桌面小组件卡片窗口:按 id 显示/隐藏,每卡片一个独立 QML engine。"""

    def __init__(self, app, widgets, config, layout_bridge):
        self.app = app
        self.widgets = widgets
        self.config = config
        self.bridge = layout_bridge
        self.engines = {}

    def bootstrap(self, default_on):
        for w in self.widgets:
            if not w.get("implemented", True):
                continue
            if self.config.is_enabled(w["id"], default=(w["id"] in default_on)):
                self.show_widget(w["id"])

    def _meta(self, wid):
        return next((w for w in self.widgets if w["id"] == wid), None)

    def is_shown(self, wid):
        return wid in self.engines

    def show_widget(self, wid):
        if wid in self.engines:
            return
        meta = self._meta(wid)
        if not meta or not meta.get("implemented", True):
            return
        eng = QQmlApplicationEngine()
        eng.rootContext().setContextProperty("layout", self.bridge)
        eng.load(QUrl.fromLocalFile(meta["qml"]))
        roots = eng.rootObjects()
        if not roots:
            return
        if self.app.platformName() == "xcb":
            self._apply_desktop_states(roots[0])
        self.engines[wid] = eng

    def hide_widget(self, wid):
        eng = self.engines.pop(wid, None)
        if eng:
            for obj in eng.rootObjects():
                obj.close()
            eng.deleteLater()

    def set_enabled(self, wid, enabled):
        self.config.set_enabled(wid, enabled)
        if enabled:
            self.show_widget(wid)
        else:
            self.hide_widget(wid)

    def _apply_desktop_states(self, window):
        def apply():
            try:
                from .x11 import set_desktop_widget_states
                set_desktop_widget_states(int(window.winId()))
            except Exception as exc:
                print(f"[x11] {exc}", file=sys.stderr)
        QTimer.singleShot(200, apply)
```

- [ ] **Step 2: 重写 app.py 为 ManagerApp**

```python
import sys
import signal
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ON = {"clock"}


class ManagerApp:
    def __init__(self):
        fmt = QSurfaceFormat.defaultFormat()
        fmt.setAlphaBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
        self.app = QApplication(sys.argv)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.app.setApplicationName("deepin-widgets")
        self.app.setQuitOnLastWindowClosed(False)

        from .registry import WidgetRegistry
        from .config_store import ConfigStore
        from .layout_bridge import LayoutBridge
        from .runtime import WidgetRuntime
        self.registry = WidgetRegistry(PROJECT_ROOT / "widgets")
        self.config = ConfigStore()
        self.layout_bridge = LayoutBridge(self.config)
        self.widgets = self.registry.discover()
        self.runtime = WidgetRuntime(self.app, self.widgets, self.config, self.layout_bridge)
        self.manager_engine = None   # Task 7 填充

    def run(self):
        self.runtime.bootstrap(DEFAULT_ON)
        from .tray import build_tray
        self.tray = build_tray(self)
        return self.app.exec()

    def open_manager(self):
        # Task 7 实现:创建/显示管理窗口
        pass
```

- [ ] **Step 3: 改 tray.py 适配新结构**

`tray.py` 里 `host.widgets` / `host.is_shown` / `host.set_widget_enabled` 改为运行时调用。把函数体内：
```python
    for w in host.widgets:
        act = QAction(w["name"], menu)
        act.setCheckable(True)
        act.setEnabled(w.get("implemented", True))
        act.setChecked(host.runtime.is_shown(w["id"]))
        act.toggled.connect((lambda wid: (lambda checked: host.runtime.set_enabled(wid, checked)))(w["id"]))
        menu.addAction(act)
        host._toggle_actions[w["id"]] = act
```
并把"管理面板…（待设计）"项改为可用（Task 7 接 open_manager,本任务先连到 `host.open_manager`,暂时空操作）：
```python
    panel = QAction("打开管理面板", menu)
    panel.triggered.connect(host.open_manager)
    menu.addAction(panel)
```

- [ ] **Step 4: 改 main.py**

```python
from manager.app import ManagerApp  # noqa: E402
...
    sys.exit(ManagerApp().run())
```

- [ ] **Step 5: 跑既有测试 + 运行 App 验证**

Run: `python -m pytest tests/ -v` → Expected: PASS（逻辑测试不受影响）
Run: `python main.py`（真机）→ Expected: 桌面出现时钟卡片;托盘菜单有"时钟"勾选、其余 5 项灰显、"打开管理面板"、"退出";Ctrl-C 可退。截图存 `docs/design-specs/shots/task3-tray.png`。

- [ ] **Step 6: 提交**

```bash
git add -A && git commit -m "refactor: 拆 WidgetHost 为 ManagerApp + WidgetRuntime"
```

---

## Task 4: CatalogBridge — 分类与可见列表

**Files:**
- Create: `src/manager/catalog_bridge.py`
- Test: `tests/test_catalog_bridge.py`

**Interfaces:**
- Produces: `CatalogBridge(runtime, widgets)`(`widgets` = registry list)。
  - Signal `changed`。
  - `setCategory(key:str)`(Slot)、`activeCategory`(Property str, notify changed,默认 `"all"`)。
  - `categories`(Property QVariantList)= `[{"key","label"}]`,固定 6 项。
  - `visibleWidgets`(Property QVariantList)= 当前分类下 `[{"id","name","category","enabled","implemented","previewQml"}]`。
  - 纯逻辑助手 `_visible()`(返回上述 list,供测试)。
- Consumes: `WidgetRuntime.is_shown`。

- [ ] **Step 1: 写失败测试**

`tests/test_catalog_bridge.py`:
```python
from manager.catalog_bridge import CatalogBridge


class FakeRuntime:
    def __init__(self, shown=()):
        self._shown = set(shown)
        self.calls = []
    def is_shown(self, wid):
        return wid in self._shown
    def set_enabled(self, wid, on):
        self.calls.append((wid, on))
        if on: self._shown.add(wid)
        else: self._shown.discard(wid)


WIDGETS = [
    {"id": "clock", "name": "时钟", "category": "clock", "implemented": True, "qml": "/x/Clock.qml", "dir": "/x"},
    {"id": "weather", "name": "天气", "category": "weather", "implemented": False, "qml": "", "dir": "/y"},
    {"id": "launcher", "name": "快捷启动", "category": "launcher", "implemented": False, "qml": "", "dir": "/z"},
]


def test_default_category_all_shows_everything():
    b = CatalogBridge(FakeRuntime(shown=["clock"]), WIDGETS)
    ids = [w["id"] for w in b._visible()]
    assert ids == ["clock", "weather", "launcher"]


def test_category_filters():
    b = CatalogBridge(FakeRuntime(), WIDGETS)
    b.setCategory("weather")
    assert [w["id"] for w in b._visible()] == ["weather"]


def test_launcher_only_in_all():
    b = CatalogBridge(FakeRuntime(), WIDGETS)
    b.setCategory("clock")
    assert "launcher" not in [w["id"] for w in b._visible()]


def test_enabled_reflects_runtime():
    b = CatalogBridge(FakeRuntime(shown=["clock"]), WIDGETS)
    clock = next(w for w in b._visible() if w["id"] == "clock")
    assert clock["enabled"] is True


def test_categories_list():
    b = CatalogBridge(FakeRuntime(), WIDGETS)
    keys = [c["key"] for c in b.categories]
    assert keys == ["all", "clock", "weather", "calendar", "system", "note"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_catalog_bridge.py -v`
Expected: FAIL（ModuleNotFoundError: manager.catalog_bridge）

- [ ] **Step 3: 写 catalog_bridge.py**

```python
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, Property

_CATEGORIES = [
    {"key": "all", "label": "全部"},
    {"key": "clock", "label": "时钟"},
    {"key": "weather", "label": "天气"},
    {"key": "calendar", "label": "日历"},
    {"key": "system", "label": "系统"},
    {"key": "note", "label": "便签"},
]


class CatalogBridge(QObject):
    changed = Signal()

    def __init__(self, runtime, widgets):
        super().__init__()
        self._runtime = runtime
        self._widgets = widgets
        self._active = "all"

    def _preview_qml(self, w):
        if not w.get("implemented", True):
            return ""
        p = Path(w["dir"]) / "Preview.qml"
        return str(p) if p.is_file() else ""

    def _visible(self):
        out = []
        for w in self._widgets:
            if self._active == "all" or w["category"] == self._active:
                out.append({
                    "id": w["id"], "name": w["name"], "category": w["category"],
                    "enabled": self._runtime.is_shown(w["id"]),
                    "implemented": w.get("implemented", True),
                    "previewQml": self._preview_qml(w),
                })
        return out

    @Slot(str)
    def setCategory(self, key):
        if key != self._active:
            self._active = key
            self.changed.emit()

    def _get_active(self):
        return self._active

    activeCategory = Property(str, _get_active, notify=changed)
    categories = Property("QVariantList", lambda self: _CATEGORIES, constant=True)
    visibleWidgets = Property("QVariantList", lambda self: self._visible(), notify=changed)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_catalog_bridge.py -v`
Expected: PASS（5 项）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(catalog): CatalogBridge 分类筛选与可见列表"
```

---

## Task 5: CatalogBridge — toggle 开关

**Files:**
- Modify: `src/manager/catalog_bridge.py`
- Test: `tests/test_catalog_bridge.py`

**Interfaces:**
- Produces: `CatalogBridge.toggle(wid:str, on:bool)`(Slot)→ 调 `runtime.set_enabled` 并 emit changed。

- [ ] **Step 1: 写失败测试**（追加）

```python
def test_toggle_calls_runtime_and_updates():
    rt = FakeRuntime()
    b = CatalogBridge(rt, WIDGETS)
    b.toggle("clock", True)
    assert rt.calls == [("clock", True)]
    clock = next(w for w in b._visible() if w["id"] == "clock")
    assert clock["enabled"] is True


def test_toggle_off():
    rt = FakeRuntime(shown=["clock"])
    b = CatalogBridge(rt, WIDGETS)
    b.toggle("clock", False)
    assert rt.calls == [("clock", False)]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_catalog_bridge.py::test_toggle_calls_runtime_and_updates -v`
Expected: FAIL（AttributeError: toggle）

- [ ] **Step 3: 加 toggle**（在 setCategory 之后）

```python
    @Slot(str, bool)
    def toggle(self, wid, on):
        self._runtime.set_enabled(wid, on)
        self.changed.emit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_catalog_bridge.py -v`
Expected: PASS（7 项）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(catalog): toggle 开关组件"
```

---

## Task 6: 全局操作 + 开机自启

**Files:**
- Create: `src/manager/autostart.py`
- Modify: `src/manager/catalog_bridge.py`
- Test: `tests/test_autostart.py`

**Interfaces:**
- Produces:
  - `autostart.is_enabled(path=None)->bool`、`autostart.set_enabled(on:bool, exec_cmd:str, path=None)`。
  - `CatalogBridge.showAll()` / `hideAll()` / `quitApp()`(Slot);`autostartEnabled`(Property bool, notify changed)、`setAutostart(on:bool)`(Slot)。
- Consumes: 运行时 `set_enabled`;App `quit`(经构造注入 `quit_fn`)。

- [ ] **Step 1: 写 autostart 失败测试**

`tests/test_autostart.py`:
```python
from manager import autostart


def test_disabled_by_default(tmp_path):
    assert autostart.is_enabled(tmp_path / "a.desktop") is False


def test_enable_writes_desktop(tmp_path):
    p = tmp_path / "a.desktop"
    autostart.set_enabled(True, "python /opt/main.py", p)
    assert p.exists()
    assert autostart.is_enabled(p) is True
    assert "python /opt/main.py" in p.read_text()


def test_disable_removes(tmp_path):
    p = tmp_path / "a.desktop"
    autostart.set_enabled(True, "x", p)
    autostart.set_enabled(False, "x", p)
    assert autostart.is_enabled(p) is False
```

- [ ] **Step 2: 跑确认失败**

Run: `python -m pytest tests/test_autostart.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 autostart.py**

```python
from pathlib import Path

_DEFAULT = Path.home() / ".config" / "autostart" / "deepin-widgets.desktop"


def _path(path):
    return Path(path) if path else _DEFAULT


def is_enabled(path=None):
    return _path(path).is_file()


def set_enabled(on, exec_cmd, path=None):
    p = _path(path)
    if on:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=桌面小组件\n"
            f"Exec={exec_cmd}\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
    elif p.is_file():
        p.unlink()
```

- [ ] **Step 4: 跑确认通过**

Run: `python -m pytest tests/test_autostart.py -v`
Expected: PASS（3 项）

- [ ] **Step 5: CatalogBridge 加全局操作（写测试）**

追加到 `tests/test_catalog_bridge.py`:
```python
def test_show_all_enables_implemented_only():
    rt = FakeRuntime()
    b = CatalogBridge(rt, WIDGETS)
    b.showAll()
    assert ("clock", True) in rt.calls
    assert all(wid != "weather" for wid, _ in rt.calls)   # 未实现不开


def test_hide_all_disables_shown():
    rt = FakeRuntime(shown=["clock"])
    b = CatalogBridge(rt, WIDGETS)
    b.hideAll()
    assert ("clock", False) in rt.calls
```

- [ ] **Step 6: 跑确认失败 → 实现 → 通过**

Run: `python -m pytest tests/test_catalog_bridge.py::test_show_all_enables_implemented_only -v` → FAIL

在 `CatalogBridge.__init__` 增加可选 `quit_fn=None` 参数并保存；加方法：
```python
    @Slot()
    def showAll(self):
        for w in self._widgets:
            if w.get("implemented", True):
                self._runtime.set_enabled(w["id"], True)
        self.changed.emit()

    @Slot()
    def hideAll(self):
        for w in self._widgets:
            if self._runtime.is_shown(w["id"]):
                self._runtime.set_enabled(w["id"], False)
        self.changed.emit()

    @Slot()
    def quitApp(self):
        if self._quit_fn:
            self._quit_fn()

    @Slot(bool)
    def setAutostart(self, on):
        from . import autostart
        import sys
        from pathlib import Path
        main = Path(__file__).resolve().parents[2] / "main.py"
        autostart.set_enabled(on, f"{sys.executable} {main}")
        self.changed.emit()

    def _get_autostart(self):
        from . import autostart
        return autostart.is_enabled()

    autostartEnabled = Property(bool, _get_autostart, notify=changed)
```
`__init__` 签名改为 `def __init__(self, runtime, widgets, quit_fn=None):` 并 `self._quit_fn = quit_fn`。更新 Task4/5 测试构造（无需 quit_fn,默认 None 即可,已兼容)。

Run: `python -m pytest tests/test_catalog_bridge.py tests/test_autostart.py -v` → Expected: PASS（全部）

- [ ] **Step 7: 提交**

```bash
git add -A && git commit -m "feat(catalog): 全局显隐/退出/开机自启"
```

---

## Task 7: 管理窗口外壳 Manager.qml + 接入 App + 托盘唤起

**Files:**
- Create: `ui/Manager.qml`
- Create: `tools/preview_manager.py`（截图用,注入假 bridge）
- Modify: `src/manager/app.py`（open_manager 创建窗口、注入 catalog bridge）

**Interfaces:**
- Consumes: `CatalogBridge`(context property `catalog`)。
- Produces: 920×624 无边框圆角主窗,可拖动;App `open_manager()` 显示/raise。

- [ ] **Step 1: 写 Manager.qml(外壳:背景渐变 + 白卡 + 占位三区)**

`ui/Manager.qml`:
```qml
import QtQuick
import QtQuick.Window

Window {
    id: win
    width: 1000; height: 704            // 含外层 40 边距;主卡 920×624 居中
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.Window
    title: "桌面小组件"

    Rectangle {                          // 外层淡蓝渐变背景
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: "#cfe0fb" }
            GradientStop { position: 0.38; color: "#e4eefe" }
            GradientStop { position: 1.0; color: "#f4f8ff" }
        }

        Rectangle {                      // 主卡(窗口)
            id: card
            width: 920; height: 624
            anchors.centerIn: parent
            color: "#ffffff"
            radius: 18
            // 阴影 Task 13 用 MultiEffect 补;先保证布局

            Column {
                anchors.fill: parent
                Rectangle { id: titleArea; width: parent.width; height: 56; color: "transparent"
                    Text { anchors.centerIn: parent; text: "标题栏占位"; color: "#aaa" } }
                Row {
                    width: parent.width; height: parent.height - 56
                    Rectangle { id: sideArea; width: 186; height: parent.height; color: "#fff"
                        Text { anchors.centerIn: parent; text: "侧栏"; color: "#aaa" } }
                    Rectangle { id: contentArea; width: parent.width - 186; height: parent.height; color: "#fbfcfe"
                        Text { anchors.centerIn: parent; text: "内容区"; color: "#aaa" } }
                }
            }

            DragHandler {                // 整卡可拖(标题栏区 Task 8 收窄)
                target: null
                onActiveChanged: if (active) win.startSystemMove()
            }
        }
    }
}
```

- [ ] **Step 2: app.py 实现 open_manager + 注入 bridge**

在 `ManagerApp.__init__` 末尾(创建 runtime 后):
```python
        from .catalog_bridge import CatalogBridge
        self.catalog = CatalogBridge(self.runtime, self.widgets, quit_fn=self.app.quit)
```
实现 `open_manager`:
```python
    def open_manager(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        if self.manager_engine is None:
            eng = QQmlApplicationEngine()
            eng.rootContext().setContextProperty("catalog", self.catalog)
            eng.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "Manager.qml")))
            if not eng.rootObjects():
                return
            self.manager_engine = eng
        win = self.manager_engine.rootObjects()[0]
        win.show(); win.raise_(); win.requestActivate()
```

- [ ] **Step 3: 写 tools/preview_manager.py(截图/视觉迭代用)**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtCore import QUrl, QObject, Signal, Property, Slot

ROOT = Path(__file__).resolve().parents[1]
FAKE = [
    {"id":"clock","name":"时钟","category":"clock","enabled":True,"implemented":True,
     "previewQml":str(ROOT/"widgets/Clock/Preview.qml")},
    {"id":"weather","name":"天气","category":"weather","enabled":False,"implemented":False,"previewQml":""},
    {"id":"calendar","name":"日历","category":"calendar","enabled":False,"implemented":False,"previewQml":""},
    {"id":"system","name":"系统状态","category":"system","enabled":False,"implemented":False,"previewQml":""},
    {"id":"note","name":"便签","category":"note","enabled":False,"implemented":False,"previewQml":""},
    {"id":"launcher","name":"快捷启动","category":"launcher","enabled":False,"implemented":False,"previewQml":""},
]
CATS = [{"key":k,"label":l} for k,l in
        [("all","全部"),("clock","时钟"),("weather","天气"),("calendar","日历"),("system","系统"),("note","便签")]]

class MockCatalog(QObject):
    changed = Signal()
    def __init__(self): super().__init__(); self._a="all"
    @Slot(str)
    def setCategory(self,k): self._a=k; self.changed.emit()
    @Slot(str,bool)
    def toggle(self,i,o): self.changed.emit()
    @Slot()
    def showAll(self): pass
    @Slot()
    def hideAll(self): pass
    @Slot()
    def quitApp(self): pass
    @Slot(bool)
    def setAutostart(self,o): pass
    def _vis(self):
        return [w for w in FAKE if self._a=="all" or w["category"]==self._a]
    activeCategory = Property(str, lambda s: s._a, notify=changed)
    categories = Property("QVariantList", lambda s: CATS, constant=True)
    visibleWidgets = Property("QVariantList", lambda s: s._vis(), notify=changed)
    autostartEnabled = Property(bool, lambda s: False, notify=changed)

if __name__ == "__main__":
    fmt = QSurfaceFormat.defaultFormat(); fmt.setAlphaBufferSize(8); QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv)
    from PySide6.QtQml import QQmlApplicationEngine
    eng = QQmlApplicationEngine()
    eng.rootContext().setContextProperty("catalog", MockCatalog())
    eng.load(QUrl.fromLocalFile(str(ROOT/"ui"/"Manager.qml")))
    sys.exit(app.exec())
```

- [ ] **Step 4: 运行验证**

Run: `python tools/preview_manager.py`（真机）
Expected: 出现 1000×704 透明窗,中央 920×624 白色圆角卡,顶部标题栏占位/左侧栏/右内容区三块,可拖动。截图 `docs/design-specs/shots/task7-shell.png`。
Run: `python main.py` 后点托盘"打开管理面板" → 同样出现。

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(ui): 管理窗口外壳 + 托盘唤起 + 预览工具"
```

---

## Task 8: TitleBar.qml(标题栏)

**Files:**
- Create: `ui/TitleBar.qml`
- Modify: `ui/Manager.qml`（替换标题栏占位 + 拖动只限标题栏）

**Interfaces:**
- Produces: `TitleBar { signal minimizeClicked(); signal closeClicked() }`,高 56。

- [ ] **Step 1: 写 TitleBar.qml**

```qml
import QtQuick

Rectangle {
    id: bar
    height: 56
    color: "transparent"
    signal minimizeClicked()
    signal closeClicked()

    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#f1f3f7" }

    Row {
        anchors.left: parent.left; anchors.leftMargin: 20
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11
        Rectangle {
            width: 26; height: 26; radius: 8
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0; color: "#5b9bff" }
                GradientStop { position: 1; color: "#3b76f6" } }
            anchors.verticalCenter: parent.verticalCenter
            Grid {                      // 4 格白点 logo
                anchors.centerIn: parent; columns: 2; spacing: 2.5
                Repeater { model: 4
                    Rectangle { width: 6; height: 6; radius: 1.8; color: "#fff"
                        opacity: (index === 0 || index === 3) ? 1.0 : 0.8 } }
            }
        }
        Text { text: "桌面小组件"; color: "#2b3344"; font.pixelSize: 15
            font.weight: Font.DemiBold; font.letterSpacing: 0.2
            anchors.verticalCenter: parent.verticalCenter }
    }

    Row {
        anchors.right: parent.right; anchors.rightMargin: 18
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        component WinBtn: Rectangle {
            width: 30; height: 30; radius: 8; color: "transparent"
            property color hoverBg: "#f2f4f8"
            property color iconColor: "#9aa4b4"
            property alias ha: ha
            HoverHandler { id: ha }
            Behavior on color { ColorAnimation { duration: 120 } }
            color: ha.hovered ? hoverBg : "transparent"
        }
        WinBtn { id: minBtn
            Canvas { anchors.centerIn: parent; width: 15; height: 15
                onPaint: { var c=getContext("2d"); c.strokeStyle=minBtn.iconColor; c.lineWidth=2; c.lineCap="round"
                    c.beginPath(); c.moveTo(3,7.5); c.lineTo(12,7.5); c.stroke() } }
            TapHandler { onTapped: bar.minimizeClicked() } }
        WinBtn { id: closeBtn; hoverBg: "#ffeceb"
            property color xColor: ha.hovered ? "#ef4444" : "#9aa4b4"
            Canvas { anchors.centerIn: parent; width: 14; height: 14
                property color cc: closeBtn.xColor
                onCcChanged: requestPaint()
                onPaint: { var c=getContext("2d"); c.strokeStyle=cc; c.lineWidth=2; c.lineCap="round"
                    c.beginPath(); c.moveTo(3,3); c.lineTo(11,11); c.moveTo(11,3); c.lineTo(3,11); c.stroke() } }
            TapHandler { onTapped: bar.closeClicked() } }
    }
}
```

- [ ] **Step 2: Manager.qml 用 TitleBar 替换占位 + 拖动限定**

把 `titleArea` 那段 Rectangle 替换为：
```qml
                TitleBar {
                    id: titleBar
                    width: parent.width
                    onMinimizeClicked: win.hide()
                    onCloseClicked: win.hide()
                    DragHandler { target: null; onActiveChanged: if (active) win.startSystemMove() }
                }
```
并删除 card 上那个整卡 DragHandler。

- [ ] **Step 3: 运行验证**

Run: `python tools/preview_manager.py`
Expected: 标题栏左侧蓝色 4 格 logo + "桌面小组件";右侧最小化/关闭按钮,hover 变底色(关闭 hover 红);拖标题栏移窗;点最小化/关闭隐藏窗口。截图 `docs/design-specs/shots/task8-titlebar.png` 与原型标题栏比对。

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat(ui): 自绘标题栏(logo/标题/最小化/关闭/拖动)"
```

---

## Task 9: Sidebar.qml + NavItem.qml(侧栏分类)

**Files:**
- Create: `ui/NavItem.qml`, `ui/Sidebar.qml`
- Modify: `ui/Manager.qml`（替换侧栏占位）

**Interfaces:**
- Consumes: `catalog.categories`、`catalog.activeCategory`、`catalog.setCategory`。
- Produces: `Sidebar`(宽 186);内部 `NavItem { property string label; property bool active; property string iconKey; signal clicked() }`。

- [ ] **Step 1: 写 NavItem.qml**

```qml
import QtQuick

Rectangle {
    id: item
    height: 36
    radius: 11
    property string label: ""
    property bool active: false
    property bool muted: false        // 底部"设置"用
    signal clicked()
    HoverHandler { id: hh }
    color: active ? "#e9f1fe"
         : (hh.hovered ? "#f4f6fa" : "transparent")
    Behavior on color { ColorAnimation { duration: 120 } }

    Row {
        anchors.left: parent.left; anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11
        Rectangle { width: 17; height: 17; radius: 4; anchors.verticalCenter: parent.verticalCenter
            color: "transparent"; border.width: 1.8
            border.color: item.active ? "#2563eb" : (item.muted ? "#8a93a3" : "#5b6472") }  // 图标占位:Task 13 换真 SVG
        Text { text: item.label; anchors.verticalCenter: parent.verticalCenter
            font.pixelSize: 13.5; font.weight: Font.Medium
            color: item.active ? "#2563eb" : (item.muted ? "#8a93a3" : "#5b6472") }
    }
    TapHandler { onTapped: item.clicked() }
}
```

- [ ] **Step 2: 写 Sidebar.qml**

```qml
import QtQuick

Rectangle {
    id: side
    width: 186
    color: "#ffffff"
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: "#f1f3f7" }

    Column {
        anchors.fill: parent
        anchors.margins: 12
        anchors.topMargin: 14
        spacing: 3

        Repeater {
            model: catalog.categories
            NavItem {
                width: parent.width
                label: modelData.label
                active: catalog.activeCategory === modelData.key
                onClicked: catalog.setCategory(modelData.key)
            }
        }
        Item { width: 1; height: 1
            // 撑开:用一个 spacer,Column 无 flex,改用底部锚定见下
        }
    }
    NavItem {                            // 底部"设置"
        label: "设置"; muted: true
        width: parent.width - 24
        anchors.left: parent.left; anchors.leftMargin: 12
        anchors.bottom: parent.bottom; anchors.bottomMargin: 14
        onClicked: catalog.setCategory("settings")
    }
}
```

- [ ] **Step 3: Manager.qml 替换侧栏占位**

把 `sideArea` Rectangle 替换为 `Sidebar { id: sideArea; height: parent.height }`。

- [ ] **Step 4: 运行验证**

Run: `python tools/preview_manager.py`
Expected: 左栏 6 个分类项,"全部"高亮(蓝底蓝字);点击切换高亮 + 内容区(下任务后)过滤;底部"设置"项灰色 hover 变底。截图 `task9-sidebar.png` 比对原型。

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(ui): 侧栏分类导航"
```

---

## Task 10: GalleryCard.qml(画廊卡:头部 + 开关 + 占位/预览槽)

**Files:**
- Create: `ui/GalleryCard.qml`

**Interfaces:**
- Consumes: `catalog.toggle`。
- Produces: `GalleryCard { property string wid; property string title; property bool enabled; property bool implemented; property string previewQml }`,固定高度 168(两行网格匀称),内部 `default property alias` 不需要。

- [ ] **Step 1: 写 GalleryCard.qml**

```qml
import QtQuick
import QtQuick.Effects

Rectangle {
    id: cardRoot
    property string wid: ""
    property string title: ""
    property bool enabled: false
    property bool implemented: true
    property string previewQml: ""

    radius: 14
    color: "#ffffff"
    border.width: 1; border.color: "#eef1f6"
    opacity: implemented ? 1.0 : 0.6
    HoverHandler { id: hover; enabled: cardRoot.implemented }

    layer.enabled: true
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: hover.hovered ? Qt.rgba(40/255,78/255,160/255,0.10) : Qt.rgba(20/255,40/255,90/255,0.04)
        shadowVerticalOffset: hover.hovered ? 6 : 1
        shadowBlur: hover.hovered ? 0.5 : 0.15
    }

    Column {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Row {                            // 头部:名称 + 开关
            width: parent.width
            Text { text: cardRoot.title; color: "#8a93a3"; font.pixelSize: 13; font.weight: Font.DemiBold }
            Item { width: parent.width - implicitWidth; height: 1 }   // spacer 占位见下
        }
        // 真实头部用下方 Item 锚定布局
    }

    // 头部(锚定版,替代上面 Column 内 Row 的 spacer 难题)
    Text { id: nameText
        text: cardRoot.title; color: "#8a93a3"; font.pixelSize: 13; font.weight: Font.DemiBold
        anchors.left: parent.left; anchors.leftMargin: 17
        anchors.top: parent.top; anchors.topMargin: 15 }

    Item {                               // 开关图标 20×20
        width: 20; height: 20
        anchors.right: parent.right; anchors.rightMargin: 17
        anchors.top: parent.top; anchors.topMargin: 15
        visible: cardRoot.implemented
        Rectangle { anchors.fill: parent; radius: 10
            color: cardRoot.enabled ? "#3b82f6" : "transparent"
            border.width: cardRoot.enabled ? 0 : 1.6
            border.color: "#ced6e2" }
        Canvas { anchors.fill: parent; visible: cardRoot.enabled
            onPaint: { var c=getContext("2d"); c.strokeStyle="#fff"; c.lineWidth=2.2; c.lineCap="round"; c.lineJoin="round"
                c.beginPath(); c.moveTo(5.8,10.3); c.lineTo(8.6,13.0); c.lineTo(14.2,7.5); c.stroke() } }
        TapHandler { onTapped: catalog.toggle(cardRoot.wid, !cardRoot.enabled) }
    }

    Loader {                             // 预览/占位槽,Task 11/12 填充
        id: bodyLoader
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: parent.top; anchors.topMargin: 44
        anchors.bottom: parent.bottom
        anchors.leftMargin: 17; anchors.rightMargin: 17; anchors.bottomMargin: 15
    }

    Text {                               // "即将推出"占位
        anchors.centerIn: bodyLoader
        visible: !cardRoot.implemented
        text: "即将推出"; color: "#aab2c0"; font.pixelSize: 13
    }
}
```
> 注:上方 Column 块是误留的草稿,实现时删掉那个 Column,只保留锚定版头部 + Loader + 占位。最终 GalleryCard 只含:背景 Rectangle + nameText + 开关 Item + bodyLoader + 占位 Text。

- [ ] **Step 2: 运行验证(临时塞两张卡到 Manager 内容区)**

临时在 Manager.qml contentArea 放：
```qml
GalleryCard { wid:"clock"; title:"时钟"; enabled:true; implemented:true; width:380; height:168 }
```
Run: `python tools/preview_manager.py`
Expected: 一张白卡,左上"时钟",右上蓝色实心圆+白勾(enabled);点开关勾变环;hover 升投影。改 `implemented:false` → 整卡淡、中央"即将推出"、无开关。截图 `task10-card.png`。

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat(ui): 画廊卡(头部/开关/投影/即将推出占位)"
```

---

## Task 11: 内容区网格 + 接 visibleWidgets + 时钟实时预览

**Files:**
- Modify: `ui/Manager.qml`（contentArea 用 Flow/Grid + Repeater）
- Create: `widgets/Clock/Preview.qml`（浅色实时时钟预览,复刻原型)

**Interfaces:**
- Consumes: `catalog.visibleWidgets`(每项 id/name/category/enabled/implemented/previewQml)。

- [ ] **Step 1: 写 Clock/Preview.qml(复刻原型浅色时钟预览)**

```qml
import QtQuick

Item {
    id: pv
    Column {
        anchors.left: parent.left
        anchors.top: parent.top
        spacing: 12
        Text { id: t; color: "#222c43"; font.pixelSize: 46; font.weight: Font.Bold
            font.letterSpacing: 1; text: "00:00" }
        Text { id: dl; color: "#9aa4b4"; font.pixelSize: 13; text: "" }
    }
    Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: {
            var d = new Date()
            var wk = ["日","一","二","三","四","五","六"]
            t.text = Qt.formatTime(d, "hh:mm")
            dl.text = (d.getMonth()+1) + "月" + d.getDate() + "日 星期" + wk[d.getDay()]
        }
    }
}
```

- [ ] **Step 2: Manager.qml contentArea 用网格 + Repeater**

把 `contentArea` Rectangle 内容替换为：
```qml
    Rectangle {
        id: contentArea
        width: parent.width - 186; height: parent.height; color: "#fbfcfe"
        Flow {
            anchors.fill: parent
            anchors.margins: 18
            anchors.leftMargin: 20; anchors.rightMargin: 20
            spacing: 14
            Repeater {
                model: catalog.visibleWidgets
                GalleryCard {
                    width: (contentArea.width - 40 - 14) / 2     // 两列
                    height: 168
                    wid: modelData.id
                    title: modelData.name
                    enabled: modelData.enabled
                    implemented: modelData.implemented
                    previewQml: modelData.previewQml
                    Component.onCompleted: if (previewQml !== "") bodyLoader.source = previewQml
                }
            }
        }
    }
```
> 删除 Task 10 临时塞的那张卡。GalleryCard 的 `bodyLoader` 需暴露:在 GalleryCard 顶部加 `property alias bodyLoaderItem: bodyLoader`,或直接在 GalleryCard 内 `Loader.source` 绑定 `previewQml`(更简洁):把 Loader 改为 `source: cardRoot.implemented && cardRoot.previewQml ? cardRoot.previewQml : ""`,删掉本步的 `Component.onCompleted` 行。

- [ ] **Step 3: 运行验证**

Run: `python tools/preview_manager.py`
Expected: "全部"分类下两列 6 张卡:时钟卡显示实时 `HH:MM` + 日期(浅色,复刻原型),其余 5 张淡显"即将推出";点侧栏"天气"→只剩天气卡;点"时钟"→只剩时钟卡。截图 `task11-grid.png` 与原型逐区比对。

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat(ui): 内容区两列网格 + 时钟实时预览 + 分类过滤"
```

---

## Task 12: 设置面板(全局)

**Files:**
- Create: `ui/SettingsPanel.qml`
- Modify: `ui/Manager.qml`（activeCategory==="settings" 时内容区显设置）

**Interfaces:**
- Consumes: `catalog.autostartEnabled`、`catalog.setAutostart`、`catalog.showAll`、`catalog.hideAll`、`catalog.quitApp`。

- [ ] **Step 1: 写 SettingsPanel.qml**

```qml
import QtQuick

Item {
    Column {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 16
        Text { text: "全局设置"; color: "#222c43"; font.pixelSize: 18; font.weight: Font.Bold }

        Row { spacing: 10
            Text { text: "开机自启"; color: "#5b6472"; font.pixelSize: 13.5; anchors.verticalCenter: parent.verticalCenter }
            Rectangle { width: 44; height: 24; radius: 12
                color: catalog.autostartEnabled ? "#3b82f6" : "#d8e0ec"
                anchors.verticalCenter: parent.verticalCenter
                Rectangle { width: 18; height: 18; radius: 9; color: "#fff"; y: 3
                    x: catalog.autostartEnabled ? 23 : 3
                    Behavior on x { NumberAnimation { duration: 140 } } }
                TapHandler { onTapped: catalog.setAutostart(!catalog.autostartEnabled) } }
        }

        Row { spacing: 12
            component Btn: Rectangle { width: 96; height: 34; radius: 10; color: "#eef1f6"
                property string label: ""; signal clicked()
                Text { anchors.centerIn: parent; text: parent.label; color: "#5b6472"; font.pixelSize: 13 }
                TapHandler { onTapped: parent.clicked() } }
            Btn { label: "全部显示"; onClicked: catalog.showAll() }
            Btn { label: "全部隐藏"; onClicked: catalog.hideAll() }
        }

        Rectangle { width: 96; height: 34; radius: 10; color: "#ffeceb"
            Text { anchors.centerIn: parent; text: "退出"; color: "#ef4444"; font.pixelSize: 13 }
            TapHandler { onTapped: catalog.quitApp() } }
    }
}
```

- [ ] **Step 2: Manager.qml 内容区按分类切换**

在 contentArea 内,Flow 外层包条件：
```qml
        Loader {
            anchors.fill: parent; anchors.margins: 20
            active: catalog.activeCategory === "settings"
            visible: active
            source: "SettingsPanel.qml"
        }
        Flow {
            visible: catalog.activeCategory !== "settings"
            // ...原网格...
        }
```

- [ ] **Step 3: 运行验证**

Run: `python main.py` 真机(设置项需真 bridge 才有自启效果)→ 点"打开管理面板" → 点侧栏"设置"
Expected: 内容区显"全局设置":开机自启开关(点切换并真的写/删 `~/.config/autostart/deepin-widgets.desktop`)、全部显示/隐藏(桌面卡片随之增减)、退出(整 App 退)。截图 `task12-settings.png`。

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat(ui): 全局设置面板(自启/全部显隐/退出)"
```

---

## Task 13: 保真打磨(阴影/图标/字体 + 与原型逐区比对)

**Files:**
- Modify: `ui/{Manager,TitleBar,NavItem,GalleryCard}.qml`

**Interfaces:** 无新接口。按 UI 规格 Drift Register 收敛视觉差。

- [ ] **Step 1: 主卡阴影**

Manager.qml 给 `card` 加 MultiEffect 投影:`shadowColor: Qt.rgba(40/255,78/255,160/255,0.22); shadowBlur: 1.0; shadowVerticalOffset: 24`(近似规格 `0 24 70`)。

- [ ] **Step 2: 侧栏图标换真 SVG**

把 NavItem 的占位 Rectangle 图标换成各分类的 SVG(用 `Image { source: "data:image/svg+xml;utf8,..." }` 或 `Shape`)。SVG 路径取自 `_unpacked/_template.html` 第 45/49/53/57/61/65 行(全部/时钟/天气/日历/系统/便签),`stroke=currentColor` 改为绑定 NavItem 文字色。

- [ ] **Step 3: 字体**

Manager.qml 根上设 `font.family`(全局):用 `Text { font.family: "Noto Sans CJK SC" }` 的统一 FontLoader 或在每个 Text 设族。优先 `"PingFang SC","Microsoft YaHei","Noto Sans CJK SC"`。

- [ ] **Step 4: 逐区截图比对**

Run: `python tools/preview_manager.py` → 截全窗 `docs/design-specs/shots/final.png`。
对照 `_unpacked/_template.html` 渲染(可 `xdg-open _unpacked/_template.html` 需 React,改为直接对照原 `桌面小组件管理器.html` 在浏览器打开的效果)逐区检查:标题栏、侧栏选中态、卡片间距/圆角/投影、开关、时钟预览字号。按 UI 规格 §Visual Drift 流程,每个差异记一行(区域/属性/目标值/实际/层级),逐层修。

- [ ] **Step 5: 全量测试 + 提交**

Run: `python -m pytest tests/ -v` → Expected: PASS（config_store 5 + registry 6 + catalog_bridge 9 + autostart 3）
```bash
git add -A && git commit -m "polish(ui): 阴影/SVG图标/字体 + 保真比对收敛"
```

---

## Self-Review(计划自查)

**Spec coverage:**
- UI 规格 Layout/Tokens → Task 7-13;TitleBar → 8;Sidebar/NavItem → 9;GalleryCard+开关 → 10;ContentGrid+实时预览 → 11;"即将推出"占位 → 10;设置面板 → 12;Motion(hover投影/太阳旋转/进度条)→ hover 投影在 10/13,太阳旋转/进度条属未实现组件(占位),不在 v1。
- 架构 §模块 → Task 1(迁移)/3(拆分)/4-6(CatalogBridge)/7(接入);registry category/implemented → Task 2;错误处理(QML 加载失败标记)→ **补充**:GalleryCard Loader `onStatusChanged` 若 `Loader.Error` 显示"加载失败"(在 Task 11 Step 2 的 Loader 上加 `onStatusChanged: if (status===Loader.Error) ...`,实现者补)。
- 测试策略 → config_store/registry/catalog_bridge/autostart 均有 TDD;QML 截图验证贯穿。

**Placeholder scan:** Task 10 Step 1 含一段明确标注的"误留草稿 Column",已在步内文字要求删除——实现者照锚定版构建。其余无 TODO/TBD。

**Type consistency:** `WidgetRuntime.set_enabled/is_shown/show_widget/hide_widget/bootstrap` 在 Task 3 定义,Task 4-6 的 FakeRuntime 与真运行时签名一致;`CatalogBridge` 的 `categories/visibleWidgets/activeCategory/setCategory/toggle/showAll/hideAll/quitApp/setAutostart/autostartEnabled` 在 Task 4-6 定义,QML(Task 9/11/12)按同名消费;`previewQml` 字段贯穿 bridge→GalleryCard 一致。
