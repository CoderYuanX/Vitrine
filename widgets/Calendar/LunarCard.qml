import QtQuick
import QtQuick.Layouts
import "DemoData.js" as Demo

// 农历 & 笔记卡(grid-area:lunar):月相 + 引言(占位)。
Rectangle {
    id: card
    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16; anchors.rightMargin: 16
        anchors.topMargin: 14; anchors.bottomMargin: 14
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Text { text: "Lunar & Notes"; font.pixelSize: 13; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Text { text: "⋮"; font.pixelSize: 14; color: "#9aa3b8" }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 11; spacing: 13
            // 月相圆(径向渐变近似)
            Rectangle {
                Layout.preferredWidth: 42; Layout.preferredHeight: 42; radius: 21
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#f0f1ea" }
                    GradientStop { position: 0.55; color: "#c7cbd6" }
                    GradientStop { position: 1.0; color: "#8e93a4" }
                }
            }
            ColumnLayout {
                spacing: 0
                Text { text: "Lunar Date"; font.pixelSize: 11; color: "#9aa3b8" }
                Text { text: Demo.LUNAR.lunarDate; font.pixelSize: 24; font.weight: Font.Bold; color: "#1c2440" }
                Text { text: Demo.LUNAR.label; font.pixelSize: 11; color: "#6471a8" }
            }
        }

        Item { Layout.fillHeight: true }
        Rectangle {
            Layout.fillWidth: true
            radius: 12
            color: "#f4f6fa"
            implicitHeight: quoteRow.implicitHeight + 20
            RowLayout {
                id: quoteRow
                anchors.fill: parent
                anchors.leftMargin: 12; anchors.rightMargin: 12
                anchors.topMargin: 10; anchors.bottomMargin: 10
                spacing: 10
                Text {
                    Layout.fillWidth: true
                    text: Demo.LUNAR.quote
                    font.pixelSize: 13; lineHeight: 1.35; color: "#2a3350"; wrapMode: Text.WordWrap
                }
                Text { text: "✎"; font.pixelSize: 14; color: "#9aa3b8" }
            }
        }
    }
}
