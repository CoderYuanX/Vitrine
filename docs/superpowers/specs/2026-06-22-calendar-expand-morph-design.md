# 日历组件 展开/折叠 几何形变动画 — 设计

日期:2026-06-22
文件:`widgets/Calendar/Calendar.qml`(仅此一处;`Dashboard.qml` 不改)

## 问题

从折叠卡片展开为仪表盘时:

1. **跳变** — 小卡先"瞬移到屏幕中央",再"撑大"成仪表盘;折叠反之。
2. **无动画** — 展开/折叠都是硬切,没有过渡。

### 根因

`Calendar.qml` 中窗口几何完全由 `expanded` 瞬时驱动,且分多步互不协调:

- `width`/`height` 绑定到 `baseW*zoom`(296↔1150)/`baseH*zoom`(172↔652),绑定一变窗口**立即**改尺寸。
- `onExpandedChanged` 调 `applyPosition()` 把窗口移到屏幕中心,**并再 `Qt.callLater(applyPosition)` 居中一次**(`Calendar.qml:80-83`)。

移动 + 改尺寸 + 二次居中分帧落地 → 肉眼可见的两步跳变。`width/height` 无 `Behavior`、`x/y` 直接赋值 → 无任何动画。

## 关键约束(防残影)

提交 `844ed7d`、注释 `Dashboard.qml:43-44`、测试 `test_dashboard_does_not_fade_or_stagger_during_window_resize` 共同记录了一段历史:**在窗口 resize 期间对仪表盘容器做 opacity 淡入 / scale 缩放,会在 KWin 透明桌面窗口上留下大块半透明残影**,已被刻意移除。

→ 本次**不得**对内容容器做透明度动画。`Dashboard.qml` 保持不动。

## 方案(Approach A:窗口几何形变)

### 1. 几何过渡(Behavior + `_animating` 门控)

- 新增 `property bool _animating: false`、`readonly property int _morphMs`(≈280)。
- 给 `x` / `y` / `width` / `height` 各加 `Behavior { enabled: root._animating; NumberAnimation { duration: _morphMs; easing.type: Easing.OutCubic } }`。
- `width`/`height` 仍是 `baseW*zoom`/`baseH*zoom` 绑定 —— `expanded` 翻转 → 目标值变 → Behavior 自动插值。
- `x`/`y` 在过渡时由定位函数赋目标值(展开=屏幕居中;折叠=`cardX/cardY`),Behavior 插值。
- **仅 `_animating` 为真时启用 Behavior**:拖动(`startSystemMove`)、滚轮缩放、启动初始定位均保持瞬时,不被动画拖慢。

### 2. 消除跳变

- 删除 `onExpandedChanged` 里的 `Qt.callLater(applyPosition)` 二次居中。
- 新增 `expand()` / `collapse()`:**先 `_animating = true`,再翻 `expanded`**,保证几何变化一开始就走 Behavior 而非硬切。
  - `CompactCard.onExpandRequested → root.expand()`
  - `Dashboard.onCloseClicked → root.collapse()`
- `onExpandedChanged`:计算并赋目标 `x/y`(单次,不再 callLater),并 `morphEnd.restart()`。
- `Timer morphEnd`(interval `_morphMs + 60`)触发后 `_animating = false`。
- `onMoved()` 持久化守卫增加 `_animating`:`if (_restoring || expanded || _animating) return`,防动画途中把居中坐标误存为 `cardX/cardY`。

### 3. 内容跟随(保守版,防残影)

- `canvas` 保持全尺寸、全不透明,`scale` 仍只跟 `zoom`,**不做 opacity 动画**。
- 窗口长大时逐步"揭开"完整仪表盘 + 滑向中央 = 窗口框真·形变;内容无透明度动画 → 规避 `844ed7d` 残影坑。
- 实测无残影且需要更强"生长"感时,可后续追加 `canvas` 的纯 `scale` 跟随(仍无 opacity)。

## 测试

- 保留现有 `test_calendar_zoom.py` / `test_calendar_expanded_style.py`。
- 新增离屏加载测试:
  1. `expand()` 后 `expanded === true`、`collapse()` 后 `=== false`;
  2. `Calendar.qml` 源码不再含 `Qt.callLater(applyPosition)`;
  3. 存在受 `_animating` 门控的几何 `Behavior`(源码断言 `enabled: root._animating`)。

## 验证

实现后实际运行截图,确认:展开/折叠平滑、无"先居中再展开"跳变、无 KWin 残影、拖动/缩放未被动画拖慢。

---

## 实施结果与最终决策(2026-06-22 更新)

原计划的「窗口几何形变动画」以及后续两种替代方案,在本机 Deepin/KWin 上都**闪烁**,实测结论:

| 方案 | 结果 |
|---|---|
| 动画窗口 x/y/w/h(Behavior) | 逐帧 resize 透明窗口 → 闪 |
| 内容飞入(窗口铺满并集 + canvas scale/平移) | 仪表盘整块逐帧时隐时现 → 闪 |
| `QSG_RENDER_LOOP=basic` | 仍闪 |
| `QT_QUICK_BACKEND=software` | 录屏里不闪,但**整进程 CPU 渲染**会让管理器 `MultiEffect` 阴影失效、且略卡,不可接受 |

**根因**:Deepin/KWin 合成器对「无边框透明桌面窗口的逐帧动画」支持很差(窗口动画期短暂变透明 → 内容闪),属平台限制,App 层无法可靠绕过(Qt 文档/社区一致)。

**最终决策(用户拍板):放弃展开/折叠过渡动画,采用「瞬时切换」。** 但保留本轮排查出的三处真修复:

1. **居中正确、无"先居中再展开"跳变** —— `applyGeom()` 用 `expandedW/expandedH` 直接算中心(绕开 `baseW/baseH` 绑定滞后一帧),并删除 `Qt.callLater` 二次居中;
2. **展开无空白填充** —— Dashboard 的 `Loader` 改为常驻预热(`active: true`),不再每次展开重建(避免内部 `Rising` 错峰淡入重放);
3. **绝不闪** —— 无任何逐帧窗口/内容动画。

`main.py` 不再需要 `QSG_RENDER_LOOP`,已还原。
