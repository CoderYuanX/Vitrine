import QtQuick
import QtQuick.Window

// 日历仪表盘组件根窗口。折叠=紧凑卡;展开=完整仪表盘。
// 几何/缩放经 layout 桥持久化(与 Clock 一致)。
Window {
    id: root
    property string widgetId: "calendar"
    property bool expanded: false
    property real zoom: 1.0

    // 折叠态(卡片)的持久化"主"位置;展开时窗口居中,不改这两个值
    property int cardX: 80
    property int cardY: 80
    property bool _restoring: false   // 程序化定位期间不持久化

    // 实时数据
    property var now: new Date()
    property int curYear: now.getFullYear()
    property int curMonth: now.getMonth()
    property int curToday: now.getDate()
    property int selectedDay: now.getDate()

    property string ampm: Qt.formatTime(now, "AP")
    property string timeText: Qt.formatTime(now, "h:mm AP").replace(" " + Qt.formatTime(now, "AP"), "")
    property string dateLong: Qt.formatDate(now, "dddd, MMM d")
    property string dateShort: Qt.formatDate(now, "ddd, MMM d")

    // 折叠/展开基准尺寸
    readonly property int baseW: expanded ? 1150 : 296
    readonly property int baseH: expanded ? 652 : 172

    width: Math.round(baseW * zoom)
    height: Math.round(baseH * zoom)
    visible: true
    color: "transparent"
    title: "deepin-widget-calendar"
    flags: Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus

    // 演示任务模型(可切换 done,会话内)
    ListModel { id: taskStore }

    function persist() { layout.saveState(widgetId, root.cardX, root.cardY, root.zoom) }

    // 按当前折叠/展开态摆放窗口:展开=屏幕居中;折叠=卡片主位置
    // 用 baseW/baseH(随 expanded 立即生效)算尺寸,避免读到滞后的 root.width 导致右偏
    function applyPosition() {
        _restoring = true
        if (expanded) {
            var w = Math.round(baseW * zoom)
            var h = Math.round(baseH * zoom)
            root.x = Math.round((Screen.width  - w) / 2) + Screen.virtualX
            root.y = Math.round((Screen.height - h) / 2) + Screen.virtualY
        } else {
            root.x = cardX
            root.y = cardY
        }
        _restoring = false
    }
    // 立即定位一次,并在尺寸变化落定后(KWin resize)再居中一次兜底
    onExpandedChanged: { applyPosition(); Qt.callLater(applyPosition) }

    Component.onCompleted: {
        var p = layout.getState(widgetId).split(",")
        root.cardX = parseInt(p[0]); root.cardY = parseInt(p[1])
        root.zoom = parseFloat(p[2]) || 1.0
        applyPosition()
        var T = demoTasks.list
        for (var i = 0; i < T.length; i++)
            taskStore.append({ text: T[i].text, tag: T[i].tag, tc: T[i].tc, tb: T[i].tb, done: false })
    }

    // 拖动后(系统移动)防抖保存位置;只在折叠态、非程序化定位时记录卡片主位置
    Timer { id: saveTimer; interval: 350; onTriggered: root.persist() }
    function onMoved() {
        if (_restoring || expanded) return
        cardX = root.x; cardY = root.y
        saveTimer.restart()
    }
    onXChanged: onMoved()
    onYChanged: onMoved()

    // 每秒刷新实时数据
    Timer {
        interval: 1000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: root.now = new Date()
    }

    QtObject {
        id: demoTasks
        property var list: [
            { text: "Prepare project proposal", tag: "Work",     tc: "#7c3aed", tb: "rgba(124,58,237,.12)" },
            { text: "Reply to client emails",   tag: "Work",     tc: "#7c3aed", tb: "rgba(124,58,237,.12)" },
            { text: "Buy groceries for dinner", tag: "Personal", tc: "#16a34a", tb: "rgba(22,163,74,.12)" }
        ]
    }

    // 缩放后的内容画布(整卡缩放,与 Clock 一致)
    Item {
        id: canvas
        width: root.baseW
        height: root.baseH
        scale: root.zoom
        transformOrigin: Item.TopLeft

        WheelHandler {
            objectName: "zoomWheel"
            enabled: !root.expanded   // 展开=固定仪表盘,禁止滚轮缩放;仅折叠卡可缩放
            onWheel: function (ev) {
                var step = ev.angleDelta.y > 0 ? 0.06 : -0.06
                root.zoom = Math.max(0.6, Math.min(2.2, root.zoom + step))
                root.applyPosition()   // 缩放改变尺寸:展开态重新居中,折叠态保持卡片原位
                root.persist()
            }
        }

        // 折叠态紧凑卡
        CompactCard {
            visible: !root.expanded
            x: 20; y: 16
            winRef: root
            timeText: root.timeText
            ampm: root.ampm
            dateText: root.dateLong
            onExpandRequested: root.expanded = true
        }

        // 展开态仪表盘(Loader:每次展开重建以重播入场动画)
        Loader {
            id: dashLoader
            active: root.expanded
            visible: root.expanded
            x: 6; y: 6
            sourceComponent: Component {
                Dashboard {
                    year: root.curYear
                    month: root.curMonth
                    today: root.curToday
                    selectedDay: root.selectedDay
                    dateLabel: root.dateShort
                    tasksModel: taskStore
                    winRef: root
                    accent: "#2f6bff"
                    onDaySelected: function (d) { root.selectedDay = d }
                    onTodayClicked: root.selectedDay = root.curToday
                    onCloseClicked: root.expanded = false
                }
            }
        }
    }
}
