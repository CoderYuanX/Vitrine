# 管理面板常驻系统托盘 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `manager` 面板改造成 QQ/微信式系统托盘常驻应用:Deepin dock 有图标、关窗最小化到托盘(首次询问并记住)、开机自启拉起托盘面板且登录即有数据、托盘反映底座连接状态并可启停底座/切自启/退出。

**Architecture:** 新增 `manager/settings.py`(面板本地偏好,纯逻辑可单测)与 `manager/tray.py`(`TrayIndicator` 封装 AyatanaAppIndicator3);`manager/app.py` 做集成(生命周期 hold/quit、关窗决策+首次对话框、单实例守卫、自启改 `-m manager`、启动宽限期后自动拉起 core、状态同步给托盘)。core 侧不改。

**Tech Stack:** Python 3.12;GTK 3.0 + **AyatanaAppIndicator3 0.1**(系统包,走 StatusNotifier 协议);`tomllib`(读)+`tomli-w`(写)做面板偏好。不新增任何 pip 依赖。

## Global Constraints

逐条来自 spec(`docs/superpowers/specs/2026-06-23-tray-resident-manager-design.md`),每个 task 隐含遵守:

- **托盘用 `AyatanaAppIndicator3` 0.1**;**缺库时优雅降级**:无托盘、**不 `hold()`**、关窗一律按退出。
- **面板偏好 `close_to_tray` 存 `~/.config/managewidgets/manager.toml`**,与 core 的 `config.toml` **分开**(避免两进程抢写)。缺文件/损坏/无该键 → `None`(=未决定,关窗要问)。
- **关窗(× / delete-event)**:`decide_close(pref)`:`True→"tray"`、`False→"quit"`、`None→"ask"`。`"ask"` 且有托盘 → 弹首次对话框「最小化到托盘 / 退出」+「记住我的选择」,**默认推荐按钮=最小化到托盘**;记住则存盘。无托盘时 `"ask"`/`"tray"` 一律退出。
- **退出只退面板,core 底座保持运行**(解耦)。
- **自启 `.desktop` 文件名沿用 `managewidgets-core.desktop`,仅 `Exec` 改为 `{sys.executable} -m manager`**。
- **启动不做一次性 connect**:`CoreClient` 自带指数退避;另设 **~2s 宽限期**,到期仍 `not is_connected()` 才 `_start_core()`。`_start_core` 就绪判定**以"runtime 的 `started_at` 变为新值"为准**(处理陈旧 runtime / 旧 token),不要只看文件存在。
- **所有来自 WS 客户端线程的 UI/托盘更新经 `GLib.idle_add` 切主线程**。
- 概览页自启开关 与 托盘自启项 操作同一 `enable/disable_autostart`,任一改动同步另一方(`handler_block` 防回环)。

---

### Task 1: 面板本地偏好 manager/settings.py

**Files:**
- Create: `manager/settings.py`
- Test: `tests/test_manager_settings.py`

**Interfaces:**
- Produces:
  - `settings_path() -> pathlib.Path`(`~/.config/managewidgets/manager.toml`)
  - `load_close_to_tray() -> bool | None`(不存在/损坏/无键 → `None`)
  - `save_close_to_tray(value: bool) -> None`(原子写,父目录自动建,仅写 `close_to_tray`)
  - `decide_close(pref: bool | None) -> str`(`True→"tray"`、`False→"quit"`、`None→"ask"`)
  - `autostart_exec_cmd() -> str`(`f"{sys.executable} -m manager"`)

- [ ] **Step 1: 写失败测试 `tests/test_manager_settings.py`**

```python
import sys

from manager.settings import (
    autostart_exec_cmd,
    decide_close,
    load_close_to_tray,
    save_close_to_tray,
    settings_path,
)


def test_decide_close_mapping():
    assert decide_close(True) == "tray"
    assert decide_close(False) == "quit"
    assert decide_close(None) == "ask"


def test_load_missing_returns_none(tmp_path, monkeypatch):
    target = tmp_path / "manager.toml"
    monkeypatch.setattr("manager.settings.settings_path", lambda: target)
    assert load_close_to_tray() is None


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "manager.toml"
    monkeypatch.setattr("manager.settings.settings_path", lambda: target)
    save_close_to_tray(True)
    assert target.exists()
    assert load_close_to_tray() is True
    save_close_to_tray(False)
    assert load_close_to_tray() is False


def test_corrupt_returns_none(tmp_path, monkeypatch):
    target = tmp_path / "manager.toml"
    target.write_text("this is not [ valid toml ===")
    monkeypatch.setattr("manager.settings.settings_path", lambda: target)
    assert load_close_to_tray() is None


def test_autostart_exec_cmd_targets_manager():
    cmd = autostart_exec_cmd()
    assert cmd == f"{sys.executable} -m manager"
    assert "-m manager" in cmd
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_manager_settings.py -v`
Expected: FAIL(`No module named 'manager.settings'`)

- [ ] **Step 3: 写 `manager/settings.py`**

```python
import os
import sys
import tempfile
from pathlib import Path

import tomllib
import tomli_w


def settings_path() -> Path:
    return Path.home() / ".config" / "managewidgets" / "manager.toml"


def load_close_to_tray() -> bool | None:
    path = settings_path()
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return None
    except (tomllib.TOMLDecodeError, OSError):
        return None
    val = data.get("close_to_tray")
    return val if isinstance(val, bool) else None


def save_close_to_tray(value: bool) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".manager.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(tomli_w.dumps({"close_to_tray": bool(value)}).encode("utf-8"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def decide_close(pref: bool | None) -> str:
    if pref is True:
        return "tray"
    if pref is False:
        return "quit"
    return "ask"


def autostart_exec_cmd() -> str:
    return f"{sys.executable} -m manager"
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_manager_settings.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: 提交**

```bash
git add manager/settings.py tests/test_manager_settings.py
git commit -m "feat(manager): 面板本地偏好(close_to_tray)+ decide_close + 自启 exec 串"
```

---

### Task 2: 托盘封装 manager/tray.py + 图标资源

**Files:**
- Create: `manager/tray.py`, `manager/assets/icons/hicolor/scalable/apps/managewidgets-connected.svg`, `manager/assets/icons/hicolor/scalable/apps/managewidgets-disconnected.svg`
- Modify: `pyproject.toml`(加 package-data 纳入 svg)
- Test: `tests/test_manager_tray.py`

**Interfaces:**
- Consumes: GTK 3.0、`AyatanaAppIndicator3` 0.1
- Produces:
  - `class TrayIndicator`:
    - `__init__(self, *, on_toggle_window, on_start_core, on_stop_core, on_set_autostart, on_quit, autostart_enabled=False)`
    - `set_connection(self, state: str, port: int | None = None) -> None`(`state ∈ {"connected","disconnected","error"}`;更新只读状态项文字 + 切图标;`port=None` 沿用上次端口)
    - `set_autostart_active(self, enabled: bool) -> None`(`handler_block` 同步勾选,不触发回调)
    - `refresh_window_item(self, visible: bool) -> None`(切「显示面板/隐藏面板」标签)

- [ ] **Step 1: 写图标资源(hicolor 结构,两个极简 SVG 圆点)**

先建目录:`mkdir -p manager/assets/icons/hicolor/scalable/apps`

`manager/assets/icons/hicolor/scalable/apps/managewidgets-connected.svg`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
  <circle cx="11" cy="11" r="7" fill="#2ecc71"/>
</svg>
```

`manager/assets/icons/hicolor/scalable/apps/managewidgets-disconnected.svg`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
  <circle cx="11" cy="11" r="7" fill="#95a5a6"/>
</svg>
```

- [ ] **Step 2: pyproject.toml 纳入 svg 资源**

在 `pyproject.toml` 末尾追加(确保安装时带上 assets;源码运行用 `__file__` 定位,不受此影响):
```toml
[tool.setuptools.package-data]
manager = ["assets/icons/hicolor/scalable/apps/*.svg"]
```

- [ ] **Step 3: 写冒烟测试 `tests/test_manager_tray.py`**

```python
import os

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3  # noqa: F401
    HAS_INDICATOR = True
except (ValueError, ImportError):
    HAS_INDICATOR = False

HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
pytestmark = pytest.mark.skipif(
    not (HAS_DISPLAY and HAS_INDICATOR), reason="需要图形显示与 AyatanaAppIndicator3")


def _tray(calls):
    from manager.tray import TrayIndicator
    return TrayIndicator(
        on_toggle_window=lambda: calls.append("toggle"),
        on_start_core=lambda: calls.append("start"),
        on_stop_core=lambda: calls.append("stop"),
        on_set_autostart=lambda e: calls.append(("autostart", e)),
        on_quit=lambda: calls.append("quit"),
        autostart_enabled=False,
    )


def test_tray_constructs_and_updates_without_feedback_loop():
    calls = []
    tray = _tray(calls)
    tray.set_connection("connected", 35355)        # 不抛
    tray.set_connection("disconnected")            # 沿用上次端口/切灰
    tray.set_connection("error")
    tray.refresh_window_item(True)
    tray.refresh_window_item(False)
    tray.set_autostart_active(True)                # 程序化同步:不得回环触发 on_set_autostart
    assert ("autostart", True) not in calls
    assert ("autostart", False) not in calls


def test_tray_menu_callbacks_fire():
    calls = []
    tray = _tray(calls)
    tray._item_window.emit("activate")
    tray._item_start.emit("activate")
    tray._item_stop.emit("activate")
    tray._item_quit.emit("activate")
    assert calls == ["toggle", "start", "stop", "quit"]
    tray._item_autostart.set_active(True)          # 用户手动切换(未阻塞)→ 触发回调
    assert ("autostart", True) in calls
```

- [ ] **Step 4: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_manager_tray.py -v`
Expected: FAIL(`No module named 'manager.tray'`)或 SKIP(无显示/无 AppIndicator);本机 `DISPLAY=:0` 且库已装,应 FAIL。

- [ ] **Step 5: 写 `manager/tray.py`**

```python
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk
from gi.repository import AyatanaAppIndicator3 as AppIndicator

_ICON_DIR = str(Path(__file__).resolve().parent / "assets" / "icons")
_ICON_CONNECTED = "managewidgets-connected"
_ICON_DISCONNECTED = "managewidgets-disconnected"


class TrayIndicator:
    """封装 AyatanaAppIndicator3:托盘图标 + 菜单 + 状态更新。业务逻辑全部经回调注入。"""

    def __init__(self, *, on_toggle_window, on_start_core, on_stop_core,
                 on_set_autostart, on_quit, autostart_enabled=False):
        self._on_set_autostart = on_set_autostart
        self._last_port = None

        # 用 icon theme path + 图标名(标准 GtkIconTheme 解析,跨 dock 比绝对路径稳)
        self._ind = AppIndicator.Indicator.new_with_path(
            "org.managewidgets.Manager",
            _ICON_DISCONNECTED,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
            _ICON_DIR,
        )
        self._ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._ind.set_title("小组件管理器")

        menu = Gtk.Menu()

        self._item_window = Gtk.MenuItem(label="显示面板")
        self._item_window.connect("activate", lambda *_: on_toggle_window())
        menu.append(self._item_window)

        menu.append(Gtk.SeparatorMenuItem())

        self._item_status = Gtk.MenuItem(label="未连接")
        self._item_status.set_sensitive(False)
        menu.append(self._item_status)

        self._item_start = Gtk.MenuItem(label="启动底座")
        self._item_start.connect("activate", lambda *_: on_start_core())
        menu.append(self._item_start)
        self._item_stop = Gtk.MenuItem(label="停止底座")
        self._item_stop.connect("activate", lambda *_: on_stop_core())
        menu.append(self._item_stop)

        self._item_autostart = Gtk.CheckMenuItem(label="开机自启")
        self._item_autostart.set_active(bool(autostart_enabled))
        self._autostart_handler = self._item_autostart.connect(
            "toggled", lambda w: self._on_set_autostart(w.get_active()))
        menu.append(self._item_autostart)

        menu.append(Gtk.SeparatorMenuItem())

        self._item_quit = Gtk.MenuItem(label="退出")
        self._item_quit.connect("activate", lambda *_: on_quit())
        menu.append(self._item_quit)

        menu.show_all()
        self._ind.set_menu(menu)
        self._menu = menu

    def set_connection(self, state, port=None):
        if port is not None:
            self._last_port = port
        if state == "connected":
            text = f"已连接 · 端口 {self._last_port}" if self._last_port else "已连接"
            self._item_status.set_label(text)
            self._ind.set_icon_full(_ICON_CONNECTED, "已连接")
        else:
            label = {"error": "鉴权失败"}.get(state, "未连接")
            self._item_status.set_label(label)
            self._ind.set_icon_full(_ICON_DISCONNECTED, label)

    def set_autostart_active(self, enabled):
        # 同步勾选状态;阻塞 toggled 信号,避免回写又触发 on_set_autostart
        self._item_autostart.handler_block(self._autostart_handler)
        self._item_autostart.set_active(bool(enabled))
        self._item_autostart.handler_unblock(self._autostart_handler)

    def refresh_window_item(self, visible):
        self._item_window.set_label("隐藏面板" if visible else "显示面板")
```

- [ ] **Step 6: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_manager_tray.py -v`
Expected: PASS(1 passed;无显示/无库环境 SKIP)

- [ ] **Step 7: 提交**

```bash
git add manager/tray.py manager/assets pyproject.toml tests/test_manager_tray.py
git commit -m "feat(manager): TrayIndicator(AyatanaAppIndicator3)+ 状态图标 + 托盘菜单"
```

---

### Task 3: app.py 集成 —— 托盘/关窗到托盘/自启面板/启动拉核/状态同步

**Files:**
- Modify: `manager/app.py`(整体重写)、`manager/pages/overview.py`(加 `set_autostart_active`)
- Test: `tests/test_manager_app_logic.py`(新增,纯逻辑:拉核/自启 exec/双向同步/无托盘关窗)、`tests/test_manager_smoke.py`(追加 overview 自启同步用例)

**Interfaces:**
- Consumes: Task 1 的 `settings`(`load_close_to_tray`/`save_close_to_tray`/`decide_close`/`autostart_exec_cmd`)、Task 2 的 `TrayIndicator`、既有 `CoreClient`/`discover`/`read_runtime`/`pid_is_core`/`core.autostart`
- Produces:
  - `manager/pages/overview.py`:`OverviewPage.set_autostart_active(self, enabled: bool) -> None`(`handler_block` 同步开关)
  - `manager/app.py`:`ManagerApp`(单实例守卫、托盘、关窗决策、自启 `-m manager`、启动宽限期拉核、状态同步)、`main()`

- [ ] **Step 1: 先写失败测试(overview 自启同步 + app 纯逻辑)**

(1) 追加到 `tests/test_manager_smoke.py` 末尾(验证概览自启同步不回环;无显示则随既有 `pytestmark` skip):
```python
def test_overview_autostart_sync_no_feedback_loop():
    from manager.pages.overview import OverviewPage
    calls = []
    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda e: calls.append(e))
    ov.set_autostart_active(True)
    assert ov._autostart.get_active() is True
    assert calls == []                        # 程序化同步未回环触发 on_autostart
```

(2) 新建 `tests/test_manager_app_logic.py`(纯逻辑:构造 `ManagerApp` 但**不** `run`/`do_activate`,手动塞桩件,不需图形界面,故不加 DISPLAY 门):
```python
import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402,F401

from manager.app import ManagerApp


def _app():
    return ManagerApp()                        # 仅构造 Gio.Application,不 run/activate


def test_maybe_autostart_core_only_when_disconnected():
    app = _app()
    started = []
    app._start_core = lambda: started.append(1)

    class _Client:
        def __init__(self, conn): self._c = conn
        def is_connected(self): return self._c

    app._client = _Client(True)
    app._maybe_autostart_core()
    assert started == []                       # 已连接 → 不拉核

    app._client = _Client(False)
    app._maybe_autostart_core()
    assert started == [1]                      # 未连接 → 拉核一次


def test_set_autostart_uses_manager_exec(monkeypatch):
    import core.autostart as autostart
    captured = []
    monkeypatch.setattr(autostart, "enable_autostart", lambda cmd: captured.append(cmd))
    monkeypatch.setattr(autostart, "disable_autostart", lambda: captured.append("disabled"))
    app = _app()
    app._set_autostart(True)
    assert captured and "-m manager" in captured[0]   # 自启的是面板而非 core
    app._set_autostart(False)
    assert captured[-1] == "disabled"


def test_autostart_cross_sync_no_loop():
    app = _app()
    set_calls, tray_calls, ov_calls = [], [], []
    app._set_autostart = lambda e: set_calls.append(e)
    app._tray = type("T", (), {"set_autostart_active": lambda self, e: tray_calls.append(e)})()
    app._overview = type("O", (), {"set_autostart_active": lambda self, e: ov_calls.append(e)})()

    app._on_overview_autostart(True)           # 概览触发 → 写自启 + 同步托盘(不反向调概览)
    assert set_calls == [True] and tray_calls == [True] and ov_calls == []

    app._on_tray_autostart(False)              # 托盘触发 → 写自启 + 同步概览(不反向调托盘)
    assert set_calls == [True, False] and ov_calls == [False] and tray_calls == [True]


def test_close_with_no_tray_quits(monkeypatch):
    import manager.app as appmod
    monkeypatch.setattr(appmod, "load_close_to_tray", lambda: None)   # 偏好未决定
    app = _app()
    app._tray = None
    quit_calls = []
    app._quit = lambda: quit_calls.append(1)
    assert app._on_close() is True             # 接管关窗事件返回 True
    assert quit_calls == [1]                   # 无托盘 → 直接退出(不隐藏、不 hold)
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_manager_smoke.py tests/test_manager_app_logic.py -q`
Expected: FAIL(`OverviewPage` 无 `set_autostart_active`;`ManagerApp` 缺 `_maybe_autostart_core`/`_set_autostart`/`_on_overview_autostart`/`_on_tray_autostart`/`_on_close` 等方法)

- [ ] **Step 3: 给 OverviewPage 加可同步的自启开关**

把 `manager/pages/overview.py` 里 autostart 开关那段(`self._autostart = Gtk.Switch()` 起的几行)替换为下面版本——存下 handler 并新增 `set_autostart_active`:

```python
        self._autostart = Gtk.Switch()
        from core.autostart import is_autostart_enabled
        self._autostart.set_active(is_autostart_enabled())
        self._autostart_handler = self._autostart.connect(
            "notify::active", lambda s, _p: on_autostart(s.get_active()))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.pack_start(Gtk.Label(label="开机自启", xalign=0), False, False, 0)
        row.pack_start(self._autostart, False, False, 0)
        self.pack_start(row, False, False, 0)
```

并在 `OverviewPage` 类内(任意方法后)新增:
```python
    def set_autostart_active(self, enabled):
        # 与托盘项联动:程序化同步,阻塞信号避免回环触发 on_autostart
        self._autostart.handler_block(self._autostart_handler)
        self._autostart.set_active(bool(enabled))
        self._autostart.handler_unblock(self._autostart_handler)
```

- [ ] **Step 4: 整体重写 `manager/app.py`**

```python
import os
import signal
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from core.config import default_config_path
from core.state import default_state_dir, pid_is_core, read_runtime
from manager.discovery import discover
from manager.pages.datasources import DataSourcesPage
from manager.pages.overview import OverviewPage
from manager.pages.widgets_placeholder import WidgetsPlaceholderPage
from manager.settings import (
    autostart_exec_cmd,
    decide_close,
    load_close_to_tray,
    save_close_to_tray,
)
from manager.ws_client import CoreClient


class ManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.managewidgets.Manager")
        self._client = None
        self._win = None
        self._tray = None
        self._held = False
        self._last_port = None

    # ---- 生命周期 ----
    def do_activate(self):
        if self._win is not None:                         # 单实例:再次激活只唤出(可能已最小化到托盘的)窗口
            self._win.show_all()
            self._win.present()
            if self._tray:
                self._tray.refresh_window_item(True)
            return
        win = Gtk.ApplicationWindow(application=self, title="小组件管理器")
        self._win = win
        win.set_default_size(560, 460)
        nb = Gtk.Notebook()
        self._overview = OverviewPage(on_start=self._start_core, on_stop=self._stop_core,
                                      on_autostart=self._on_overview_autostart)
        self._datasources = DataSourcesPage(on_set_provider=self._set_provider,
                                            on_set_interval=self._set_interval)
        nb.append_page(self._overview, Gtk.Label(label="概览"))
        nb.append_page(self._datasources, Gtk.Label(label="数据源"))
        nb.append_page(WidgetsPlaceholderPage(), Gtk.Label(label="小组件"))
        win.add(nb)
        win.connect("delete-event", self._on_close)       # 接管 ×,不直接销毁
        win.show_all()

        self._tray = self._build_tray()                   # 缺库 → None(降级)
        if self._tray is not None:
            self.hold()                                   # 仅有托盘时 hold,隐藏窗口不退出
            self._held = True

        self._connect_client()
        GLib.timeout_add(2000, self._maybe_autostart_core)  # 宽限期:~2s 未连上则拉核

    def _build_tray(self):
        try:
            from core.autostart import is_autostart_enabled
            from manager.tray import TrayIndicator
            return TrayIndicator(
                on_toggle_window=self._toggle_window,
                on_start_core=self._start_core,
                on_stop_core=self._stop_core,
                on_set_autostart=self._on_tray_autostart,
                on_quit=self._quit,
                autostart_enabled=is_autostart_enabled(),
            )
        except Exception as exc:                          # 缺 AyatanaAppIndicator3 等 → 降级
            print(f"[manager] 托盘不可用,降级为普通窗口: {exc}", file=sys.stderr)
            return None

    def _on_close(self, *args):
        action = decide_close(load_close_to_tray())
        if self._tray is None:                            # 无托盘:只能退出
            self._quit()
            return True
        if action == "tray":
            self._hide_window()
            return True
        if action == "quit":
            self._quit()
            return True
        return self._ask_close()                          # "ask"

    def _ask_close(self):
        dlg = Gtk.MessageDialog(transient_for=self._win, modal=True,
                                message_type=Gtk.MessageType.QUESTION, text="关闭窗口")
        dlg.format_secondary_text("最小化到托盘后台继续运行,还是直接退出?")
        dlg.add_button("最小化到托盘", Gtk.ResponseType.YES)
        dlg.add_button("退出", Gtk.ResponseType.NO)
        dlg.set_default_response(Gtk.ResponseType.YES)    # 默认推荐:最小化到托盘
        check = Gtk.CheckButton(label="记住我的选择")
        dlg.get_content_area().pack_start(check, False, False, 6)
        check.show()
        resp = dlg.run()
        remember = check.get_active()
        dlg.destroy()
        if resp == Gtk.ResponseType.YES:
            if remember:
                save_close_to_tray(True)
            self._hide_window()
        elif resp == Gtk.ResponseType.NO:
            if remember:
                save_close_to_tray(False)
            self._quit()
        # 其它(关掉对话框)→ 窗口保持,不动作
        return True

    def _hide_window(self):
        self._win.hide()
        if self._tray:
            self._tray.refresh_window_item(False)

    def _toggle_window(self):
        if self._win.get_visible():
            self._win.hide()
            visible = False
        else:
            self._win.show_all()
            self._win.present()
            visible = True
        if self._tray:
            self._tray.refresh_window_item(visible)

    def _quit(self):
        if self._held:
            self.release()
            self._held = False
        if self._client:
            self._client.stop()
        if self._win:
            self._win.destroy()
        self.quit()

    # ---- 连接 / 状态 ----
    def _runtime_path(self):
        return default_state_dir() / "core.json"

    def _connect_client(self):
        host, port, token = discover(self._runtime_path(), default_config_path())
        self._client = CoreClient(host, port, token,
                                  on_event=lambda m: GLib.idle_add(self._on_event, m),
                                  on_state=lambda s: GLib.idle_add(self._on_state, s))
        self._client.start()
        self._client.subscribe(["system.cpu", "system.mem", "time.now"])
        self._client.send({"id": "ls", "action": "list_providers"})

    def _on_state(self, state):
        self._overview.set_connection(state)
        if self._tray:
            self._tray.set_connection(state, self._last_port)
        return False

    def _on_event(self, msg):
        if msg.get("type") == "data":
            self._datasources.apply_data(msg["topic"], msg["data"])
        elif msg.get("type") == "status":
            self._last_port = msg["status"].get("core", {}).get("port")
            self._overview.update(msg["status"])
            self._datasources.update(msg["status"])
            if self._tray:
                self._tray.set_connection("connected", self._last_port)
        return False

    # ---- 启停底座 ----
    def _maybe_autostart_core(self):
        if not (self._client and self._client.is_connected()):
            self._start_core()
        return False

    def _start_core(self):
        if getattr(self, "_start_polls_active", False):
            return
        self._start_polls_active = True
        rt = read_runtime(self._runtime_path())
        self._prev_started_at = rt.get("started_at") if rt else None   # 记旧实例时间戳
        subprocess.Popen([sys.executable, "-m", "core"])
        self._start_polls = 0
        GLib.timeout_add(500, self._reconnect_when_ready)

    def _reconnect_when_ready(self):
        # 以"runtime 的 started_at 变成新值"为就绪判定:跳过陈旧 runtime,拿到新 token 再连
        self._start_polls += 1
        rt = read_runtime(self._runtime_path())
        if rt and rt.get("started_at") != self._prev_started_at:
            self._start_polls_active = False
            self._reconnect()
            return False
        if self._start_polls >= 20:                       # ~10s 仍无新实例 → 放弃
            self._start_polls_active = False
            return False
        return True

    def _reconnect(self):
        if self._client:
            self._client.stop()
        self._connect_client()

    def _stop_core(self):
        if self._client and self._client.is_connected():
            self._client.send({"action": "shutdown"})
            return
        rt = read_runtime(self._runtime_path())
        if rt and rt.get("pid") and pid_is_core(rt["pid"]):
            try:
                os.kill(rt["pid"], signal.SIGTERM)
            except OSError:
                pass

    # ---- provider/interval ----
    def _set_provider(self, pid, enabled):
        if self._client:
            self._client.send({"action": "set_provider", "provider": pid, "enabled": enabled})

    def _set_interval(self, topic, interval):
        if self._client:
            self._client.send({"action": "set_interval", "topic": topic, "interval": interval})

    # ---- 自启(改为自启面板 -m manager;概览与托盘联动)----
    def _set_autostart(self, enabled):
        from core.autostart import disable_autostart, enable_autostart
        if enabled:
            enable_autostart(autostart_exec_cmd())        # Exec=… -m manager
        else:
            disable_autostart()

    def _on_overview_autostart(self, enabled):
        self._set_autostart(enabled)
        if self._tray:
            self._tray.set_autostart_active(enabled)

    def _on_tray_autostart(self, enabled):
        self._set_autostart(enabled)
        self._overview.set_autostart_active(enabled)


def main(argv=None) -> int:
    app = ManagerApp()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行确认通过(冒烟 + 逻辑 + 全量回归)**

Run: `.venv/bin/python -m pytest tests/test_manager_app_logic.py tests/test_manager_smoke.py -v`
Expected: PASS(app 逻辑 5 例全过;冒烟含新 `test_overview_autostart_sync_no_feedback_loop`)
Run: `.venv/bin/python -m pytest -q`
Expected: PASS(全过;无显示环境下 GUI 冒烟/托盘用例 SKIP,app 逻辑用例不依赖显示照常跑)

- [ ] **Step 6: 真机 E2E 手动验证(需图形会话,逐项对照)**

```bash
.venv/bin/python -m manager        # 不必先起 core
```
- 不先起 core:面板启动后 ~2s 自动拉起底座 → 托盘出现图标、概览"已连接"、数据源跳动。
- 托盘右键菜单:显示/隐藏面板、启动/停止底座、开机自启、退出 均可用。
- 点 × → 首次弹框(默认聚焦"最小化到托盘")。选"最小化到托盘"+勾"记住" → 窗口隐藏、托盘仍在;点托盘"显示面板"唤回。
- 再点 × → 不再弹框,直接最小化(记住生效)。`cat ~/.config/managewidgets/manager.toml` 应见 `close_to_tray = true`。
- 停止底座 → 托盘图标转灰、状态项"未连接";启动底座 → 转绿"已连接 · 端口 35355"。
- 概览自启开关与托盘"开机自启"项联动;打开后 `cat ~/.config/autostart/managewidgets-core.desktop` 的 `Exec` 含 `-m manager`。
- 托盘"退出" → 面板退出;`pgrep -f "python -m core"` 显示底座仍在(退出只退面板)。随后 `kill -TERM <core pid>` 清理。

- [ ] **Step 7: 提交**

```bash
git add manager/app.py manager/pages/overview.py tests/test_manager_smoke.py tests/test_manager_app_logic.py
git commit -m "feat(manager): 托盘常驻集成(关窗到托盘/自启面板/启动拉核/状态同步/单实例)"
```

---

### Task 4: README 更新 + 全量回归

**Files:**
- Modify: `README.md`
- Test: 全量 `pytest`

**Interfaces:** 无新增接口。

- [ ] **Step 1: 改 `README.md`**

在「系统依赖」一节的 `apt install` 行追加 `gir1.2-ayatanaappindicator3-0.1`,并在文件中「测试」节后、「已知问题与修复记录」节前插入一节:

```markdown
## 托盘与常驻(系统托盘)

面板是常驻系统托盘应用(Deepin dock):

- **关窗行为**:首次点窗口 × 会询问「最小化到托盘 / 退出」,可勾"记住我的选择"
  (偏好存 `~/.config/managewidgets/manager.toml`,与 core 的 `config.toml` 分开)。
- **托盘菜单**:显示/隐藏面板、启动/停止底座、开机自启、退出。**退出只退面板,
  core 底座继续运行**(要停底座用菜单"停止底座")。图标随连接状态变绿/灰。
- **开机自启**:打开后登录即在托盘,并自动拉起底座、数据开始跳。自启的 `.desktop`
  **历史原因沿用文件名 `managewidgets-core.desktop`,实际自启的是 manager 面板
  (`Exec=… -m manager`)**。
- **缺托盘库时**:若系统未装 `gir1.2-ayatanaappindicator3-0.1`,面板仍可运行,
  只是没有托盘图标(降级为普通窗口,关窗即退出)。
```

并把「系统依赖」节改为:
```markdown
## 系统依赖(PyGObject 无法用 pip 装,需系统包)
    # Debian/Deepin 系:
    sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-ayatanaappindicator3-0.1
```

- [ ] **Step 2: 全量回归**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS(全过;无显示时托盘/冒烟用例 SKIP)

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs(readme): 系统托盘依赖 + 托盘/常驻/自启行为说明"
```

---

## 自检(写完计划后对照 spec)

- **覆盖**:面板偏好+decide_close+自启 exec(T1)、TrayIndicator+图标+package-data(T2)、app 集成(单实例/关窗到托盘+首次对话框+记住/自启改 `-m manager`+概览↔托盘联动/启动宽限期拉核+陈旧 runtime 鲁棒/状态同步给托盘/缺库降级不 hold)(T3)、README 系统依赖+命名说明+行为说明(T4)。spec 各节均有对应 task。
- **类型一致**:`TrayIndicator` 方法名贯穿一致——`set_connection(state, port)`、`set_autostart_active(enabled)`、`refresh_window_item(visible)`;`settings` 导出 `load_close_to_tray`/`save_close_to_tray`/`decide_close`/`autostart_exec_cmd`;`OverviewPage.set_autostart_active(enabled)`。app 对这些的调用签名一致。
- **降级/边界**:缺 AppIndicator → `_build_tray` 返回 None、不 `hold()`、`_on_close` 直接退出、`_quit` 不 `release`(`_held=False`);陈旧 runtime → `_reconnect_when_ready` 以 `started_at` 变化为就绪判定;退出只退面板不碰 core。
- **测试边界**:T1 纯单测;T3 的 `test_manager_app_logic.py` 用桩件覆盖纯决策(拉核仅在未连接、自启用 `-m manager`、自启双向同步不回环、无托盘关窗即退),不依赖显示;T2/T3 的 GUI/托盘冒烟在无显示或无 AppIndicator 时 SKIP;托盘是否真正出现在 dock、关窗对话框、点图标唤出、图标随状态变色 由 T3 Step6 人工 E2E 验收。
- **TDD 顺序**:每个 task 都先写测试并确认 RED,再实现到 GREEN(T3 已修正为 测试 → 改 OverviewPage/app → 通过)。
