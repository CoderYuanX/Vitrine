# 桌面小组件管理器 — UI 设计规格

## Source Of Truth

- **Primary source**: `桌面小组件管理器.html`(bundler 打包),已解包为 `_unpacked/_template.html`(完整 HTML+内联样式)与 `_unpacked/_trailing.txt`(交互逻辑 `class Component`)。
- Secondary references: 缩略图 SVG(`桌面小组件管理器.html` 内 `__bundler_thumbnail`)。
- Current implementation: 无(管理界面尚未实现);桌面卡片侧已有 `~/Desktop/widgets` 的 Clock.qml 可复用。
- Spec file path: `docs/design-specs/2026-06-21-widget-manager-ui.md`
- **Source quality: HIGH**(显式 CSS 数值 + 完整交互逻辑,非截图推断)
- Extraction method: HTML/CSS(内联 style)
- Target platform: Linux 桌面(Deepin 25 / X11),PySide6 + QML
- Target stack: PySide6 6.8 + Qt Quick / QML
- Missing source states: 无 hover 截图(但 `style-hover` 属性给出了 hover 值);无"加载失败/空"状态(原型未涉及,需自定义)。
- Inferred values: 仅少量(见 Risk Register);绝大多数为源精确值。

## Development Contract

- This spec is the source of truth for implementation: **Yes**
- Code changes must map to: 本文件的 Tokens / Layout / Components / Interaction 小节。
- Out-of-scope changes: 桌面卡片本身的渲染逻辑(沿用既有 Clock.qml);后端运行时架构见 brainstorming 架构设计文档。
- Requirements needing confirmation before coding: 见末尾"待用户确认"。
- Last reviewed before coding: 待用户评审。

## Visual Intent

一个 macOS 风、明亮淡蓝的小组件管理面板:白色圆角主窗 + 大柔和投影,浮在淡蓝渐变背景上。左侧分类导航,右侧两列卡片网格。**每张卡片的卡身就是该组件的实时缩略预览**(时钟走秒、系统进度条跳动),卡片右上角一个圆形开关切换该组件在桌面上的启用/禁用。

> 重要语义:原型是一个静态 mock 窗口(模拟桌面背景里的一个应用窗)。我们的实现里,这就是管理器的主窗口;卡片上的开关真正控制桌面挂件的显示/隐藏。

## Layout

- **外层背景**(原型用,实现中是管理窗口的内容根):渐变 `linear-gradient(155deg,#cfe0fb 0%,#e4eefe 38%,#f4f8ff 100%)`,居中,padding 40px。实现时管理窗口本体即下面的"主卡片",外层渐变可作窗口背景或省略(窗口直接是主卡片)。
- **主卡片(窗口)**: `920 × 624` px,背景 `#ffffff`,圆角 `18px`,阴影 `0 24px 70px rgba(40,78,160,0.22), 0 2px 8px rgba(40,78,160,0.08)`,`overflow:hidden`,纵向 flex。
  - QML 适配:窗口本体设为该尺寸;若做无边框圆角窗,圆角+阴影由根 `Rectangle` 承载,窗口透明。**可调整大小**留待后续(原型为固定尺寸,v1 固定 920×624)。
- **标题栏**:高 `56px`,padding `0 18 0 20`,下边框 `1px #f1f3f7`。左:26px 圆角渐变图标(`linear-gradient(150deg,#5b9bff,#3b76f6)`,圆角 8,内含 4 格白色 svg,阴影 `0 2px 6px rgba(59,118,246,0.35)`)+ 标题"桌面小组件"(15px/600 #2b3344,letter-spacing 0.2)。右:最小化(横线)、关闭(×)按钮,各 30×30 圆角 8;最小化 hover bg `#f2f4f8`;关闭 hover bg `#ffeceb` 文字 `#ef4444`。
- **主体**:flex 1,横向 = 侧栏 + 内容区。
- **侧栏**:宽 `186px`,padding `14 12`,右边框 `1px #f1f3f7`,纵向 flex。顶部 6 个分类项,`flex:1` 撑开,底部"设置"项。
- **内容区**:flex 1,padding `18 20`,背景 `#fbfcfe`,`overflow-y:auto`;**CSS grid `grid-template-columns: 1fr 1fr`,gap `14px`,`align-content:start`**(两列卡片网格)。
- Spacing scale(高频):3 / 5 / 6 / 8 / 11 / 12 / 14 / 16 / 17 / 18 / 20 px。
- Responsive: v1 固定尺寸,不做响应式。

## Tokens

### Color
- Background(窗口外):渐变 `#cfe0fb→#e4eefe→#f4f8ff`
- Surface:主窗 `#ffffff`;内容区底 `#fbfcfe`;卡片 `#fff`(天气卡 `linear-gradient(160deg,#ffffff 60%,#f3f8ff)`)
- Text:主 `#222c43` / `#2b3344`;次 `#5b6472` / `#8a93a3`;弱 `#9aa4b4` / `#aab2c0` / `#b8c0cd`
- Accent(蓝):`#3b82f6`(开关/进度/日期数字);导航选中文字 `#2563eb`,选中底 `#e9f1fe`
- 进度条渐变:`linear-gradient(90deg,#60a5fa,#3b82f6)`
- Danger:`#ef4444`(关闭按钮 hover)
- Borders:`#f1f3f7`(分隔)/ `#eef1f6`(卡片边)
- 便签:底 `#fdf6d8` 边 `#f3e9bf` 文字 `#7a6f44`
- 开关 off 环:`#ced6e2`

### Typography
- Font family: `'PingFang SC','Microsoft YaHei',system-ui,-apple-system,sans-serif`(Deepin 上回退到思源/文泉驿,需指定中文字体)
- Sizes: 标题 15;导航 13.5;卡名 13;正文 12/12.5/13;弱注 10/10.5;时钟 46;天气温度 40;日历大日 38;日历月格 10.5
- Weights: 400 / 500(导航/便签)/ 600(卡名/标题/数值)/ 700(大数字)
- Line heights: 时钟 1;天气温度 1;日历大日 1.05;便签 1.7
- 数字:`font-variant-numeric: tabular-nums`(时钟),QML 用等宽数字字体或 `Font.tabularFigures`。

### Shape And Effects
- Radius: 窗 18;卡片 14;导航项/天气图标格 11;按钮/图标 8;启动器图标 12;进度条 3;日历今日圆点 50%
- Shadows: 窗 `0 24px 70px rgba(40,78,160,0.22)`;卡片静止 `0 1px 3px rgba(20,40,90,0.04)`;卡片 hover `0 6px 18px rgba(40,78,160,0.10)`;图标徽标 `0 2px 6px rgba(59,118,246,0.35)`
- Gradients: 见 Color
- Blur/glass: 无(纯不透明设计)

## Components

### TitleBar
- 用途:窗口标题 + 窗口控制(最小化/关闭)。
- 子:AppIcon、Title、Spacer、MinBtn、CloseBtn。
- 状态:按钮 hover 变底色;关闭 hover 红。
- 交互:最小化 → 隐藏管理窗口(回托盘);关闭 → 隐藏管理窗口(**非退出 App**,App 仍托管桌面卡片)。可拖动标题栏移动窗口。

### Sidebar / NavItem
- 用途:分类筛选。
- NavItem(全部/时钟/天气/日历/系统/便签):icon(17px line svg)+ 文字,padding `9 12`,radius 11,gap 11,13.5px/500,item 间 margin-bottom 3。
- 状态:选中 = bg `#e9f1fe` / fg `#2563eb`;未选 = bg transparent / fg `#5b6472`。未选 hover(源未给,**推断**):bg `#f4f6fa`(与"设置"项 hover 一致)。
- 底部"设置"项:fg `#8a93a3`,hover bg `#f4f6fa`。v1 行为:打开设置(占位或全局设置,见待确认)。

### ContentGrid
- 两列网格,gap 14,卡片按当前分类过滤显示(见 Interaction)。

### GalleryCard(核心,每组件一张)
- 用途:展示一个组件 + 启用开关 +**实时预览**。
- 容器:卡片样式(见 Tokens),padding `15 17`,hover 升起阴影。
- Header:卡名(13/600 #8a93a3)+ ToggleIcon(右上)。
- ToggleIcon:on = 实心蓝圆 `#3b82f6` + 白勾;off = 灰环 `#ced6e2`。20×20。点击切换该组件桌面启用状态。
- Body = **该组件的实时 QML 缩略预览**(用户已拍板"实时 QML 缩略")。每类预览内容:
  - **时钟**:`HH:MM`(46/700 #222c43,tabular)+ `M月D日 星期X`(13 #9aa4b4)
  - **天气**:温度 `26°`(40/700)、`北京 · 晴`(12.5 #8a93a3)、旋转太阳 svg(`wm-spin` 22s 线性无限)、`18°/28°  湿度40%`(12 #aab2c0)
  - **日历**:月标 `YYYY/MM`、大日(38/700 #3b82f6)、星期标、7列迷你月历(今日 = 蓝底白字圆点)
  - **系统**:CPU/内存/存储 三条进度(轨 `#eef1f6` 高5 radius3,填充蓝渐变,`width: N%`,CPU/内存 `transition width .6s`)
  - **便签**:黄色便签纸,文案多行
  - **快捷启动**(仅"全部"分类显示):3 个 46×46 圆角渐变图标(文件管理/浏览器/设置),hover 上移 2px
- Content rules:卡身预览复用真实组件 QML(`Loader`,裁剪缩放、不可交互);组件未实现时显示"即将推出"占位;加载失败显示"加载失败"占位(源未定义,**自定义**)。

## Architecture And Testability(UI 侧)

- **Presentation**:`ui/` 下 QML — `Manager.qml`(窗口=主卡片)、`TitleBar.qml`、`Sidebar.qml`、`NavItem.qml`、`GalleryCard.qml`、`previews/*.qml`(或直接 Loader 真实组件)。仅经 model/property 取数,不直接调服务。
- **State/Bridge**:`CatalogBridge`(QObject,Python)暴露:分类列表、组件列表(id/名/分类/enabled/预览源)、`setCategory`、`toggle(id,on)`、设置读写。承担原型 `class Component` 的 state(activeCat、enabled、now/cpu/mem)角色,但真实数据来自运行时/Provider。
- **Composition**:`app.py` 把 CatalogBridge 注入 Manager.qml 的 context。
- Tests:CatalogBridge 纯逻辑单测(分类过滤 show 映射、toggle 翻转 + 落 config + 调运行时);QML 视觉用截图验证。

## Motion
- 卡片 hover:阴影 `0 1px 3px…` → `0 6px 18px…`(过渡,推断 ~0.18s ease)。
- 天气太阳:`@keyframes wm-spin` 旋转 360°,22s linear infinite,transform-origin 中心。
- 进度条:`width` 变化 `transition .6s ease`(CPU/内存;存储无过渡)。
- 启动器图标 hover:`translateY(-2px)`。
- Reduced motion:可选关闭太阳旋转。

## Interaction Logic
- **分类点击**:`setCat(k)` → 内容区只显示该类卡片;`all` 显示全部 + 快捷启动。导航项高亮切换。
- **开关点击**:`toggle(id)` → 翻转 enabled → 桌面卡片实时显/隐 + 落 config(同进程内存直调)。开关图标 on/off 切换。
- 标题栏最小化/关闭 → 隐藏窗口(App 不退);标题栏拖动移动窗口。
- 窗口可由托盘"打开管理面板"唤起。
- 实时数据:时钟每秒、系统每 2.5s 刷新(真实数据来自 Provider,非原型的随机数)。

## Platform Translation(Web → QML)
- 源平台 Web(flex/grid + 内联 style);目标 QML。
- 用 QML 原语:`RowLayout`/`ColumnLayout`/`GridLayout`(对应 flex/grid)、`Rectangle`(卡片/圆角/边框)、`layer.effect`+`DropShadow`(MultiEffect on Qt6)做阴影、`Repeater`(日历格/网格)、`Shape`/`Canvas` 或预渲染 SVG 图标。
- 避免:HTML 特有的 `box-shadow` 直译——QML 用 `MultiEffect`/`DropShadow`;hover 用 `HoverHandler`。
- 与源差异:桌面缩放(DPI)会放大固定 px——QML 用逻辑像素,注意 Deepin 缩放;X11/Wayland 阴影/透明差异(本机 X11)。
- 截图验证:用 webapp-testing 不适用;改用 QML 窗口截图(运行管理器截图 / `grabToImage`)。

## Visual Drift Risk Register
- **推断值**:未选导航项 hover 底色 `#f4f6fa`(类比设置项);卡片 hover 过渡时长 ~0.18s;"加载失败/即将推出"占位样式自定义。
- **缺失状态**:组件未实现的占位、加载失败、空分类。
- **保真风险**:阴影在 QML(MultiEffect)与 CSS 观感差异;中文字体在 Deepin 与 PingFang 字形差异;SVG 图标需逐个复刻为 QML Shape 或位图。
- 可接受容差:阴影/字体的细微差;颜色/尺寸/布局需精确。

## Acceptance Checks
- 截图主窗与原型并排逐区对比:标题栏、侧栏选中态、两列网格、各卡片预览、开关 on/off。
- CatalogBridge 单测:分类过滤、toggle 落 config + 调运行时。
- 手动:点分类切换筛选、点开关桌面卡片实时显隐、最小化/关闭不退 App、托盘唤起。

## 已确认决策(2026-06-21,用户拍板)
1. **窗口形态**:✅ 无边框自绘标题栏,完全复刻原型(自己画最小化/关闭、圆角、投影、拖动移窗)。
2. **画廊内容**:✅ 列全部 6 类;时钟可用,其余(天气/日历/系统/便签/快捷启动)灰显标"即将推出"占位。
3. **"设置"项**:✅ 做全局设置面板 —— 开机自启开关、全部显/隐、退出 App、运行状态(即第一轮"控制宿主"能力的落地点)。
4. **窗口尺寸**:✅ v1 固定 920×624,不可调整大小(留后续)。

### "即将推出"占位卡样式(自定义,源未定义)
- 沿用卡片容器(白底/边 #eef1f6/圆角14/padding 15·17),但整卡 `opacity ~0.6`、不可 hover 升起。
- Header:卡名正常 + 右上角不显示开关(或显示禁用态灰环,不可点)。
- Body:居中弱注"即将推出"(13 #aab2c0)。
