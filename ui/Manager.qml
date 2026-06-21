import QtQuick
import QtQuick.Window

Window {
    id: win
    readonly property int baseW: 920
    readonly property int baseH: 624
    readonly property real uiScale: Math.min(width / baseW, height / baseH)
    width: 920; height: 624
    minimumWidth: 460
    minimumHeight: 312
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.Window
    title: "桌面小组件"

    // 锁定纵横比:WM 边缘缩放只改单边时,另一边同步,
    // 保证 width/baseW === height/baseH —— uiScale 永不 letterbox,
    // 缩放卡片始终铺满窗口,不留透明可穿透条带。
    property bool _lockingAspect: false
    function _lockAspect(byWidth) {
        if (_lockingAspect)
            return
        _lockingAspect = true
        if (byWidth)
            height = Math.round(width * baseH / baseW)
        else
            width = Math.round(height * baseW / baseH)
        _lockingAspect = false
    }
    onWidthChanged: _lockAspect(true)
    onHeightChanged: _lockAspect(false)

    Item {
        id: scaledRoot
        width: win.baseW
        height: win.baseH
        transformOrigin: Item.TopLeft
        transform: Scale {
            xScale: win.uiScale
            yScale: win.uiScale
        }

        Rectangle {                      // 主卡(窗口)
            id: card
            anchors.fill: parent
            color: "#ffffff"
            radius: 18

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
                    Item {
                        id: contentArea
                        width: parent.width - 186; height: parent.height
                        Rectangle { anchors.fill: parent; color: "#fbfcfe"; radius: 18 }
                        Rectangle { anchors.left: parent.left; anchors.top: parent.top; width: parent.width; height: 18; color: "#fbfcfe" }
                        Rectangle { anchors.left: parent.left; anchors.top: parent.top; width: 18; height: parent.height; color: "#fbfcfe" }
                        Loader {
                            anchors.fill: parent; anchors.margins: 20
                            active: catalog.activeCategory === "settings"
                            visible: active
                            source: "SettingsPanel.qml"
                        }
                        Flow {
                            visible: catalog.activeCategory !== "settings"
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
