import QtQuick

// 月历单元格:日数字 + 分类圆点。今日/选中显示 accent 实心圆。
Item {
    id: cell
    property int n: 1
    property bool muted: false
    property bool selected: false
    property string dot: ""          // 分类色,空串=无点
    property string subText: ""
    property string dayType: ""      // holiday / workday / ""
    property color accent: "#2f6bff"
    signal clicked()

    Rectangle {
        id: hover
        anchors.fill: parent
        anchors.margins: 1
        radius: 10
        color: "transparent"
    }

    Column {
        anchors.centerIn: parent
        spacing: 4

        // 选中:accent 实心圆;否则纯文字
        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: cell.selected ? 29 : numText.implicitWidth
            height: cell.selected ? 29 : numText.implicitHeight
            Rectangle {
                visible: cell.selected
                anchors.fill: parent
                radius: 15
                color: cell.accent
                // 近似 box-shadow 0 4px 12px accent66
                Rectangle {
                    anchors.fill: parent; anchors.topMargin: 2
                    radius: 15; color: cell.accent; opacity: 0.4; z: -1
                }
            }
            Text {
                id: numText
                anchors.centerIn: parent
                text: cell.n
                font.pixelSize: 14
                font.weight: cell.selected ? Font.Bold : Font.Medium
                color: cell.selected ? "#ffffff"
                     : cell.muted ? "#bcc3d2" : "#22304e"
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: cell.subText
            visible: cell.subText.length > 0 && !cell.selected
            font.pixelSize: 9
            width: cell.width - 6
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
            color: cell.dayType === "holiday" ? "#ef4444"
                 : cell.dayType === "workday" ? "#d97706" : "#9aa3b8"
        }

        // 分类圆点(选中时隐藏)
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 5; height: 5; radius: 2.5
            color: (cell.selected || cell.dot === "") ? "transparent" : cell.dot
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: !cell.muted
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onEntered: if (!cell.selected) hover.color = Qt.rgba(47/255, 107/255, 255/255, 0.08)
        onExited: hover.color = "transparent"
        onClicked: cell.clicked()
    }
}
