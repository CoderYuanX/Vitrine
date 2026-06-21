import QtQuick
import QtQuick.Layouts

// 即将到来卡(grid-area:up):暖色背景,取本地事件库中今日之后的未来事件。
Rectangle {
    id: card
    property color accent: "#2f6bff"
    property string todayIso: ""
    property int rev: 0
    function _hasEvents() { return typeof events !== "undefined" && events }
    function upcomingList() {
        return (card.rev, card._hasEvents() && card.todayIso) ? events.upcoming(card.todayIso, 4) : []
    }
    // "YYYY-MM-DD" + 可选时间 → "M月D日 HH:MM"
    function _when(e) {
        var p = e.date.split("-")
        var s = parseInt(p[1]) + "月" + parseInt(p[2]) + "日"
        return e.time ? s + " " + e.time : s
    }

    radius: 18
    color: Qt.rgba(252/255, 250/255, 243/255, 0.94)   // 暖色
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    Connections {
        target: card._hasEvents() ? events : null
        ignoreUnknownSignals: true
        function onChanged() { card.rev++ }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 15; anchors.rightMargin: 15
        anchors.topMargin: 12; anchors.bottomMargin: 12
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Text { text: "Upcoming"; font.pixelSize: 13; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Text { text: "⋮"; font.pixelSize: 14; color: "#9aa3b8" }
        }

        ColumnLayout {
            Layout.fillWidth: true; Layout.topMargin: 8; spacing: 4
            Repeater {
                model: card.upcomingList()
                delegate: ColumnLayout {
                    Layout.fillWidth: true; spacing: 2
                    Text { text: modelData.title; font.pixelSize: 13; font.weight: Font.DemiBold; color: "#2a3350" }
                    Text { text: card._when(modelData); font.pixelSize: 11; color: "#9aa3b8" }
                }
            }
            Text {
                visible: card.upcomingList().length === 0
                text: "暂无即将到来的事件"; font.pixelSize: 12; color: "#aab2c0"
            }
        }

        Item { Layout.fillHeight: true }
        Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(120/255,130/255,160/255,0.16); Layout.topMargin: 6 }
        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 6
            Text { text: "View Calendar"; font.pixelSize: 13; font.weight: Font.Bold; color: "#2a3350" }
            Item { Layout.fillWidth: true }
            Text { text: "›"; font.pixelSize: 16; font.weight: Font.Bold; color: card.accent }
        }
    }
}
