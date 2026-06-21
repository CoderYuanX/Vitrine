import QtQuick
import QtQuick.Layouts
import "CalendarModel.js" as Cal
import "DemoData.js" as Demo

// 月历卡(grid-area:cal)。真实当月网格 + 今日高亮 + 选中 + Today。
Rectangle {
    id: card
    property int year: 2025
    property int month: 4          // 0-11
    property int today: 20         // 今日日数字(仅当月)
    property int selectedDay: 20
    property color accent: "#2f6bff"
    property var calendarInfoSource: null
    property int rev: 0                 // 事件变更计数,驱动圆点重算
    signal daySelected(int day)
    signal todayClicked()
    signal prevMonth()
    signal nextMonth()

    Connections {
        target: (typeof events !== "undefined") ? events : null
        ignoreUnknownSignals: true
        function onChanged() { card.rev++ }
    }

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 18; anchors.rightMargin: 18
        anchors.topMargin: 16; anchors.bottomMargin: 16
        spacing: 0

        // 标题行
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: card.year + "年" + (card.month + 1) + "月"
                font.pixelSize: 20; font.weight: Font.Bold; color: "#1c2440"
            }
            Item { Layout.fillWidth: true }
            // ‹ › 月份翻页
            Repeater {
                model: [{ ch: "‹", next: false }, { ch: "›", next: true }]
                delegate: Rectangle {
                    width: 24; height: 24; radius: 7
                    color: navMA.containsMouse ? "#eef2fb" : "transparent"
                    Text { anchors.centerIn: parent; text: modelData.ch
                           font.pixelSize: 18; color: "#6471a8" }
                    MouseArea {
                        id: navMA; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modelData.next ? card.nextMonth() : card.prevMonth()
                    }
                }
            }
            Rectangle {
                width: todayLbl.implicitWidth + 20; height: 24; radius: 8
                color: todayMA.containsMouse ? "#eef2fb" : "transparent"
                border.width: 1
                border.color: todayMA.containsMouse ? "#9bb4ee" : "#d2d8e6"
                Text {
                    id: todayLbl; anchors.centerIn: parent
                    text: "今天"; font.pixelSize: 12; font.weight: Font.Bold; color: "#2a3350"
                }
                MouseArea {
                    id: todayMA; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: card.todayClicked()
                }
            }
        }

        // 周名
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 10
            Repeater {
                model: ["日","一","二","三","四","五","六"]
                delegate: Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData
                    font.pixelSize: 11; font.weight: Font.Bold; font.letterSpacing: 0.4
                    color: "#9aa3b8"
                }
            }
        }

        // 6×7 网格
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 4
            columns: 7
            rowSpacing: 0; columnSpacing: 0
            Repeater {
                id: grid
                model: Cal.buildMonth(card.year, card.month)
                delegate: DayCell {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    n: modelData.n
                    muted: modelData.muted
                    selected: !modelData.muted && modelData.n === card.selectedDay
                    subText: (!modelData.muted && card.calendarInfoSource)
                             ? card.calendarInfoSource.cellLabel(card.year, card.month, modelData.n) : ""
                    dayType: (!modelData.muted && card.calendarInfoSource)
                             ? card.calendarInfoSource.dayType(card.year, card.month, modelData.n) : ""
                    dot: modelData.muted ? ""
                       : ((typeof events !== "undefined" && events)
                          ? (card.rev, events.dotFor(card.year, card.month, modelData.n))
                          : "")
                    accent: card.accent
                    onClicked: card.daySelected(modelData.n)
                }
            }
        }

        // 图例
        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: 8
            height: 1; color: Qt.rgba(120/255, 130/255, 160/255, 0.16)
        }
        Flow {
            Layout.fillWidth: true
            Layout.topMargin: 8
            spacing: 12
            Repeater {
                model: Demo.LEGEND
                delegate: Row {
                    spacing: 5
                    Rectangle {
                        width: 7; height: 7; radius: 3.5
                        anchors.verticalCenter: parent.verticalCenter
                        color: modelData.color
                    }
                    Text {
                        text: modelData.label
                        font.pixelSize: 11; color: "#6471a8"
                    }
                }
            }
        }
    }
}
