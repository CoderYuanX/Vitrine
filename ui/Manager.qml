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
                TitleBar {
                    id: titleBar
                    width: parent.width
                    onMinimizeClicked: win.hide()
                    onCloseClicked: win.hide()
                    DragHandler { target: null; onActiveChanged: if (active) win.startSystemMove() }
                }
                Row {
                    width: parent.width; height: parent.height - 56
                    Sidebar { id: sideArea; height: parent.height }
                    Rectangle {
                        id: contentArea
                        width: parent.width - 186; height: parent.height; color: "#fbfcfe"
                        Flow {
                            anchors.fill: parent
                            anchors.margins: 18
                            anchors.leftMargin: 20; anchors.rightMargin: 20
                            spacing: 14
                            Repeater {
                                model: catalog.visibleWidgets
                                GalleryCard {
                                    width: (contentArea.width - 40 - 14) / 2
                                    height: 168
                                    wid: modelData.id
                                    title: modelData.name
                                    widgetEnabled: modelData.enabled
                                    implemented: modelData.implemented
                                    previewQml: modelData.previewQml
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
