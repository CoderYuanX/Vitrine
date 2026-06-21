import QtQuick
import QtQuick.Window
import "../ui"

Window {
    id: win
    width: 820; height: 220
    visible: true
    color: "transparent"
    title: "GalleryCard Preview"

    Rectangle {
        anchors.fill: parent
        color: "#f0f4fa"

        Row {
            anchors.centerIn: parent
            spacing: 20

            GalleryCard {
                wid: "clock"
                title: "时钟"
                enabled: true
                implemented: true
                width: 380
                height: 168
            }

            GalleryCard {
                wid: "weather"
                title: "天气"
                enabled: false
                implemented: false
                width: 380
                height: 168
            }
        }
    }
}
