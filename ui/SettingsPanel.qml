import QtQuick
import QtQuick.Controls

Item {
    Column {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 16
        Text { text: "全局设置"; color: "#222c43"; font.pixelSize: 18; font.weight: Font.Bold
 }

        Row { spacing: 10
            Text { text: "开机自启"; color: "#5b6472"; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter
 }
            Rectangle { width: 44; height: 24; radius: 12
                color: catalog.autostartEnabled ? "#3b82f6" : "#d8e0ec"
                anchors.verticalCenter: parent.verticalCenter
                Rectangle { width: 18; height: 18; radius: 9; color: "#fff"; y: 3
                    x: catalog.autostartEnabled ? 23 : 3
                    Behavior on x { NumberAnimation { duration: 140 } } }
                TapHandler { onTapped: catalog.setAutostart(!catalog.autostartEnabled) } }
        }

        // 天气
        Column { spacing: 10
            Text { text: "天气"; color: "#222c43"; font.pixelSize: 15; font.weight: Font.Bold }

            Row { spacing: 10
                Text { text: "自动定位(按 IP)"; color: "#5b6472"; font.pixelSize: 14
                       anchors.verticalCenter: parent.verticalCenter }
                Rectangle { width: 44; height: 24; radius: 12
                    color: weather.autoLocate ? "#3b82f6" : "#d8e0ec"
                    anchors.verticalCenter: parent.verticalCenter
                    Rectangle { width: 18; height: 18; radius: 9; color: "#fff"; y: 3
                        x: weather.autoLocate ? 23 : 3
                        Behavior on x { NumberAnimation { duration: 140 } } }
                    TapHandler { onTapped: weather.setAutoLocate(!weather.autoLocate) } }
            }

            Row { spacing: 10
                Text { text: "城市"; color: "#5b6472"; font.pixelSize: 14
                       anchors.verticalCenter: parent.verticalCenter }
                TextField {
                    id: cityField
                    width: 180
                    enabled: !weather.autoLocate
                    opacity: enabled ? 1.0 : 0.5
                    text: weather.manualCity
                    placeholderText: "如:上海 / Shanghai"
                    font.pixelSize: 13
                    color: "#222c43"
                    background: Rectangle { radius: 8; color: "#f4f6fb"; border.width: 1; border.color: "#e3e8f2" }
                    onEditingFinished: weather.setCity(text)
                }
            }

            Text {
                visible: weather.autoLocate
                text: "关闭自动定位后改用手填城市;关闭后不再上报 IP 位置。"
                color: "#9aa4b4"; font.pixelSize: 11
            }
        }

        Row { spacing: 12
            component Btn: Rectangle { width: 96; height: 34; radius: 10; color: "#eef1f6"
                property string label: ""; signal clicked()
                Text { anchors.centerIn: parent; text: parent.label; color: "#5b6472"; font.pixelSize: 13
 }
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
 }
            TapHandler { onTapped: catalog.quitApp() }
        }
    }
}
