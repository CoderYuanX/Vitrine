# 桌面小组件管理器 — 架构设计

> 配套 UI 规格:`docs/design-specs/2026-06-21-widget-manager-ui.md`(视觉真相)。
> 本文是架构真相:进程模型、模块、数据流、迁移。

## 1. 定位

`~/Desktop/managewidgets` 是一个顶层 PySide6 + QML 桌面应用。**管理器是主体**,桌面小组件(时钟等)是它下面的子项。一个进程同时:渲染管理界面、按配置生成并拥有所有桌面卡片窗口、持久化。原 `~/Desktop/widgets` 的"宿主"运行时代码被吸收进来(原仓库保留作历史)。

## 2. 决策记录(brainstorming 确认)

- 技术栈:PySide6(Qt6.8)+ QML 原生。
- 进程模型:**单进程、一个 App 拥有全部**(管理界面窗口 + 桌面卡片子窗口 + 运行时)。
- 联动:同进程内存直调,实时生效,**不需要文件监听/IPC**。
- 项目位置:`~/Desktop/managewidgets`(把 widgets 代码搬入)。
- v1 功能:开关组件、画廊浏览、每组件设置、控制 App(设置面板)。
- 画廊预览:**实时 QML 缩略**(Loader 加载真实组件 QML)。
- 原 widgets 仓库:保留。

## 3. 目录结构

```
managewidgets/
├── main.py                    # 入口:单实例锁 → ManagerApp().run()
├── requirements.txt           # PySide6 / psutil / requests / python-xlib
├── src/manager/
│   ├── app.py                 # ManagerApp:QApplication + 运行时 + 托盘 + 管理窗口
│   ├── runtime.py             # WidgetRuntime(原 WidgetHost):扫描/生成卡片/显隐/持久化
│   ├── registry.py            # 扫 widgets/*/widget.json(原样搬入)
│   ├── config_store.py        # ~/.config/deepin-widgets/config.json(原样搬入)
│   ├── catalog_bridge.py      # ★新:管理界面 ↔ 运行时/配置 的 QObject 桥
│   ├── layout_bridge.py       # 卡片自身 x/y/zoom 持久化(原 bridge.py)
│   ├── tray.py / single_instance.py / x11.py   # 原样搬入,tray 激活"管理面板"项
├── ui/
│   ├── Manager.qml            # 主窗(=主卡片):标题栏 + 侧栏 + 网格
│   ├── TitleBar.qml / Sidebar.qml / NavItem.qml / GalleryCard.qml
│   └── previews/              # 各组件画廊预览(或直接 Loader 真实组件)
├── widgets/Clock/             # widget.json + Clock.qml(原样搬入)
├── tests/                     # config_store / registry / catalog_bridge 纯逻辑单测
└── docs/
    ├── design-specs/2026-06-21-widget-manager-ui.md
    └── superpowers/specs/2026-06-21-widget-manager-design.md
```

## 4. 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| **ManagerApp** (app.py) | 顶层。透明 surface format、`quitOnLastWindowClosed=False`、SIGINT;起运行时、装托盘、托管管理窗口;把 CatalogBridge 注入 Manager.qml | 运行时、托盘、桥 |
| **WidgetRuntime** (runtime.py) | 原 WidgetHost 改名。扫注册表→按 config 为启用组件建 QML 卡片窗口(每卡片独立 engine);`show_widget(id)`/`hide_widget(id)`/`is_shown(id)`;每卡片应用 X11 EWMH | registry、config_store、layout_bridge、x11 |
| **WidgetRegistry** | 扫 `widgets/*/widget.json`(id/名/分类/qml/预览/默认设置);**新增 category 字段**;**新增 implemented 标记**(区分"即将推出") | — |
| **ConfigStore** | 读写 config.json,per widget enabled/x/y/zoom + 设置 | — |
| **CatalogBridge** (新) | 管理界面唯一数据源。暴露:分类列表、组件列表(id/名/分类/enabled/implemented/预览源)、`setCategory(k)`、`toggle(id,on)`、`getSetting/setSetting`、全局操作(全部显隐/退出/自启) | runtime、config_store、registry |
| **LayoutBridge** | 卡片回存 x/y/zoom(沿用) | config_store |
| **Tray** | "打开管理面板"(激活原占位)+ 退出 | — |

## 5. 数据流

- **启动**:锁 → 运行时扫注册表、读 config、为启用组件建卡片(时钟)→ 装托盘 → 管理窗口默认隐藏,托盘点开。
- **画廊开关**:Manager.qml → `CatalogBridge.toggle(id,on)` → 运行时显/隐卡片 + ConfigStore 落盘 → 桌面实时变。
- **分类筛选**:Manager.qml → `CatalogBridge.setCategory(k)` → 桥更新可见组件列表 → QML 重新过滤网格(纯前端 model 过滤,无副作用)。
- **卡片拖动/缩放**:卡片经 LayoutBridge 自存(沿用)。
- **每组件设置 / 全局设置**:`setSetting` → 落 config +(若卡片在显示)推给活动卡片。
- **真实数据**:时钟每秒、系统每 2.5s,由各 Provider 提供(替换原型随机数);Provider 为后续组件实现时引入。

## 6. 错误处理

- config 损坏 → ConfigStore 回退(已有);坏 widget.json → registry 跳过(已有)。
- 组件 QML 加载失败 → 运行时/Loader 按卡片捕获,画廊标"加载失败",不拖垮 App。
- X11 EWMH 仅 xcb 平台执行(已有)。
- 二次启动 → 唤起已有管理窗口再退出(改进现状的直接退出)。

## 7. 测试策略

- 沿用:`config_store`、`registry` 纯逻辑单测。
- 新增:`catalog_bridge` 单测 —— 分类→show 映射、`toggle` 翻转 enabled + 落 config + 调运行时(用假运行时注入验证);设置读写。
- registry 新字段(category/implemented)解析测。
- QML 视觉:运行管理器截图,与原型逐区对比(见 UI 规格 Acceptance）。

## 8. 迁移步骤(widgets → managewidgets)

1. `managewidgets` git init。
2. 搬 `src/`(包名 `widgets_host`→`manager`,`WidgetHost`→`WidgetRuntime`)、`widgets/`、`tests/`、相关 docs。
3. registry 加 `category` / `implemented` 字段;Clock 的 widget.json 补 `category: clock`。
4. 新增 `catalog_bridge.py`、`ui/*.qml`、改 `app.py`(托管管理窗口 + 注入桥)、`tray.py`(激活管理面板项)。
5. 原 `~/Desktop/widgets` 不动,作为历史参考。

## 9. 范围边界(YAGNI)

- v1 不做:窗口可调整大小、天气/日历/系统/便签/启动器的真实实现(占位"即将推出")、毛玻璃、Wayland 置底。
- 注意:桌面卡片"置底常驻"仍是既有未解问题(见原 widgets README),不在本次 UI 工作范围,但迁移后继承该技术债。
