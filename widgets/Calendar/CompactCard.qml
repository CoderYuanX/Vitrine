import QtQuick
import QtQuick.Layouts
import "DemoData.js" as Demo

// 折叠态紧凑卡(clock 变体)。拖动=移动窗口;单击=展开。
Item {
    id: root
    property var weatherSource: null
    property string timeText: "10:28"
    property string ampm: "AM"
    property string dateText: "Tuesday, May 20"
    property var winRef: null          // 宿主 Window 引用(用于 startSystemMove)
    signal expandRequested()

    implicitWidth: 256
    implicitHeight: cardRect.implicitHeight

    Rectangle {
        id: cardRect
        width: 256
        implicitHeight: cardCol.implicitHeight + 36
        height: implicitHeight
        radius: 22
        color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.55)

        // hover 抬升
        transform: Translate { id: lift; y: cardHover.hovered ? -3 : 0
            Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } } }

        ColumnLayout {
            id: cardCol
            anchors.left: parent.left; anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 20; anchors.rightMargin: 20
            spacing: 2

            // 城市 + 天气图标
            RowLayout {
                Layout.fillWidth: true
                RowLayout {
                    spacing: 5
                    // 矢量定位针(替代 📍 emoji,避免系统 emoji 字体影响)
                    Canvas {
                        Layout.preferredWidth: 11; Layout.preferredHeight: 13
                        Layout.alignment: Qt.AlignVCenter
                        onPaint: {
                            var c = getContext("2d"); c.reset()
                            c.fillStyle = "#7b8398"
                            c.beginPath(); c.arc(5.5, 5, 4.5, 0, 2 * Math.PI); c.fill()
                            c.beginPath(); c.moveTo(1.8, 7.0); c.lineTo(9.2, 7.0); c.lineTo(5.5, 13); c.closePath(); c.fill()
                            c.fillStyle = "#ffffff"
                            c.beginPath(); c.arc(5.5, 5, 1.8, 0, 2 * Math.PI); c.fill()
                        }
                    }
                    Text { text: root.weatherSource ? root.weatherSource.city : Demo.WEATHER.city; font.pixelSize: 13; color: "#7b8398" }
                }
                Item { Layout.fillWidth: true }
                SunCloud { Layout.preferredWidth: 34; Layout.preferredHeight: 28 }
            }
            // 时间
            RowLayout {
                spacing: 4
                Text { text: root.timeText; font.pixelSize: 44; font.weight: Font.Bold; color: "#1c2440" }
                Text { text: root.ampm; font.pixelSize: 15; font.weight: Font.Bold; color: "#7b8398"
                       Layout.alignment: Qt.AlignBottom; bottomPadding: 6 }
            }
            // 日期 + 温度
            RowLayout {
                Layout.fillWidth: true
                Text { text: root.dateText; font.pixelSize: 13; color: "#5a6280" }
                Item { Layout.fillWidth: true }
                Text { text: root.weatherSource ? root.weatherSource.temp : Demo.WEATHER.temp; font.pixelSize: 18; font.weight: Font.Bold; color: "#1c2440" }
            }
        }

        HoverHandler { id: cardHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: root.expandRequested() }
        DragHandler {
            target: null
            onActiveChanged: if (active && root.winRef) root.winRef.startSystemMove()
        }
    }
}
