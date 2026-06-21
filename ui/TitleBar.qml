import QtQuick

Rectangle {
    id: bar
    height: 56
    color: "transparent"
    signal minimizeClicked()
    signal closeClicked()

    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#f1f3f7" }

    Row {
        anchors.left: parent.left; anchors.leftMargin: 20
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11
        Rectangle {
            width: 26; height: 26; radius: 8
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0; color: "#5b9bff" }
                GradientStop { position: 1; color: "#3b76f6" } }
            anchors.verticalCenter: parent.verticalCenter
            Grid {                      // 4 格白点 logo
                anchors.centerIn: parent; columns: 2; spacing: 2.5
                Repeater { model: 4
                    Rectangle { width: 6; height: 6; radius: 1.8; color: "#fff"
                        opacity: (index === 0 || index === 3) ? 1.0 : 0.8 } }
            }
        }
        Text { text: "桌面小组件"; color: "#2b3344"; font.pixelSize: 15
            font.weight: Font.DemiBold; font.letterSpacing: 0.2

            anchors.verticalCenter: parent.verticalCenter }
    }

    Row {
        anchors.right: parent.right; anchors.rightMargin: 18
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        component WinBtn: Rectangle {
            width: 30; height: 30; radius: 8
            property color hoverBg: "#f2f4f8"
            property color iconColor: "#9aa4b4"
            property alias ha: ha
            HoverHandler { id: ha }
            Behavior on color { ColorAnimation { duration: 120 } }
            color: ha.hovered ? hoverBg : "transparent"
        }
        WinBtn { id: minBtn
            Canvas { anchors.centerIn: parent; width: 15; height: 15
                onPaint: { var c=getContext("2d"); c.strokeStyle=minBtn.iconColor; c.lineWidth=2; c.lineCap="round"
                    c.beginPath(); c.moveTo(3,7.5); c.lineTo(12,7.5); c.stroke() } }
            TapHandler { onTapped: bar.minimizeClicked() } }
        WinBtn { id: closeBtn; hoverBg: "#ffeceb"
            property color xColor: ha.hovered ? "#ef4444" : "#9aa4b4"
            Canvas { anchors.centerIn: parent; width: 14; height: 14
                property color cc: closeBtn.xColor
                onCcChanged: requestPaint()
                onPaint: { var c=getContext("2d"); c.strokeStyle=cc; c.lineWidth=2; c.lineCap="round"
                    c.beginPath(); c.moveTo(3,3); c.lineTo(11,11); c.moveTo(11,3); c.lineTo(3,11); c.stroke() } }
            TapHandler { onTapped: bar.closeClicked() } }
    }
}
