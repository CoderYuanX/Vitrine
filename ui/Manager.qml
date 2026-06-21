import QtQuick
import QtQuick.Window

Window {
    id: win
    width: 1000; height: 704            // 含外层 40 边距;主卡 920×624 居中
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.Window
    title: "桌面小组件"

    Rectangle {                          // 外层淡蓝渐变背景
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: "#cfe0fb" }
            GradientStop { position: 0.38; color: "#e4eefe" }
            GradientStop { position: 1.0; color: "#f4f8ff" }
        }

        Rectangle {                      // 主卡(窗口)
            id: card
            width: 920; height: 624
            anchors.centerIn: parent
            color: "#ffffff"
            radius: 18
            // 阴影 Task 13 用 MultiEffect 补;先保证布局

            Column {
                anchors.fill: parent
                Rectangle { id: titleArea; width: parent.width; height: 56; color: "transparent"
                    Text { anchors.centerIn: parent; text: "标题栏占位"; color: "#aaa" } }
                Row {
                    width: parent.width; height: parent.height - 56
                    Rectangle { id: sideArea; width: 186; height: parent.height; color: "#fff"
                        Text { anchors.centerIn: parent; text: "侧栏"; color: "#aaa" } }
                    Rectangle { id: contentArea; width: parent.width - 186; height: parent.height; color: "#fbfcfe"
                        Text { anchors.centerIn: parent; text: "内容区"; color: "#aaa" } }
                }
            }

            DragHandler {                // 整卡可拖(标题栏区 Task 8 收窄)
                target: null
                onActiveChanged: if (active) win.startSystemMove()
            }
        }
    }
}
