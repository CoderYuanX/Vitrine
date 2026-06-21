import QtQuick
import QtQuick.Layouts
import "DemoData.js" as Demo

// 天气卡(grid-area:weather):实时时间/日期 + 天气演示数据。
Rectangle {
    id: card
    property var weatherSource: null
    property string timeText: "10:28"
    property string ampm: "AM"
    property string dateText: "Tuesday, May 20"

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 0

        // 城市行
        RowLayout {
            Layout.fillWidth: true
            Text { text: card.weatherSource ? card.weatherSource.cityFull : Demo.WEATHER.cityFull; font.pixelSize: 13; color: "#7b8398" }
            Item { Layout.fillWidth: true }
            Text { text: "⋮"; font.pixelSize: 14; color: "#9aa3b8" }
        }

        // 时间
        RowLayout {
            Layout.topMargin: 2
            spacing: 4
            Text { text: card.timeText; font.pixelSize: 30; font.weight: Font.Bold; color: "#1c2440" }
            Text { text: card.ampm; font.pixelSize: 12; font.weight: Font.Bold; color: "#7b8398"
                   Layout.alignment: Qt.AlignBottom; bottomPadding: 4 }
        }
        Text { text: card.dateText; font.pixelSize: 13; color: "#5a6280" }

        // 天气主体
        RowLayout {
            Layout.topMargin: 7
            spacing: 10
            SunCloud { Layout.preferredWidth: 40; Layout.preferredHeight: 32 }
            ColumnLayout {
                spacing: 0
                Text { text: card.weatherSource ? card.weatherSource.temp : Demo.WEATHER.temp; font.pixelSize: 22; font.weight: Font.Bold; color: "#1c2440" }
                Text { text: card.weatherSource ? card.weatherSource.desc : Demo.WEATHER.desc; font.pixelSize: 12; color: "#7b8398" }
            }
        }

        // 高低温 + 湿度
        RowLayout {
            Layout.topMargin: 6
            spacing: 14
            Text { text: card.weatherSource ? card.weatherSource.hi : Demo.WEATHER.hi; font.pixelSize: 12; color: "#7b8398" }
            Text { text: card.weatherSource ? card.weatherSource.lo : Demo.WEATHER.lo; font.pixelSize: 12; color: "#7b8398" }
            Text { text: "湿度 " + (card.weatherSource ? card.weatherSource.humidity : Demo.WEATHER.humidity); font.pixelSize: 12; color: "#7b8398" }
        }
        Item { Layout.fillHeight: true }
    }
}
