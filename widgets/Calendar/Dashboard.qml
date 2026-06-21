import QtQuick
import QtQuick.Window

// 展开仪表盘容器(grid 布局,固定像素复刻原型)。
// 列 252/238/238/290,行 188/200/192,gap 14,容器 padding 16,圆角 26。
Item {
    id: root
    property int year: 2025
    property int month: 4
    property int today: 20
    property int selectedDay: 20
    property string selectedIso: ""    // 选中日 ISO(YYYY-MM-DD),供事件读写
    property string todayIso: ""       // 今日 ISO,供 Upcoming 取未来事件
    property string timeText: "10:28"
    property string ampm: "AM"
    property string dateLabel: "Tue, May 20"
    property string fullDateLabel: "Tuesday, May 20"
    property var tasksModel
    property var winRef: null          // 宿主 Window 引用(用于 startSystemMove)
    property color accent: "#2f6bff"
    signal daySelected(int day)
    signal todayClicked()
    signal prevMonth()
    signal nextMonth()
    signal closeClicked()

    readonly property int pad: 16
    readonly property int gap: 14
    // 列 x / 行 y(相对内容区)
    readonly property int c0: 0
    readonly property int c1: 252 + gap
    readonly property int c2: c1 + 238 + gap
    readonly property int c3: c2 + 238 + gap
    readonly property int r0: 0
    readonly property int r1: 188 + gap
    readonly property int r2: r1 + 200 + gap
    readonly property int contentW: 252 + 238 + 238 + 290 + 3 * gap   // 1060
    readonly property int contentH: 188 + 200 + 192 + 2 * gap          // 608

    implicitWidth: contentW + 2 * pad
    implicitHeight: contentH + 2 * pad

    // popIn 整容器入场
    opacity: 0
    scale: 0.9
    transform: Translate { id: pop; y: 18 }
    Component.onCompleted: popAnim.start()
    ParallelAnimation {
        id: popAnim
        NumberAnimation { target: root; property: "opacity"; to: 1; duration: 460; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "scale";   to: 1; duration: 460; easing.type: Easing.OutCubic }
        NumberAnimation { target: pop;  property: "y";       to: 0; duration: 460; easing.type: Easing.OutCubic }
    }

    // 入场:popIn(整容器) + cardRise(各卡错峰)
    component Rising: Item {
        id: ri
        property int delay: 0
        opacity: 0
        scale: 0.97
        transform: Translate { id: tr; y: 20 }
        Component.onCompleted: anim.restart()
        SequentialAnimation {
            id: anim
            PauseAnimation { duration: ri.delay }
            ParallelAnimation {
                NumberAnimation { target: ri; property: "opacity"; to: 1; duration: 520; easing.type: Easing.OutCubic }
                NumberAnimation { target: tr; property: "y"; to: 0; duration: 520; easing.type: Easing.OutCubic }
                NumberAnimation { target: ri; property: "scale"; to: 1; duration: 520; easing.type: Easing.OutCubic }
            }
        }
    }

    // 展开容器
    Rectangle {
        anchors.fill: parent
        radius: 26
        color: "#fbfcfe"
        border.width: 1
        border.color: "#eef1f6"

        // 从容器留白处拖动移动窗口
        DragHandler {
            target: null
            onActiveChanged: if (active && root.winRef) root.winRef.startSystemMove()
        }

        Item {
            id: content
            x: root.pad; y: root.pad
            width: root.contentW; height: root.contentH

            Rising { x: root.c0; y: root.r0; width: 252; height: 188; delay: 100
                WeatherCard { anchors.fill: parent
                    weatherSource: (typeof weather !== "undefined") ? weather : null
                    timeText: root.timeText
                    ampm: root.ampm
                    dateText: root.fullDateLabel
                } }

            Rising { x: root.c0; y: root.r1; width: 252; height: 200 + root.gap + 192; delay: 180
                TasksCard { anchors.fill: parent; todayModel: root.tasksModel; accent: root.accent } }

            Rising { x: root.c1; y: root.r0; width: 238 + root.gap + 238; height: 188 + root.gap + 200; delay: 140
                CalendarCard {
                    anchors.fill: parent
                    year: root.year; month: root.month; today: root.today
                    selectedDay: root.selectedDay; accent: root.accent
                    onDaySelected: function(d) { root.daySelected(d) }
                    onTodayClicked: root.todayClicked()
                    onPrevMonth: root.prevMonth()
                    onNextMonth: root.nextMonth()
                } }

            Rising { x: root.c3; y: root.r0; width: 290; height: 188 + root.gap + 200; delay: 200
                AgendaCard {
                    anchors.fill: parent
                    year: root.year; month: root.month; day: root.selectedDay
                    selectedIso: root.selectedIso; dateLabel: root.dateLabel; accent: root.accent
                } }

            Rising { x: root.c1; y: root.r2; width: 238; height: 192; delay: 260
                ProductivityCard { anchors.fill: parent; accent: root.accent } }

            Rising { x: root.c2; y: root.r2; width: 238; height: 192; delay: 300
                UpcomingCard { anchors.fill: parent; accent: root.accent; todayIso: root.todayIso } }

            Rising { x: root.c3; y: root.r2; width: 290; height: 192; delay: 280
                LunarCard { anchors.fill: parent } }
        }
    }

    // 关闭按钮
    Rectangle {
        anchors.right: parent.right; anchors.rightMargin: 12
        anchors.top: parent.top; anchors.topMargin: 12
        width: 30; height: 30; radius: 8
        color: closeMA.containsMouse ? "#ffeceb" : "transparent"
        Text { anchors.centerIn: parent; text: "×"; color: closeMA.containsMouse ? "#ef4444" : "#9aa4b4"; font.pixelSize: 15; font.weight: Font.Bold }
        MouseArea {
            id: closeMA; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; onClicked: root.closeClicked()
        }
    }
}
