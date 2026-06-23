# 桌面小组件管理器 — 设计文档(第一版:底座 + 管理面板)

- 日期:2026-06-23
- 状态:已确认,待实现
- 适用范围:本设计文档仅覆盖**第一版**——数据底座 + 管理面板。桌面渲染、小组件包与宿主进程在后续版本(见末尾路线图)。

## 1. 背景与目标

用户想要一个**跨 Linux 发行版**的桌面小组件平台。最终形态包含三部分:

1. **数据底座(中台)**:统一采集系统数据/天气/媒体等,所有小组件从它这里订阅数据。
2. **小组件宿主**:把小组件渲染到桌面上(X11 优先)。
3. **管理面板**:启用/配置/布局小组件、管理数据源。

经讨论,**第一版只做"底座 + 管理面板",不做小组件渲染**。先把平台和控制台立起来,并用真实路径验证"底座供数"这一核心接口。

### 关键约束与决策(已确认)

| 决策点 | 结论 |
|---|---|
| 运行平台 | **X11 优先**(覆盖当前 Deepin 25 及 KDE/GNOME-X11/XFCE/MATE/Cinnamon);Wayland 架构预留,后续单独加宿主后端 |
| 渲染方式 | 后续版本用无边框 keep-below 桌面层窗口(Conky 式);本版不涉及 |
| 小组件形式 | Web(HTML/CSS/JS),后续版本;本版不涉及 |
| 技术栈 | **Python**;GUI 用 **GTK + PyGObject(gi)**;数据供给用 **WebSocket** |
| 第一版范围 | **底座 + 管理面板**(面板实时显示底座数据,小组件页占位) |

### 非目标(本版明确不做 / YAGNI)

- 桌面渲染、小组件包格式、宿主进程、示例小组件
- Wayland 宿主(layer-shell)
- 天气 / MPRIS / 磁盘 / 网络 / 温度等更多数据源
- 远程数据、多用户、云同步、插件签名审核、小组件市场

## 2. 总体架构(第一版)

两个进程,通过本地 WebSocket 解耦:

```
┌─────────────────────────────────────────────────────────┐
│  ① 底座 core (Python, 无界面常驻)                          │
│   • Provider 框架(可插拔):system(CPU/内存)、time        │
│   • 本地 WebSocket 服务 (ws://127.0.0.1:PORT) pub/sub      │
│   • 配置存储 (~/.config/managewidgets/config.toml)         │
│   • 状态查询(provider 列表/状态/当前值/客户端数)          │
└───────────────────────▲──────────────────────────────────┘
                         │ WS 订阅 system.cpu / time.now …
                         │ (面板是底座的第一个消费者,dogfood 数据契约)
              ┌──────────┴───────────────────────────────────┐
              │ ② 管理面板 manager (Python + GTK GUI)          │
              │  • 概览页:底座启停/自启/端口/客户端数/运行时长 │
              │  • 数据源页:provider 实时值 / 间隔 / 开关 / 设置│
              │  • 小组件页:占位(渲染功能开发中)              │
              └───────────────────────────────────────────────┘
```

**核心设计点**:管理面板通过 WebSocket 连接底座、订阅 topic 来显示实时数据。面板因此成为底座的**第一个真实消费者**,提前用生产路径验证了"底座供数"接口。后续小组件复用同一条已跑通的路径。

## 3. 底座 core

### 3.1 Provider 框架

- 每个数据源是一个 Provider 插件,统一接口:
  - `id`(如 `system`、`time`)
  - `topics`:它产出的 topic 列表;**每个 topic 各有自己的刷新周期 `interval`(秒)**,可被配置覆盖(如 `system.cpu` 1s、`system.mem` 2s)
  - `enabled`:启用/停用(provider 级,关掉则其所有 topic 都停)
  - `poll(topic) -> dict`:被周期性调用,返回该 topic 的最新数据
  - 可选 `settings_schema`:provider 专属配置项(本版 system/time 无需)
- 底座维护一个调度循环:对每个启用 provider 的每个 topic,按该 topic 的 interval 调 `poll(topic)`,把结果推给订阅了该 topic 的客户端。

### 3.2 本版 Provider

| Provider | Topics | 数据示例 | 默认间隔 |
|---|---|---|---|
| `system` | `system.cpu` | `{ "percent": 37.2, "per_core": [..] }` | 1s |
| `system` | `system.mem` | `{ "percent": 61.0, "used": .., "total": .. }` | 2s |
| `time` | `time.now` | `{ "iso": "...", "epoch": .., "tz": ".." }` | 1s |

- `system` 用 `psutil`(纯内核接口,跨发行版一致)。
- `time` 用标准库。

### 3.3 WebSocket 协议(pub/sub)

监听 `ws://127.0.0.1:PORT`(端口默认值写在配置,默认 `35355`,占用则顺延)。

客户端 → 底座:
```json
{ "action": "subscribe",   "topics": ["system.cpu", "time.now"] }
{ "action": "unsubscribe", "topics": ["system.cpu"] }
{ "action": "list_providers" }
```

底座 → 客户端:
```json
{ "type": "data",      "topic": "system.cpu", "data": { "percent": 37.2 }, "ts": 1750000000.0 }
{ "type": "providers", "providers": [ { "id": "system", "enabled": true, "interval": 1, "topics": [..], "status": "running" }, .. ] }
{ "type": "error",     "message": "unknown topic: foo" }
```

控制类(供面板改配置/启停 provider):
```json
{ "action": "set_provider", "id": "system", "enabled": false }
{ "action": "set_interval", "id": "system", "topic": "system.cpu", "interval": 2 }
```
底座处理后广播一条新的 `providers` 状态。

### 3.4 配置存储

- 路径:`~/.config/managewidgets/config.toml`
- 内容:WebSocket 端口、各 provider 的 `enabled` 与 `interval` 覆盖、自启状态。
- 启动时读取,运行中被面板改动后写回。

### 3.5 进程与自启

- 底座是独立可执行入口(如 `managewidgets-core`),可由面板拉起,也可手动/自启运行。
- 自启:在 `~/.config/autostart/` 写入 `.desktop` 文件(XDG 标准,跨桌面通用),由面板开关控制。

## 4. 管理面板 manager

GTK + PyGObject 应用。一个主窗口,左侧导航或顶部页签切换三页。

### 4.1 概览页

- 底座状态:运行中 / 已停止;监听端口;当前连接客户端数;运行时长。
- 按钮:启动底座 / 停止底座。
- 开关:开机自启(写/删 autostart `.desktop`)。

### 4.2 数据源页(主角)

- 列出所有 provider 产出的 topic,每行:
  - 名称(如 "CPU 占用")
  - **实时当前值**(面板自身订阅该 topic,持续刷新显示)
  - 刷新间隔(可编辑,改动通过 `set_interval` 下发)
  - 启用/停用开关(通过 `set_provider` 下发)
  - 设置入口(本版 system/time 无额外设置,留位)
- 面板与底座断连时显示"未连接",并提供重连。

### 4.3 小组件页(占位)

- 空状态:说明"小组件渲染功能开发中",列出后续能力(贴桌面、Web 小组件、订阅底座数据)。
- 不实现任何渲染/列表逻辑。

### 4.4 面板 ↔ 底座连接

- 面板启动时尝试连接 `ws://127.0.0.1:PORT`;连不上则提示底座未运行,可在概览页一键启动。
- 面板用一个后台 WebSocket 客户端线程/异步循环接收推送,经 GLib 主循环安全地更新 UI。

## 5. 错误处理

- **底座未运行**:面板显式提示,提供"启动底座"。不静默卡死。
- **端口被占用**:底座顺延端口并写回配置;面板从配置读端口。
- **provider 采集异常**(如 psutil 偶发报错):该 provider 标记 `status: error` 并广播,面板显示错误态,不影响其他 provider 与底座主循环。
- **WS 客户端异常断开**:底座清理其订阅;面板侧自动重连(带退避)。
- **配置文件损坏**:底座回退到默认配置并记录日志,不崩溃。

## 6. 测试策略

- **Provider 单元测试**:`system`/`time` 的 `poll()` 返回结构正确(psutil 可 mock)。
- **协议单元测试**:订阅/退订/控制消息的处理逻辑;未知 topic / 坏消息返回 `error`。
- **底座集成测试**:起一个底座实例,用测试 WS 客户端订阅,断言能收到 `data` 推送,改 interval 生效,停 provider 后不再推送。
- **面板**:连接逻辑与重连退避可单元测;GUI 渲染做冒烟(能起、能连、能显示一次数据)。
- 遵循 TDD:每个单元先写失败测试再实现。

## 7. 仓库结构(建议)

```
managewidgets/
  core/                     # 底座
    __init__.py
    server.py               # WebSocket pub/sub 服务 + 调度循环
    providers/
      __init__.py
      base.py               # Provider 接口
      system.py             # CPU/内存
      time.py               # 时间
    config.py               # 配置读写
    __main__.py             # managewidgets-core 入口
  manager/                  # 管理面板
    __init__.py
    app.py                  # GTK 应用入口
    ws_client.py            # 连底座的 WS 客户端
    pages/
      overview.py
      datasources.py
      widgets_placeholder.py
  tests/
    test_providers.py
    test_protocol.py
    test_core_integration.py
    test_ws_client.py
  pyproject.toml
  docs/superpowers/specs/2026-06-23-widget-manager-platform-design.md
```

依赖:`psutil`、一个 WebSocket 库(如 `websockets`)、`PyGObject`(系统包 `python3-gi` + `gir1.2-gtk`)。

## 8. 后续路线图(本版之后)

1. **小组件宿主(X11)**:无边框 keep-below 桌面层窗口;锁定/编辑两态;位置持久化(显示器 + 相对坐标);可选点击穿透。
2. **Web 小组件包**:`manifest.json` + `index.html`;注入 `mw.subscribe(topic, cb)` 薄封装;`~/.local/share/managewidgets/widgets/` 扫描即装。
3. **更多 Provider**:天气(wttr.in 无 key 或 OpenWeatherMap)、MPRIS 媒体、磁盘/网络/温度。
4. **管理面板补全**:小组件列表 + 开关、设置表单(读 manifest schema 自动生成)、布局编辑。
5. **Wayland 宿主后端**:wlr-layer-shell(wlroots/KWin);GNOME-Wayland 退化为普通窗口并说明限制。

## 9. 验收(本版 Definition of Done)

启动底座 → 打开管理面板 → 数据源页中 CPU/内存/时间实时跳动 → 修改某项刷新间隔立即生效 → 停用某 provider 后其值停止更新 → 重启面板能自动重连。这证明"底座 + 管理器"地基可用,且数据契约已被真实消费者验证。
