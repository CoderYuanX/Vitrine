# 管理面板常驻系统托盘(tray-resident manager)设计

## 背景与目标

当前 `manager` 面板从终端启动、关窗即结束,体验上"像一个进程"而非常驻应用。
本特性把面板改造成 **QQ/微信式的系统托盘常驻应用**:

- Deepin 任务栏(dock)有一个常驻托盘图标;
- 关闭窗口默认最小化到托盘(进程不退),点托盘图标再唤出;
- 开机自启改为拉起托盘面板,登录后托盘即有图标、底座数据在跳;
- 托盘图标与菜单反映底座连接状态,并能直接启停底座、切自启、退出。

非目标(YAGNI,本期不做):多窗口/多实例、托盘消息气泡通知、tooltip 悬停提示
(AppIndicator 协议不可靠支持)、core 底座的托盘化(core 仍是无界面 daemon)。

## 技术选型

- 托盘用 **AyatanaAppIndicator3 0.1**(系统已装,走 Deepin dock 认的
  StatusNotifierItem 协议)。旧的 `Gtk.StatusIcon`(XEmbed)在 Deepin dock 常不
  显示,不用。不新增任何 pip 依赖。
- 若运行环境缺 `AyatanaAppIndicator3`:**优雅降级**——面板照常以普通窗口运行
  (无托盘),日志一条告警;此时关窗按"退出"处理(无托盘可最小化)。

## 架构总览:新增/改动文件

```
manager/
  settings.py        # 新增:面板本地偏好(close_to_tray)读写 + decide_close 纯函数
  tray.py            # 新增:TrayIndicator —— 封装 AyatanaAppIndicator3 + 菜单 + 状态更新
  app.py             # 改:生命周期(hold/quit)、delete-event+首次对话框、单实例守卫、
                     #     启动时自动拉起 core、自启改 -m manager、把状态同步给托盘
  assets/
    managewidgets-connected.svg     # 新增:已连接图标(极简)
    managewidgets-disconnected.svg  # 新增:未连接图标(极简)
tests/
  test_manager_settings.py  # 新增:settings 读写 + decide_close
  test_manager_tray.py      # 新增:TrayIndicator 冒烟(DISPLAY + AppIndicator 可用时)
  test_manager_smoke.py     # 改:补 app 关窗决策 / 自启 exec 串 的断言
```

`core/` 不改(`core/autostart.py` 已是通用 `enable_autostart(exec_cmd)`,只是 manager
传入的 exec 串改成 `-m manager`)。

## 组件详述

### 1. `manager/settings.py` —— 面板本地偏好

与 core 的 `~/.config/managewidgets/config.toml` **分开**,避免 core 与 manager 两个
进程并发抢写同一文件丢字段。

- `settings_path() -> Path` → `~/.config/managewidgets/manager.toml`
- `load_close_to_tray() -> bool | None`:文件不存在/损坏/无该键 → `None`(表示"未决定,
  下次关窗要问");正常读出 `True`/`False`。
- `save_close_to_tray(value: bool) -> None`:原子写(`mkstemp → 写 → os.replace`),
  父目录自动建。仅写 `close_to_tray` 一个键。
- `decide_close(pref: bool | None) -> str`:纯函数,`True→"tray"`、`False→"quit"`、
  `None→"ask"`。供 app 的 delete-event 决策,单测覆盖三分支。

读用 `tomllib`(stdlib),写用 `tomli_w`(已是依赖)。

### 2. `manager/tray.py` —— TrayIndicator

封装 AppIndicator,与 GTK 主线程同循环。构造时由 app 注入回调,自身不持有业务逻辑。

```
class TrayIndicator:
    def __init__(self, *, on_toggle_window, on_start_core, on_stop_core,
                 on_set_autostart, on_quit):
        # 建 Indicator(id="org.managewidgets.Manager",
        #   category=APPLICATION_STATUS, status=ACTIVE)
        # set_icon_theme_path(<manager/assets 绝对路径>)
        # set_icon_full("managewidgets-disconnected", "未连接")
        # 建 Gtk.Menu 并 set_menu(...)
    def set_connection(self, state: str, port: int | None = None) -> None
        # state ∈ {"connected","disconnected","error"};更新只读"连接状态"项文字
        # 与图标(connected→已连接图标,其余→未连接图标);port 为 None 时沿用上次已知端口
    def set_autostart_active(self, enabled: bool) -> None
        # 同步"开机自启"勾选项,handler_block 避免回写触发 on_set_autostart
    def refresh_window_item(self, visible: bool) -> None
        # 切换"显示面板"/"隐藏面板"标签文字
```

**菜单项(从上到下)**:
1. 显示面板 / 隐藏面板(`on_toggle_window`;标签随窗口可见性切换)
2. ── 分隔 ──
3. 连接状态:`已连接 · 端口 35355` / `未连接`(只读,`set_sensitive(False)`)
4. 启动底座(`on_start_core`) / 停止底座(`on_stop_core`)—— 两个独立项
5. 开机自启(`Gtk.CheckMenuItem`,`on_set_autostart(active)`)
6. ── 分隔 ──
7. 退出(`on_quit`)

图标:`set_icon_theme_path` 指向 `manager/assets` 绝对路径,`set_icon_full(name, desc)`
在 `managewidgets-connected` / `managewidgets-disconnected` 间切。

### 3. `manager/app.py` —— 集成

**生命周期 / 单实例**
- `do_activate`:**单实例守卫**——若窗口已存在则 `self._win.present()` 后 `return`
  (修掉评审记的 `do_activate` 重入会开第二窗口的问题);否则建窗口、建
  `TrayIndicator`、`self.hold()`(隐藏窗口时 app 不退出)。
- 若 `TrayIndicator` 因缺库构造失败:记日志,`self._tray=None`,继续无托盘运行。

**关窗(× / delete-event)**
- 处理器读 `load_close_to_tray()` → `decide_close(pref)`:
  - `"tray"` → 隐藏窗口、`refresh_window_item(False)`、`return True`(阻止销毁)。
  - `"quit"` → `self._quit()`。
  - `"ask"`(且有托盘)→ 弹**首次关窗对话框**:两按钮「最小化到托盘 / 退出」+
    「记住我的选择」`Gtk.CheckButton`。选完:勾了记住则 `save_close_to_tray(...)`;
    然后按所选执行 隐藏 或 退出。无托盘时 `"ask"` 直接退出。
- `_toggle_window()`:可见则隐藏、否则 `show_all()+present()`,并 `refresh_window_item`。
- `_quit()`:释放 hold、销毁窗口、`self.quit()`。**core 底座保持运行**(解耦;要停先点
  "停止底座")。

**启动即有数据(自启托盘面板的闭环)**
- `_connect_client()` 仍负责 discover+连。新增:activate 时若 `runtime` 文件不存在
  (core 未运行)→ 自动调 `_start_core()` 拉起底座;存在则只连(实例锁防重复起)。

**自启语义**
- `autostart_exec_cmd() -> str` 返回 `f"{sys.executable} -m manager"`(原 `-m core`),
  供 `_toggle_autostart` 与单测共用。概览页自启开关 与 托盘自启项 操作同一
  `enable/disable_autostart`,初始态都读 `is_autostart_enabled()`。
- 两处开关任一改动后,调用 `tray.set_autostart_active(...)` 与概览页 switch 同步。

**状态同步给托盘**
- 现有 `on_state(state)` 回调里(已 `GLib.idle_add` 切主线程)除更新概览页外,
  追加 `self._tray.set_connection(state, self._last_port)`。
- `_on_event` 收到 `status` 帧时记录 `self._last_port = status["core"]["port"]`,
  并 `self._tray.set_connection(<当前态>, self._last_port)` 刷新端口显示。

### 4. 图标资源 `manager/assets/*.svg`

两个极简 SVG(一个圆点:已连接=绿、未连接=灰),仅供托盘区分状态。随包安装:
`pyproject.toml` 的 `tool.setuptools` 增 `package-data`/`include-package-data`
把 `manager/assets/*.svg` 纳入,运行时用 `importlib.resources`/`__file__` 定位绝对
路径传给 `set_icon_theme_path`。

## 数据流

```
登录(自启 -m manager)
  → ManagerApp.do_activate:建窗口+建托盘+hold
  → discover;若无 runtime 自动 _start_core 拉起 core
  → CoreClient 连上 → on_state("connected") → 概览页 + tray.set_connection("connected", port)
  → status 帧 → _last_port 更新 → 数据源页/概览页刷新 + tray 端口显示刷新
用户点 × → delete-event → decide_close:
  首次 → 对话框 → (记住?存盘) → 隐藏到托盘 或 退出
  之后 → 按已存偏好 隐藏 或 退出
托盘菜单:显示/隐藏面板、启停底座、开机自启、退出(只退面板)
```

## 配置与文件

| 文件 | 归属 | 内容 |
|---|---|---|
| `~/.config/managewidgets/config.toml` | core 写 | 端口/provider/interval(不动) |
| `~/.config/managewidgets/manager.toml` | manager 写 | `close_to_tray = true/false` |
| `~/.config/autostart/managewidgets-core.desktop` | manager 写 | `Exec=… -m manager`(语义改为自启面板) |

> 注:自启 `.desktop` 的文件名沿用 `managewidgets-core.desktop`(`core/autostart.py`
> 既有命名),仅 `Exec` 改为 `-m manager`,避免新增第二个 .desktop 与旧文件并存。

## 错误处理与边界

- 缺 `AyatanaAppIndicator3` → 无托盘降级运行;`ask`/`tray` 关窗一律按退出。
- `manager.toml` 损坏/缺失 → `load_close_to_tray()` 返回 `None` → 关窗再问。
- 启动时 core 已在 → 不重复起(runtime 存在即跳过;实例锁兜底)。
- 退出仅退面板,不触碰 core;`_stop_core` 仍是显式动作。
- 自启项与概览页开关任一改动,另一方同步,避免两处状态不一致。
- 托盘状态更新全部经 `GLib.idle_add` 在主线程执行(回调来自 WS 客户端线程)。

## 测试策略

- `tests/test_manager_settings.py`(纯单测,无 GUI):
  - `save→load` 往返;缺文件→`None`;损坏→`None`;原子写(写后是合法 toml)。
  - `decide_close(True/False/None)` → `"tray"/"quit"/"ask"`。
  - `autostart_exec_cmd()` 含 `-m manager`。
- `tests/test_manager_tray.py`(`importorskip("gi")` + AppIndicator 可用 + DISPLAY):
  - 用 no-op 回调构造 `TrayIndicator` 不崩;
  - `set_connection("connected", 35355)` / `("disconnected", None)`、
    `set_autostart_active(True/False)`、`refresh_window_item(True/False)` 调用不崩;
  - 触发"启动底座"等菜单项 `activate` → 对应回调被调用一次。
- `tests/test_manager_smoke.py`(改):
  - app 的关窗决策:`pref=True→隐藏(返回 True 不退)`、`pref=False→退出`、
    `pref=None→ask`(用 `decide_close` 驱动,逻辑可测,不依赖真窗口事件);
  - 既有数据源页可见性/同步测试保持通过。
- 全量回归全过;无显示环境下 GUI 相关用例 skip。

> 真机交互(托盘是否出现在 Deepin dock、关窗对话框、点图标唤出)由人工 E2E 验收,
> 不在自动化范围。

## 自启/卸载注意

- 旧用户若已启用"开机自启"(指向 `-m core`),升级后**再次切换一次自启开关**即可把
  `.desktop` 的 Exec 刷新为 `-m manager`;或首次启动时检测到旧 Exec 自动改写(本期
  按"切换一次刷新"处理,不做自动迁移,避免隐式改用户文件)。
