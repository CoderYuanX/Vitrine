import QtQuick

Rectangle {
    id: item
    height: 36
    radius: 11
    property string label: ""
    property bool active: false
    property bool muted: false        // 底部"设置"用
    signal clicked()
    HoverHandler { id: hh }
    color: active ? "#e9f1fe"
         : (hh.hovered ? "#f4f6fa" : "transparent")
    Behavior on color { ColorAnimation { duration: 120 } }

    Row {
        anchors.left: parent.left; anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11
        Rectangle { width: 17; height: 17; radius: 4; anchors.verticalCenter: parent.verticalCenter
            color: "transparent"; border.width: 1.8
            border.color: item.active ? "#2563eb" : (item.muted ? "#8a93a3" : "#5b6472") }  // 图标占位:Task 13 换真 SVG
        Text { text: item.label; anchors.verticalCenter: parent.verticalCenter
            font.pixelSize: 14; font.weight: Font.Medium
            color: item.active ? "#2563eb" : (item.muted ? "#8a93a3" : "#5b6472") }
    }
    TapHandler { onTapped: item.clicked() }
}
