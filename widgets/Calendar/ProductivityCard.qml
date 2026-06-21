import QtQuick
import QtQuick.Layouts
import "DemoData.js" as Demo

// 效率卡(grid-area:prod):三项统计 + 进度条(演示)。
Rectangle {
    id: card
    property color accent: "#2f6bff"

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    component Stat: ColumnLayout {
        property string label: ""
        property string value: ""
        property string sub: ""
        spacing: 0
        Text { text: label; font.pixelSize: 11; color: "#9aa3b8" }
        Text { text: value; font.pixelSize: 26; font.weight: Font.Bold; color: "#1c2440" }
        Text { text: sub; font.pixelSize: 10; color: "#b3bacb" }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 15; anchors.rightMargin: 15
        anchors.topMargin: 14; anchors.bottomMargin: 14
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Text { text: "Productivity"; font.pixelSize: 13; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Text { text: "⋮"; font.pixelSize: 14; color: "#9aa3b8" }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 14
            Stat { label: "Meetings";   value: Demo.PRODUCTIVITY.meetings;  sub: "Today" }
            Item { Layout.fillWidth: true }
            Stat { label: "Tasks Done"; value: Demo.PRODUCTIVITY.tasksDone; sub: "This Week" }
            Item { Layout.fillWidth: true }
            Stat { label: "Focus Time"; value: Demo.PRODUCTIVITY.focus;     sub: "This Week" }
        }

        Item { Layout.fillHeight: true }
        Rectangle {
            Layout.fillWidth: true; height: 6; radius: 3
            color: Qt.rgba(120/255, 130/255, 160/255, 0.18)
            Rectangle {
                width: parent.width * Demo.PRODUCTIVITY.progress
                height: parent.height; radius: 3; color: card.accent
            }
        }
        Text { text: Demo.PRODUCTIVITY.note; font.pixelSize: 12; color: "#6471a8"; Layout.topMargin: 7 }
    }
}
