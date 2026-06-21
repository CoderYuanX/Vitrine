import QtQuick

Rectangle {
    id: item
    height: 36
    radius: 11
    property string label: ""
    property string iconKey: ""
    property bool active: false
    property bool muted: false        // 底部"设置"用
    signal clicked()
    HoverHandler { id: hh }
    color: active ? "#e9f1fe"
         : (hh.hovered ? "#f4f6fa" : "transparent")
    Behavior on color { ColorAnimation { duration: 120 } }

    // Icon color: active=blue, muted=dim gray, idle=medium gray
    readonly property string iconColor: item.active ? "#2563eb" : (item.muted ? "#8a93a3" : "#5b6472")

    // SVG inner paths mapped by iconKey (stroke-width 1.8, viewBox 0 0 24 24)
    function svgInner(key) {
        switch (key) {
        case "all":
            return '<rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/>'
        case "clock":
            return '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8" stroke-linecap="round" stroke-linejoin="round"/>'
        case "weather":
            return '<path d="M7.5 18h9a4 4 0 0 0 .4-7.98A5.5 5.5 0 0 0 6.4 11 3.5 3.5 0 0 0 7.5 18Z" stroke-linejoin="round"/>'
        case "calendar":
            return '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4" stroke-linecap="round"/>'
        case "system":
            return '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20.5h6M12 16.5v4" stroke-linecap="round"/>'
        case "note":
            return '<path d="M6 3h8l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v4h4"/>'
        case "settings":
            return '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v2.5M12 19v2.5M4.2 7l2.2 1.3M17.6 15.7l2.2 1.3M4.2 17l2.2-1.3M17.6 8.3l2.2-1.3" stroke-linecap="round"/>'
        default:
            return '<rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/>'
        }
    }

    function svgSource(key, color) {
        var inner = svgInner(key)
        return 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="' + color + '" stroke-width="1.8">' + inner + '</svg>'
    }

    Row {
        anchors.left: parent.left; anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11
        Image {
            width: 17; height: 17
            anchors.verticalCenter: parent.verticalCenter
            source: item.svgSource(item.iconKey, item.iconColor)
            fillMode: Image.PreserveAspectFit
            smooth: true
        }
        Text {
            text: item.label
            anchors.verticalCenter: parent.verticalCenter
            font.pixelSize: 14; font.weight: Font.Medium
            font.family: "PingFang SC,Microsoft YaHei,Noto Sans CJK SC"
            color: item.iconColor
        }
    }
    TapHandler { onTapped: item.clicked() }
}
