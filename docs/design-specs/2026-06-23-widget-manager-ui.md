# 设计规格 — 小组件管理器界面（整窗对齐原型）

- **日期**：2026-06-23
- **目标模块**：`manager/`（整个管理器窗口：外壳 + 侧栏 + 顶栏 + 概览/数据源/小组件三页）
- **设计真源**：`prototype/小组件管理器.html`
  - 该文件是「Bundled Page」打包导出；真实源在其内嵌 JSON 的 `pages["小组件管理器.dc"]`，已解包至工作副本 `scratchpad/unbundled.html`（HTML 模板）+ `scratchpad/logic.js`（`class Component extends DCLogic` 状态与计算样式）。
  - 提取依据标注：`原型CSS` = unbundled 内联样式/`:root` 变量；`原型JS` = logic.js 的 getter/state；`推断` = 截图或经验推断。
- **源质量**：**HIGH**。完整 `:root` token 体系（颜色/间距/字号/圆角/阴影显式给值）、每个视图含状态相关样式 getter、完整交互状态机。无需臆测主色或字体。
- **实现栈**：Python + GTK 3（PyGObject），见 `pyproject.toml` / `manager/app.py`。

---

## 0. 范围与确认状态

- 用户已确认：范围 = **整个应用**，工作 = 把现有 GTK3 管理器窗口**对齐原型**。
- 本规格为开发契约。每轮编码须回到本文件、指明实现的章节，并把视觉漂移回写本文件。

### 已锁定决策（2026-06-23 用户确认）
1. **方向**：确认，按 §11 切片顺序逐层实现。
2. **字体**：**随包安装**。把完整 `Inter.ttf` + `JetBrainsMono.ttf` 纳入 `manager/assets/fonts/`，启动时若用户字体目录缺则复制并 `fc-cache` 注册（本机 `~/.local/share/fonts/` 已存在该二者，可直接取用为包内源）。→ 撤销 §10 风险 2。
3. **细节保真**：**全部自绘高保真**。sparkline 折线、重连脉冲、iOS 风开关一律用 `Gtk.DrawingArea`（Cairo）自绘还原，不降级。→ 撤销 §10 风险 3、4 的降级条款。

---

## 1. 布局（Layout）

整体是一个**居中的「macOS 风格窗口」卡片**。原型在浏览器里画了个 1040×680 的假窗口；真实 GTK 应用本身就是窗口，所以**外层假窗口边框/居中容器不复刻**，只复刻其内部结构。

| 区域 | 原型值（原型CSS） | GTK 映射 |
|---|---|---|
| 窗口内容尺寸 | 1040×680（假窗口）| `Gtk.ApplicationWindow` 默认 `1040×680`（当前是 560×460，需改）|
| 标题栏 traffic-light 行 | 高 38px，三个 12px 圆点 + 居中标题 + 右侧「关闭即隐藏至托盘」提示 | **不复刻**假红绿灯。标题/托盘提示交给真实窗口标题栏；「关闭即隐藏至托盘」语义已由现有 `close_to_tray` 逻辑承载 |
| 主体 | `flex` 横向：sidebar + main，`min-height:0` | `Gtk.Box(HORIZONTAL)` |
| 侧栏 aside | **宽 220px 固定**，纵向 flex，背景 `--bg-sidebar`，右侧 1px 分隔 | `Gtk.Box(VERTICAL)`，`set_size_request(220,-1)`，CSS `.sidebar` |
| 主列 | `flex:1`，纵向，`min-width:0` | `Gtk.Box(VERTICAL)`，hexpand |
| 顶栏 header | **高 64px 固定**，横向，左侧标题/副标题，右侧连接 chip，`padding` 横向，底部 1px 边框 | `Gtk.Box(HORIZONTAL)`，`.topbar` |
| 内容 main | `flex:1; overflow:auto; padding:24px` | `Gtk.ScrolledWindow` 内放 `Gtk.Stack`，每页 `border-width≈24` |

**导航 = 侧栏，不是标签页**。当前实现用 `Gtk.Notebook`（顶部标签），**必须替换**为：侧栏按钮 + `Gtk.Stack` 切页。

### 侧栏结构（自上而下）
1. **品牌行**：`padding:18px 18px`，gap 10。30×30 圆角 8 的方块 logo（文字「W」，背景 `--brand-primary`，白字 700）+ 两行文字：`WidgetHub`（14px/700）/`小组件管理器`（11px，`--text-muted`）。
2. **导航 nav**：`padding:6px 12px`，gap 2，三个按钮：
   - 概览 / 数据源（右侧 provider 计数 badge）/ 小组件（右侧「即将」灰字 badge）。
   - 每项含 16px 图标 + 文案，见 §4 导航按钮。
3. **底部状态**：`margin-top:auto; padding:14px 18px`，顶部 1px 边框。8px 圆点（绿=运行/灰=未运行）+ 文案（`底座运行中`/`正在连接…`/`底座未运行`）。

---

## 2. 设计 Token（原型CSS，`:root`）

> GTK3 CSS **不支持** CSS 自定义属性（`--var`）与 flexbox。颜色 token → `@define-color`；其余（间距/字号/圆角）在各 `.class` 规则里写字面值，并在注释标注来源 token 名。布局一律用 GTK Box，不用 CSS 排版。

### 颜色
```
@define-color bg_app        #EEF3F9;  /* 画布（窗口外）*/
@define-color bg_window     #F8FAFD;
@define-color bg_panel      #FFFFFF;  /* 卡片/侧栏面板 */
@define-color bg_panel_subtle #F6F8FC;
@define-color bg_sidebar    #F7F9FD;
@define-color border_default #E3E8F0;
@define-color border_subtle  #EDF1F6;
@define-color border_strong  #D6DEE9;
@define-color border_focus   #8BB8FF;
@define-color text_primary   #111827;
@define-color text_secondary #4B5563;
@define-color text_muted     #7B8794;
@define-color text_disabled  #AAB4C2;
@define-color brand_primary  #2563EB;
@define-color brand_primary_hover #1D4ED8;
@define-color brand_primary_soft  #EAF2FF;  /* 导航激活底 */
@define-color brand_primary_subtle #F3F7FF;
@define-color brand_primary_border #BBD4FF;
@define-color success_primary #16A34A;  @define-color success_soft #EAF8EF;
@define-color success_subtle #F3FBF6;    @define-color success_border #BFE8CD; @define-color success_text #15803D;
@define-color danger_primary #EF4444;   @define-color danger_hover #DC2626;
@define-color danger_soft #FEF2F2;       @define-color danger_subtle #FFF7F7; @define-color danger_border #FECACA; @define-color danger_text #DC2626;
@define-color warning_primary #F59E0B;   @define-color warning_soft #FFF7E6; @define-color warning_border #FCD48B; @define-color warning_text #B45309;
@define-color info_primary #3B82F6;      @define-color info_soft #EFF6FF; @define-color info_border #BFDBFE; @define-color info_text #1D4ED8;
/* 紫色用于内存可视化：#8b5cf6（原型JS memColor 正常态）*/
/* 中性档（原型用到）：neutral-100/200/300/400 ≈ #F3F4F6 / #E5E7EB / #D1D5DB / #9CA3AF（推断，Tailwind 灰阶）*/
```

### 字体 / 字号 / 字重 / 行高
- `font-sans`: `Inter, system-ui, ...`（**风险**：系统未必装 Inter，回退 system-ui；见 §10）。
- `font-mono`: `JetBrains Mono, ui-monospace, ...`（数值/端口/时间/间隔用等宽）。
- 字号：title 24/metric 20/section 16/body 14/caption 12（px）。原型局部另用 18(页标题)、15(provider 名)、13、11、10。
- 字重：400/500/600/700。
- 行高：title 32/metric 28/section 24/body 22/caption 18。

### 间距 / 圆角 / 阴影
- space：xs4 / sm8 / md12 / lg16 / xl24。
- radius：xs4 / sm6 / md8 / lg10 / xl14 / window16 / pill999。
- 阴影：
  - card `0 6px 18px rgba(15,23,42,.06)`；card-hover `0 10px 24px rgba(15,23,42,.10)`。
  - button `0 4px 10px rgba(37,99,235,.22)`；danger-button `0 4px 10px rgba(239,68,68,.22)`。
  - **风险**：GTK3 `box-shadow` 支持有限（不支持外扩多层柔和阴影的某些写法），可能需降级为单层或省略，标注为漂移。

---

## 3. 现有实现状态（Existing status）

| 现状 | 评估 |
|---|---|
| `Gtk.Notebook` 顶部标签切页 | **替换**为侧栏 + `Gtk.Stack` |
| 窗口 560×460 | **改** 1040×680 |
| 无任何 CSS / token | **新增** `CssProvider` 全局加载 token + 组件类 |
| `OverviewPage`：裸 Label「端口:- | 客户端:- | 运行时长:-」+ 启动/停止按钮 + 自启 Switch | 重排为：状态横幅 + 4 张 metric 卡 + 设置卡。**保留**回调 `on_start/on_stop/on_autostart`、方法 `set_connection/update/set_autostart_active` 签名与数据流 |
| `DataSourcesPage`：`Gtk.Frame` + `Gtk.Switch` + `Gtk.SpinButton(0.5–3600,0.5)` 每行 | 重排为 provider section 卡（badge+开关）+ topic 行（值+进度条+步进器+最近更新）。**保留** `on_set_provider/on_set_interval`、`update/apply_data`、信号阻塞防回环逻辑 |
| `WidgetsPlaceholderPage`：两行文字 | 重排为居中空状态 + 3 张预览卡 |
| 托盘/supervisor/自启/关闭策略 | **不动**，纯展示层对齐 |

**数据契约（须保留）**：`status = {core:{port,clients,uptime,notices[]}, providers:[{id,enabled,topics:[{topic,interval,last_value}]}]}`；事件 `data{topic,data}` / `status{...}` / `error{message}`；连接态 `connected|disconnected|reconnecting|error|start_failed`。

---

## 4. 组件清单（Components）

### 导航按钮（原型JS `navStyle`）
- `padding:9px 12px; radius:8px; font 13/600; gap:11`；图标 16px。
- 激活：背景 `brand_primary_soft`，文字 `brand_primary`；非激活：透明背景，文字 `text_secondary`。hover：浅底（`--bg-panel-subtle`，推断）。
- 数据源 badge：`activeProviderCount`（启用的 provider 数）；白底、`brand_primary` 字、`brand_primary_border` 边、pill。
- 小组件 badge：「即将」10px/600 灰字 pill。

### 顶栏（原型CSS + JS `titles`）
- 左：页标题 18/700 + 副标题 12 `text_muted`。三页标题/副标题：
  - 概览 / 「查看数据底座运行状态并控制其生命周期」
  - 数据源 / 「管理 provider、查看实时数据、调整刷新间隔」
  - 小组件 / 「桌面 Web 小组件 — 即将推出」
- 右：连接 chip（圆点 7px + 文案），三态配色见 §5。

### 概览页
- **状态横幅**：左 42×42 圆角10 图标块 + 标题/描述 + 右侧主操作按钮。三态（见 §5）。按钮：连接时「停止底座」（danger 实心 + danger 阴影）/未连「启动底座」（brand 实心 + brand 阴影）/重连「启动中…」。高 38，`padding:0 20`，radius sm。
- **告警条**（可关）：`alertOpen` 时显示；warning 配色；标题「配置文件损坏，已重置为默认值」+ 描述（config.toml 解析失败…）+ 右上 × 关闭。→ 映射现有 `core.notices`。
- **4 张 metric 卡**：grid 4 列 gap14。卡 = `metricCardStyle`（白底、border_default、radius lg、card 阴影、padding16）。每卡：标签 12 muted / 大数值 mono 22/700（连接时 brand 色，断开 `text_disabled` 显「—」）/ 脚注 11 muted。
  - 监听端口 `portVal`（连接 8765，断开 —）/ `ws://127.0.0.1`
  - 已连接客户端 `clientsVal` / `WebView 订阅者`
  - 运行时长 `uptimeVal`（`fmtUptime`：>1h 显 `h m`，否则 `m s`）/ `自上次启动`
  - 底座版本 `v0.1.0` / `data-base`
- **设置卡**：两行，行间分隔。
  - 开机自启：标题 14/600 + 描述 12 muted + 右侧 iOS 风开关（`trackStyle/knobStyle`）。
  - 托盘行为：标题 + 描述「关闭窗口仅隐藏面板…」+ 右侧「隐藏到托盘」标签（非开关，纯文案；可按现有 `close_to_tray` 偏好做成可点）。

### 数据源页
- **断连横幅**（`disconnected` 时）：danger 配色，「未连接到数据底座 / 控件已禁用…」+「启动底座」按钮。
- **provider section 卡**（System、Time）：`sectionBase`（白底 radius lg card 阴影），停用/断连时 `opacity:.62`。
  - section 头：34×34 圆角8 图标 + 名称 15/700 + `provider · system`（mono 12 muted）+ 状态 badge（运行中/已停用）+ iOS 开关（断连时禁用半透明）。
  - **topic 行**（`rowBase` padding16/18 gap18，行间 1px subtle 边框）：
    - 左 150px：topic 中文名 13/600 + key（mono 11 muted，如 `system.cpu`）。
    - 中 150px：值 mono 18/700 + 5px 高进度条（宽=百分比，色随阈值 §5）。
    - sparkline（System 的 CPU/MEM 有迷你折线，`spark()` 生成 118×30 polyline；**可选**，GTK 需自绘，列为低优先/可降级）。
    - 右：刷新间隔步进器（− 值 +，步进按钮 `stepBtnStyle` 24×24）+ 最近更新（「刚刚」/「已暂停」）。
  - Time provider 只有「当前时间」`time.now` 行（值 = `HH:MM:SS` mono）。
- 底部注记：「刷新间隔范围 0.5s – 3600s，修改后立即生效。」
- **间隔步进档位（原型JS `bumpIv`）**：`[0.5,1,2,3,5,10,15,30,60,120,300,600,1800,3600]`，显示 `fmtIv`（<10 显一位小数，否则整数）+ `s`。当前实现用连续 SpinButton(0.5,3600,0.5)；**对齐为按档位步进**（保留 `on_set_interval`）。

### 小组件页
- 居中空状态：54×54 圆角14 图标块 + 标题 17/700「小组件渲染功能开发中」+ 描述 13 + 三个 chip（贴到桌面 / Web 小组件 / 订阅底座数据）。
- 「未来组件库预览」标题 + grid 3 列预览卡（`previewCardStyle`：subtle 底、**虚线** border_strong、radius lg、min-height148、右上「即将支持」角标）：CPU 仪表 / 内存条（3 根紫色进度）/ 时钟（mono 30）。

---

## 5. 状态（States）

| 维度 | 取值 | 视觉 |
|---|---|---|
| 连接 `conn` | connected / reconnecting / disconnected | chip & 横幅 & 底部圆点配色（success / warning+`livePulse` 脉冲 / neutral）。文案：已连接 / 重连中… / 未连接 |
| daemon | on/off | 决定主按钮 启动/停止 与配色 |
| provider 开关 | 运行中 / 已停用 | badge：success / neutral；section opacity |
| 断连 | 所有 provider 开关禁用、值显「—」、最近更新「已暂停」、section opacity .62 |
| 指标阈值（原型JS） | CPU >80 danger / >60 warning / 否则 brand；MEM >85 danger / >70 warning / 否则紫 `#8b5cf6` | 进度条与数值同色 |
| 自启开关 | on/off | iOS 风 track/knob |
| 告警 | open/dismissed | 概览告警条显隐 |
| 焦点 | 输入/按钮 focus | `border_focus #8BB8FF`（推断映射现有 GTK focus ring）|

> 原型默认渲染态：`page=overview, daemon=true, conn=connected, autostart=true, alertOpen=true, sysEnabled=true, timeEnabled=true, cpu=37.2, mem=58.4`。验收截图以此为基准。

---

## 6. 动效（Motion）

| 元素 | 原型值 | GTK 映射 / 降级 |
|---|---|---|
| 导航激活底色 | `transition:background .15s ease` | GTK CSS `transition` 支持，保留 |
| iOS 开关 knob | `left .18s ease` + track `background .18s` | GTK 用 `Gtk.Switch` 自带动画；自绘则加 transition |
| 重连脉冲 | `livePulse 1s ease-in-out infinite`（连接点）| GTK CSS keyframes 有限，**降级**为静态点或简单 opacity 脉冲，标注漂移 |
| 实时 tick | JS 每 1s 模拟数据 | 真实应用由 supervisor 推 `data` 事件驱动，**不模拟** |
| reduced-motion | 原型未定义 | 跟随系统 |

---

## 7. 交互逻辑（Interaction）

- 侧栏点击 → `Gtk.Stack` 切页 + 顶栏标题/副标题更新 + 导航激活态。
- 概览主按钮 → `on_start` / `on_stop`（沿用 supervisor）。
- 告警 × → 关闭该 notice（对应 `notices` 项消除/忽略）。
- 自启开关 → `on_autostart`（已与托盘联动，阻塞信号防回环，**保留**）。
- provider 开关 → `on_set_provider(pid, bool)`，断连时禁用。
- 间隔 ± → 按档位移动后 `on_set_interval(topic, seconds)`，断连时禁用。
- 所有「别处改了再同步回来」的回写须**阻塞信号防回环**（沿用现有 `_sync_switch/_sync_interval/set_autostart_active`）。

---

## 8. 数据 / 内容规则

- 断连占位符统一「—」。最近更新「刚刚」/「已暂停」。
- 数值格式：端口纯数字 mono；运行时长 `fmtUptime`；间隔 `fmtIv`+s；CPU/MEM 一位小数 + `%`；时间 `HH:MM:SS`。
- 文案过长（provider 描述、告警描述）允许换行（`set_line_wrap`）。
- 中文为主，UI 标签全中文，技术 key（`system.cpu`/`provider · time`）保留英文 mono。

---

## 9. 模块边界与独立测试

- **展示模块**：`OverviewPage` / `DataSourcesPage` / `WidgetsPage`（新）+ 侧栏 `Sidebar` + 顶栏 `TopBar` + 外壳 `MainWindow`。仅经回调/`update()` 接收数据，不直接调 supervisor。
- **样式模块**：`manager/theme.py`（新）—— 集中 `CssProvider` 加载 token CSS（建议外置 `manager/assets/style.css`）。可独立加载校验（解析不报错）。
- **状态/服务**：`CoreSupervisor`（已存在）—— 不改，继续经 `on_state/on_event` 通知 UI。
- **组合边界**：`ManagerApp.do_activate()` —— 唯一接线处。
- **独立测试**：
  - 展示：构造各 page，调 `update(假status)` / `set_connection(state)`，断言 Label 文本/可见性（无需真 supervisor）。沿用 `tests/` 现有风格（88 passing）。
  - 主题：加载 CSS 不抛错。
  - 服务：supervisor 既有测试不动。

---

## 10. 风险登记（Risk register）

1. **GTK3 CSS ≠ Web CSS**：无 flexbox / `--var` / 部分 `box-shadow`。布局全部靠 GTK Box；阴影/脉冲可能降级。→ 标注为已知漂移，不算失败。
2. **字体 Inter / JetBrains Mono 未必安装**：回退 system-ui / monospace。视觉会轻微偏移。需确认是否随包安装字体或接受回退。
3. **sparkline 折线**：GTK 无原生，需 `Gtk.DrawingArea` 自绘。列为低优先，首版可省略，标注漂移。
4. **iOS 风开关**：可用 `Gtk.Switch`（主题色未必是 brand 蓝）或自绘 `DrawingArea`。首版用 `Gtk.Switch` + CSS 着色，标注与原型 40×22 尺寸的差异。
5. **假窗口/红绿灯不复刻**：真实窗口用系统标题栏。属有意取舍，非漂移。
6. **中性灰阶（neutral-100..400）** 原型未在 `:root` 给值，按 Tailwind 灰阶推断，标注 `推断`。
7. **无法在本机看实时渲染时**：以截图路径 + 区域文字描述回报（§见 skill「无实时预览」）。

---

## 11. 实现切片（Slices，每片结束须可构建 + 验证）

1. **主题层**：`manager/assets/style.css` + `theme.py` 加载 `@define-color` 与基础类；窗口 1040×680、画布底色。验证：启动不报错、整体配色变浅蓝。
2. **外壳层**：`Notebook` → 侧栏(`Sidebar`) + `Gtk.Stack` + 顶栏(`TopBar`)。验证：三页可切、标题随页变、导航激活态。
3. **概览页**：状态横幅 + 4 metric 卡 + 设置卡，接旧回调与 `update/set_connection`。验证：connected/disconnected 两态截图。
4. **数据源页**：provider section 卡 + topic 行（值/进度条/badge/开关/步进器/最近更新），间隔改档位。验证：connected/disconnected、provider 开/关截图。
5. **小组件页**：空状态 + 3 预览卡。验证：截图。
6. **动效与收尾**：导航/开关过渡、（可选）脉冲、sparkline 评估。验证：交互录屏或分态截图。

每片后跑 `pytest` 并截图（`docs/screenshots/`），漂移回写本文件 §12。

## 12. 漂移记录（编码阶段追加）

### 漂移修复轮次 1（2026-06-23，用户实机反馈「中间指标卡没对齐原型」）
- **区域**：概览页 4 张 metric 卡（§4）。
- **症状**：卡片高度固定 104px 且用 `set_margin_*(16)`（GTK 外部 margin，非内边距），导致内容只占上 ~60%、底部大片留白；原型卡为紧凑、内容随高度填满。
- **责任层**：layout / token。
- **修复**：新增 `.mw-metric-card { padding:16px }`（内边距走 CSS）；卡片去掉 `set_size_request(-1,104)`、外部 margin、子项固定高，改 `valign=START` 随内容自然撑开（约 96px，贴合原型）。
- **证据**：原型 playwright 实渲 vs 现行离屏渲染并排比对（scratchpad/cmp-fixed.png），中段已对齐;`docs/screenshots/manager-overview.png` 已更新;`pytest` **114 passed**。
- 验证手段升级:本轮用 **playwright + google-chrome 实渲原型 HTML** 作为像素级正解(`scratchpad/proto-render.png`),不再仅凭目测。

实现已落地。新增/改动文件:
- `manager/theme.py`、`manager/assets/style.css`、`manager/assets/fonts/{Inter,JetBrainsMono}.ttf`(切片 1)
- `manager/widgets/draw.py`(PillSwitch / MeterBar / Sparkline / PulseDot / IntervalStepper,全 Cairo 自绘)
- `manager/shell.py`(Sidebar / TopBar / MainShell,切片 2)
- `manager/pages/overview.py`(重写,切片 3)、`manager/pages/datasources.py`(重写,切片 4)、`manager/pages/widgets.py`(新,切片 5,删除 widgets_placeholder.py)
- `manager/app.py`(Notebook→MainShell、1040×680、theme.apply、_on_state/_on_event 路由经 shell)
- 测试:`tests/test_manager_smoke.py`(spin→stepper、widgets 导入);`pyproject.toml`(package-data 加 css/fonts)

剩余漂移(诚实记录,均为有意取舍或低影响):
| 区域 | 项 | 目标(原型) | 实际 | 责任层/说明 |
|---|---|---|---|---|
| 外壳 | 假窗口 + 红绿灯 | 浏览器内画的 1040×680 假窗口 | 不复刻,用真实系统标题栏 | 有意(§10 风险 5) |
| 图标 | 线性图标 | 原型自定义 SVG 线条图标 | 用 GTK symbolic 图标近似(view-grid / network-server / view-app-grid / computer / alarm / emblem-ok 等) | 组件层,字形略异;低影响 |
| 阴影 | 卡片柔和投影 | `0 6px 18px rgba(...)` 多层 | GTK 单层 box-shadow 渲染,观感接近 | token 层;GTK 限制,可接受 |
| 像素 | 间距微调 | 原型逐 px | 按 token 还原,未做逐像素 ghost-overlay 比对 | 低优先;主结构/配色已对齐 |
| 图标 | icon tile 彩色底 | 原型 tile 有状态色底 | 已按 brand/success/warning/neutral 加浅色底;连接态图标用本机存在的 symbolic 图标近似 | GTK 图标主题与原型 SVG 字形不同;低影响 |

2026-06-23 像素校准追加:
- 概览状态横幅去掉外层 `.mw-card` 包裹,改为彩色横幅直接挂载页面,匹配原型层级。
- `mw-icon-tile` 增加 brand/success/warning/neutral 状态底色与图标前景色。
- 小组件空状态恢复为白色大卡片容器 `.mw-empty-card`,预览卡维持虚线卡。
- 截图重生成为固定 1040×680 离屏渲染,主态使用原型基准数据:port=8765、clients=2、uptime=2h、CPU=37.2%、MEM=58.4%、notice=config_reset。

自绘高保真项(用户要求,已落地,无降级):iOS 风开关 40×22 + .18s 缓动、阈值色进度条、迷你折线(含浅色填充)、重连脉冲环。字体随包(Inter + JetBrains Mono)已装并生效。

## 13. 验收检查（Acceptance）

验证方式:离屏渲染(`Gtk.OffscreenWindow`,真实 GTK/CSS/字体栈 + 仿真 status)逐态截图;`pytest` 全量;真实 `manager.app` 导入 + 部件树构建 + `_on_state`/`_on_event` 路由跑通(GUI 常驻进程受工具沙箱限制无法长驻,故以构建+路由验证替代)。

- [x] 窗口 1040×680，浅蓝画布，侧栏 220px + 主列，无顶部标签页。
- [x] 侧栏品牌行 + 三导航（含计数/「即将」badge）+ 底部状态点。
- [x] 顶栏三页标题/副标题正确，右侧连接 chip 三态配色。
- [x] 概览：横幅(连接=success/断开=neutral)、4 卡数值与断连「—」、设置卡两行 + 自启开关。
- [x] 数据源：System(cpu/mem)+Time section、badge(运行中/已停用)、PillSwitch、进度条阈值色(CPU>60 橙/内存紫)、档位步进、断连置灰 + 「—」/「已暂停」、sparkline(≥2 点)。
- [x] 小组件：空状态 + 3 虚线预览卡(CPU 仪表 / 内存条 / 时钟)。
- [x] 旧回调/数据流/防回环全部保留,`pytest` **108 passed**。
- [x] 截图覆盖存 `docs/screenshots/`:manager-overview{,-disconnected}.png、manager-datasources{,-disconnected}.png、manager-widgets.png。

验证命令:`.venv/bin/python -m pytest -q` → 108 passed。
