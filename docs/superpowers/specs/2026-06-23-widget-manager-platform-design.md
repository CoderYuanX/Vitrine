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

### 3.3 WebSocket 协议(pub/sub + request/response)

**绑定与权限(最小权限原则)**:
- 仅监听 `127.0.0.1`,**绝不绑定 `0.0.0.0` 或任何远程地址**;拒绝非环回来源的连接。
- **正确的安全边界认知**:`127.0.0.1` 的 TCP 端口对**本机所有用户的任意进程**开放,不只是当前用户。所以"只监听环回"并不能把控制权限限制到当前用户。
- **第一版采用轻量 token 鉴权**(关闭跨用户漏洞,且不引入复杂认证):
  - 底座启动时生成随机 token,写入 runtime 文件 `core.json`,该文件**权限设为 `0600`(仅属主可读)**。
  - 客户端连接后,首条消息须携带 `token`;不带或不符 → 回 `error` + `unauthorized` 并断开。
  - 其他用户读不到 `0600` 的 token 文件,因而无法控制;当前用户的进程(面板)能读到。这是成本极低的正确做法,且为将来 Web 小组件保留了 TCP/WebSocket 形态(宿主把 token 注入给小组件)。
- 仍非目标:网络访问、跨机、强身份。后续若需更强隔离再考虑 Unix domain socket。

端口:默认 `35355`,占用则顺延;实际端口与 token 通过 runtime 状态文件(`0600`)对外公布(见 3.4),不靠面板猜。

**请求带可选 `id`,底座回 `ok`/`error` 响应(便于面板确认成功/失败、便于测试):**

客户端 → 底座:
```json
{ "id": "req-0", "action": "hello",        "token": "<从 core.json 读到的 token>" }
{ "id": "req-1", "action": "subscribe",   "topics": ["system.cpu", "time.now"] }
{ "id": "req-2", "action": "unsubscribe", "topics": ["system.cpu"] }
{ "id": "req-3", "action": "list_providers" }
{ "id": "req-4", "action": "set_provider", "provider": "system", "enabled": false }
{ "id": "req-5", "action": "set_interval", "topic": "system.cpu", "interval": 2 }
{ "id": "req-6", "action": "shutdown" }
```
- `hello` 必须是首条消息;未通过鉴权前的其他消息一律回 `unauthorized` 并断开。
- `shutdown`:请求底座优雅退出(见 §3.7 停止语义)。回 `ok` 后底座清理 runtime 文件并退出。

底座 → 客户端:
```json
// 数据推送(无 id,主动广播)
{ "type": "data",  "topic": "system.cpu", "data": { "percent": 37.2 }, "ts": 1750000000.0 }
// 状态快照(主动广播 + 可由 list_providers 触发,带回请求 id)
{ "type": "status", "id": "req-3", "status": { /* 见 3.5 状态模型 */ } }
// 控制成功
{ "type": "ok",    "id": "req-5" }
// 控制/请求失败,带机器可读 code
{ "type": "error", "id": "req-5", "code": "invalid_interval", "message": "interval must be in [0.5, 3600]" }
```

错误 `code` 枚举(第一版):`unauthorized`(token 缺失/不符)、`unknown_topic`、`unknown_provider`、`invalid_interval`、`bad_request`(JSON 解析失败 / 缺字段)。

**interval 边界与生效语义**:
- 取值范围 **[0.5, 3600] 秒**;非数字、负数、越界一律返回 `invalid_interval`,不改动现状。
- `set_interval` 成功后:**立即 `poll(topic)` 推一次,并以新周期重置该 topic 的定时器**(不必等旧周期走完)。
- `set_provider` / `set_interval` 处理成功后,除回 `ok` 外,再向所有客户端广播一条最新 `status`。

### 3.4 端口发现与实例发现(runtime 状态)

为避免"面板读到旧端口""多个底座互相踩配置",**端口/实例状态走独立的 runtime 文件,与可编辑配置分离**:

- 路径:`~/.local/state/managewidgets/core.json`(XDG state 目录,文件权限 `0600`)。
- 内容:`{ "pid": 12345, "port": 35355, "token": "<随机>", "started_at": 1750000000.0, "version": "0.1.0" }`。
- **实例锁用 `flock`,不靠裸 PID 判断**(避免 PID 复用误判):
  - 锁文件 `~/.local/state/managewidgets/core.lock`,底座启动时对它 `flock(LOCK_EX | LOCK_NB)`。
  - **拿到锁** → 没有其他实例(进程死亡时内核自动释放锁,天然防 PID 复用)→ 继续启动。
  - **拿不到锁** → 已有实例在跑 → 直接退出并打印已有端口。
- 底座启动流程:
  1. 尝试 `flock` 实例锁;失败即已有实例,退出。
  2. 拿到锁后,**仍校验残留 `core.json` 的可信度**:若文件里的 `pid` 存活且 `/proc/<pid>/cmdline` 确为 `managewidgets-core`、`started_at` 吻合,才信任其端口;否则视为陈旧文件丢弃。(双保险:flock 是主锁,cmdline+started_at 校验防止信任到被复用 PID 的无关进程。)
  3. 绑定端口(默认 35355,占用顺延),生成 token,成功后**原子写入** `core.json`(写临时文件 → `chmod 0600` → `rename`)。
  4. 正常退出时删除 `core.json`(锁由进程退出自动释放)。
- 面板发现底座流程:**优先读 `core.json` 拿 port + token**;读不到再退回 `config.toml` 默认端口尝试(无 token 时连接会被拒,提示需重启底座);都失败则视为底座未运行,提示一键启动。

### 3.5 状态模型(provider / topic)

`status` 快照结构明确分层,面板直接渲染,**不从 `data` 推送里反推**:

```json
{
  "core": {
    "port": 35355, "uptime": 137.0, "clients": 2, "version": "0.1.0",
    "notices": [
      { "code": "config_reset",
        "message": "配置文件损坏,已重置;原文件备份为 config.toml.bak.20260623T101500" }
    ]
  },
  "providers": [
    {
      "id": "system",
      "enabled": true,
      "status": "running",            // running | error | disabled
      "topics": [
        { "topic": "system.cpu", "interval": 1.0, "last_value": {"percent":37.2},
          "last_ts": 1750000000.0, "last_error": null },
        { "topic": "system.mem", "interval": 2.0, "last_value": {"percent":61.0},
          "last_ts": 1750000000.0, "last_error": null }
      ]
    }
  ]
}
```

- **provider 级**:`enabled`、`status`。`status: error` 表示采集异常(`last_error` 记在出错的 topic 上)。
- **topic 级**:`interval`、`last_value`、`last_ts`、`last_error`。
- **第一版无独立的 topic 级 enabled**:一个 topic 是否活跃 = 其 provider 的 `enabled`(与 §4.2 的 provider 级开关一致)。`set_topic` 留作后续扩展。
- **客户端数 `clients`** 放在 `core` 整体下,不放进 provider。
- **`core.notices`**:底座的一次性运行告警数组,每项 `{ code, message }`。第一版用到 `config_reset`(配置损坏已重置)。面板读到即向用户提示;数组为空表示无告警。这样"配置已重置"这类事件有明确字段承载,面板和测试都不需臆测。

### 3.6 配置存储

- 路径:`~/.config/managewidgets/config.toml`(可编辑、可持久)。
- 内容:WebSocket 默认端口、各 provider 的 `enabled`、各 topic 的 `interval` 覆盖、自启状态。**不含运行时端口/pid**(那是 runtime 文件的职责,见 3.4)。
- 启动时读取,运行中被面板改动后写回。

### 3.7 进程:启动与停止语义

- 底座是独立可执行入口(如 `managewidgets-core`),可由面板拉起,也可手动/自启运行。
- **启动(面板"启动底座")**:面板以子进程方式拉起 `managewidgets-core`,然后按 §3.4 通过 runtime 文件发现端口+token 并连接。
- **停止(面板"停止底座")——首选协议、不靠猜进程**:
  1. **首选**:面板发 WS `shutdown` 控制消息;底座回 `ok` 后**优雅退出**(停调度循环、断开所有客户端、删除 `core.json`、释放锁)。此路径与"谁拉起的"无关——即使底座是自启或手动跑的,只要面板能连上就能停。
  2. **兜底**:WS 连不上但 `core.json` 存在且校验可信(pid 存活 + cmdline 匹配,见 §3.4)→ 面板向该 pid 发 `SIGTERM`;底座捕获 `SIGTERM` 同样走优雅退出。
  3. **不做**:对校验不通过 / 无法确认身份的 pid 发信号(避免误杀无关进程)——此时提示用户手动处理。
- 底座对 `SIGTERM`/`SIGINT` 均做优雅退出:清理 `core.json`、释放 `flock`。
- 自启:在 `~/.config/autostart/` 写入 `.desktop` 文件(XDG 标准,跨桌面通用),由面板开关控制。

## 4. 管理面板 manager

GTK + PyGObject 应用。一个主窗口,左侧导航或顶部页签切换三页。

### 4.1 概览页

- 底座状态:运行中 / 已停止;监听端口;当前连接客户端数;运行时长。
- 按钮:启动底座(拉起子进程)/ 停止底座(发 WS `shutdown`,兜底 `SIGTERM`,见 §3.7)。
- **告警区**:渲染 `core.notices`(如"配置已重置"提示),可手动关闭。
- 开关:开机自启(写/删 autostart `.desktop`)。

### 4.2 数据源页(主角)

**按 provider 分组显示**,启停与间隔的语义因此清晰、不互相误伤:

- 每个 provider 一个分组,**组标题上放 provider 级启用/停用开关**(下发 `set_provider`)。停用即该 provider 所有 topic 一起停。
- 组内每个 topic 一行,只负责该 topic 自己的展示与间隔:
  - 名称(如 "CPU 占用")
  - **实时当前值**(面板自身订阅该 topic,持续刷新显示)
  - 刷新间隔(可编辑,下发 `set_interval`;越界则面板提示底座返回的 `invalid_interval`)
  - (设置入口:本版 system/time 无额外设置,留位)
- **不在 topic 行放 provider 开关**——避免"在 CPU 行关开关却把内存也停了"的语义歧义。
- 面板与底座断连时整页显示"未连接",并提供重连。

### 4.3 小组件页(占位)

- 空状态:说明"小组件渲染功能开发中",列出后续能力(贴桌面、Web 小组件、订阅底座数据)。
- 不实现任何渲染/列表逻辑。

### 4.4 面板 ↔ 底座连接(GTK / asyncio 边界,实现方案定死)

为避免实现时在 GTK 主循环和 asyncio 之间摇摆,**这一版固定如下方案**:

- 端口与 token 来自 §3.4 的发现流程(先 runtime `core.json`,再退回配置默认端口)。连上后**首条发 `hello` 带 token**完成鉴权,再订阅。连不上则提示底座未运行,可在概览页一键启动。
- `manager/ws_client.py` **在一个独立线程内运行自己的 asyncio event loop**,该线程负责所有 WebSocket 收发与自动重连(带指数退避)。
- **所有 UI 更新一律通过 `GLib.idle_add(...)` 回到 GTK 主线程执行**;WS 线程绝不直接碰 GTK 控件。
- 面板向底座发请求时,WS 线程按 `id` 关联 `ok`/`error` 响应,再用 `GLib.idle_add` 把结果回灌给 UI(保存成功/失败提示)。
- 主窗口关闭时**显式停止 asyncio loop、关闭 WS 连接、join 线程**,不留悬挂线程。

## 5. 错误处理

- **底座未运行**:面板显式提示,提供"启动底座"。不静默卡死。
- **端口被占用**:底座顺延端口,实际端口写入 runtime `core.json`(§3.4);面板从 runtime 文件读端口,因此不会读到旧端口。
- **多实例**:底座启动时用 `flock` 实例锁,拿不到锁即拒绝启动第二个;不靠裸 PID 判断,天然防 PID 复用(§3.4)。
- **未授权连接**:首条非 `hello` 或 token 不符 → 回 `unauthorized` 并断开;同机其他用户因读不到 `0600` 的 token 文件而无法控制(§3.3)。
- **provider 采集异常**(如 psutil 偶发报错):对应 topic 写入 `last_error`、provider 标记 `status: error` 并广播 `status`,面板显示错误态;不影响其他 provider 与底座主循环。
- **WS 客户端异常断开**:底座清理其订阅、`clients` 计数减一;面板侧自动重连(指数退避)。
- **坏请求**:JSON 解析失败 / 缺字段 → 回 `error` + `bad_request`,连接不断。
- **配置文件损坏**:底座**把损坏文件重命名为 `config.toml.bak.YYYYMMDDHHMMSS`,生成全新默认配置并记录日志**,并在 `status.core.notices` 追加一条 `config_reset`;面板读到该 notice 后提示"配置已重置"。绝不静默覆盖用户配置。

## 6. 测试策略

- **Provider 单元测试**:`system`/`time` 的 `poll(topic)` 返回结构正确(psutil 可 mock)。
- **协议单元测试**:订阅/退订/控制消息处理;请求 `id` 正确回传;未知 topic→`unknown_topic`、坏消息→`bad_request`、越界间隔→`invalid_interval`;`set_interval` 后立即重推一次并重置周期。
- **鉴权测试**:不发 `hello` 或 token 错→`unauthorized` 并断开;正确 token→放行;`shutdown` 触发优雅退出(清 `core.json`、释放锁)。
- **底座集成测试**:起一个底座实例,用测试 WS 客户端订阅,断言收到 `data` 推送、改 interval 推送频率随之变化、停 provider 后该组 topic 停推而其他 provider 不受影响。
- **端口/多实例测试**:端口被占用时底座顺延并把实际端口写入 `core.json`,测试客户端按该文件能连上;已持锁底座存在时再次启动因 `flock` 失败而直接退出、不起第二个实例;陈旧 `core.json`(pid 复用为无关进程,cmdline 不匹配)被识别为不可信、不误判为存活实例。
- **配置健壮性测试**:`config.toml` 内容损坏时,底座把它备份为 `config.toml.bak.<ts>`、生成默认配置、正常启动,且 `status.core.notices` 含 `config_reset`。
- **面板**:WS 客户端连接/重连退避、`id`↔响应关联可单元测;runtime 端口发现优先于配置端口;GUI 渲染做冒烟(能起、能连、能显示一次数据)。
- 遵循 TDD:每个单元先写失败测试再实现。

## 7. 仓库结构(建议)

```
managewidgets/
  core/                     # 底座
    __init__.py
    server.py               # WebSocket pub/sub 服务 + 调度循环 + 请求/响应
    state.py                # runtime 文件(core.json,0600)+ token 生成 + flock 实例锁 + 可信校验
    config.py               # 配置读写 + 损坏备份回退
    providers/
      __init__.py
      base.py               # Provider 接口(topics / poll(topic) / interval)
      system.py             # CPU/内存
      time.py               # 时间
    __main__.py             # managewidgets-core 入口(实例发现 → 绑定 → 写 runtime)
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
    test_state_discovery.py   # 端口顺延 / runtime 文件 / 多实例
    test_config.py            # 损坏备份回退
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

逐项可验证清单:

- [ ] `managewidgets-core` 可启动,监听 `127.0.0.1` 上的端口,并写出 `core.json`(pid/port/started_at/version)。
- [ ] `managewidgets-manager` 可启动,显示概览 / 数据源 / 小组件(占位)三页。
- [ ] 数据源页中 `system.cpu` / `system.mem` / `time.now` 实时刷新。
- [ ] 修改 `system.cpu` 的 interval 后,推送频率随之变化(可观测),且面板收到 `ok` 提示保存成功。
- [ ] 停用 `system` provider 后,CPU/内存停止推送,`time.now` 不受影响。
- [ ] 面板关闭重开后,能通过 runtime 文件自动连接到已运行的底座。
- [ ] 底座未运行时,面板可在概览页一键启动底座。
- [ ] 端口被占用时,底座顺延端口并写入 `core.json`,面板据此仍能连上(不读到旧端口)。
- [ ] 已有底座在跑时,再次启动底座因 `flock` 实例锁失败而不起第二个实例。
- [ ] 面板"停止底座"经 WS `shutdown` 优雅停止底座(即便底座非面板拉起);WS 不可用时按可信 pid 兜底 `SIGTERM`。
- [ ] 连接需带正确 token(来自 `0600` 的 `core.json`);缺/错 token 被 `unauthorized` 拒绝。
- [ ] `config.toml` 损坏时,底座备份为 `config.toml.bak.<ts>`、以默认配置正常启动,并通过 `core.notices` 让面板提示"配置已重置"。
- [ ] 越界 interval 被拒(`invalid_interval`),坏请求返回 `bad_request`,连接不断。

达成即证明"底座 + 管理器"地基可用,且数据契约已被真实消费者(面板)端到端验证。
