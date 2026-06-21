import QtQuick
import QtQuick.Window

Window {
    id: root
    property real zoom: 1.0
    property string widgetId: "clock"
    readonly property int baseW: 320
    readonly property int baseH: 210
    width: Math.round(baseW * zoom)
    height: Math.round(baseH * zoom)
    visible: true
    color: "transparent"
    title: "deepin-widget-clock"
    // Qt.Tool:桌面挂件不进任务栏(映射即排除,无 200ms 缺口,不依赖 dock 是否认 skip-taskbar)
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus

    function persist() { layout.saveState(widgetId, root.x, root.y, root.zoom) }

    Component.onCompleted: {
        var p = layout.getState(widgetId).split(",")
        root.x = parseInt(p[0]); root.y = parseInt(p[1])
        root.zoom = parseFloat(p[2]) || 1.0
    }

    Item {
        width: root.baseW; height: root.baseH
        scale: root.zoom
        transformOrigin: Item.TopLeft

        Rectangle {
            id: card
            anchors.fill: parent
            anchors.margins: 6
            radius: 30
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#3A3A3C" }
                GradientStop { position: 1.0; color: "#1C1C1E" }
            }
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.10)

            DragHandler {
                target: null
                onActiveChanged: {
                    if (active) root.startSystemMove()
                    else root.persist()
                }
            }
            WheelHandler {
                onWheel: function(ev) {
                    var step = ev.angleDelta.y > 0 ? 0.08 : -0.08
                    root.zoom = Math.max(0.6, Math.min(2.6, root.zoom + step))
                    root.persist()
                }
            }

            Column {
                anchors.centerIn: parent
                spacing: 4
                Text { id: weekText; anchors.horizontalCenter: parent.horizontalCenter
                    color: "#FF7A6B"; font.pixelSize: 24; font.weight: Font.DemiBold; text: "星期六" }
                Text { id: timeText; anchors.horizontalCenter: parent.horizontalCenter
                    color: "white"; font.pixelSize: 56; font.weight: Font.Bold; font.letterSpacing: 1; text: "00:00:00" }
                Text { id: dateText; anchors.horizontalCenter: parent.horizontalCenter
                    color: Qt.rgba(1, 1, 1, 0.55); font.pixelSize: 18; text: "" }
            }
        }
    }

    Timer {
        interval: 1000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: {
            var d = new Date()
            var weeks = ["星期日","星期一","星期二","星期三","星期四","星期五","星期六"]
            timeText.text = Qt.formatTime(d, "hh:mm:ss")
            dateText.text = Qt.formatDate(d, "yyyy年M月d日")
            weekText.text = weeks[d.getDay()]
        }
    }
}
