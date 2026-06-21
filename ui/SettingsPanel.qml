import QtQuick

Item {
    Column {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 16
        Text { text: "全局设置"; color: "#222c43"; font.pixelSize: 18; font.weight: Font.Bold
            font.family: "PingFang SC,Microsoft YaHei,Noto Sans CJK SC" }

        Row { spacing: 10
            Text { text: "开机自启"; color: "#5b6472"; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter
                font.family: "PingFang SC,Microsoft YaHei,Noto Sans CJK SC" }
            Rectangle { width: 44; height: 24; radius: 12
                color: catalog.autostartEnabled ? "#3b82f6" : "#d8e0ec"
                anchors.verticalCenter: parent.verticalCenter
                Rectangle { width: 18; height: 18; radius: 9; color: "#fff"; y: 3
                    x: catalog.autostartEnabled ? 23 : 3
                    Behavior on x { NumberAnimation { duration: 140 } } }
                TapHandler { onTapped: catalog.setAutostart(!catalog.autostartEnabled) } }
        }

        Row { spacing: 12
            component Btn: Rectangle { width: 96; height: 34; radius: 10; color: "#eef1f6"
                property string label: ""; signal clicked()
                Text { anchors.centerIn: parent; text: parent.label; color: "#5b6472"; font.pixelSize: 13
                    font.family: "PingFang SC,Microsoft YaHei,Noto Sans CJK SC" }
                TapHandler { onTapped: parent.clicked() } }
            Btn { label: "全部显示"; onClicked: catalog.showAll() }
            Btn { label: "全部隐藏"; onClicked: catalog.hideAll() }
        }

        Rectangle {
            id: quitBtn
            width: 96; height: 34; radius: 10
            HoverHandler { id: quitHover }
            color: quitHover.hovered ? "#ffe0de" : "#ffeceb"
            Behavior on color { ColorAnimation { duration: 120 } }
            Text { anchors.centerIn: parent; text: "退出"; color: "#ef4444"; font.pixelSize: 13
                font.family: "PingFang SC,Microsoft YaHei,Noto Sans CJK SC" }
            TapHandler { onTapped: catalog.quitApp() }
        }
    }
}
