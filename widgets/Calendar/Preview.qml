import QtQuick
import "CalendarModel.js" as Cal

// 画廊预览:左=月份/大日号/星期,右=迷你周历(今日蓝点)。复刻管理器设计稿日历卡。
Item {
    id: pv
    property var now: new Date()

    // 当月网格,去掉尾部整周全是非本月的那一行(尽量 5 行,贴合设计)
    function cells() {
        var c = Cal.buildMonth(now.getFullYear(), now.getMonth())
        if (c.length === 42) {
            var allMuted = true
            for (var i = 35; i < 42; i++) if (!c[i].muted) { allMuted = false; break }
            if (allMuted) c = c.slice(0, 35)
        }
        return c
    }
    readonly property var weeks: ["星期日","星期一","星期二","星期三","星期四","星期五","星期六"]

    Row {
        anchors.fill: parent
        spacing: 14

        // 左列
        Column {
            width: 78
            spacing: 2
            Text {
                text: pv.now.getFullYear() + "/" + ("0" + (pv.now.getMonth() + 1)).slice(-2)
                font.pixelSize: 12; color: "#aab2c0"
            }
            Text {
                text: pv.now.getDate()
                font.pixelSize: 38; font.weight: Font.Bold; color: "#3b82f6"; lineHeight: 1.05
            }
            Text { text: pv.weeks[pv.now.getDay()]; font.pixelSize: 12; color: "#9aa4b4" }
        }

        // 右:迷你月历
        Column {
            width: parent.width - 78 - 14
            spacing: 3

            Grid {
                width: parent.width
                columns: 7
                Repeater {
                    model: ["日","一","二","三","四","五","六"]
                    delegate: Item {
                        width: parent.width / 7; height: 13
                        Text { anchors.centerIn: parent; text: modelData
                               font.pixelSize: 10; color: "#b8c0cd" }
                    }
                }
            }
            Grid {
                width: parent.width
                columns: 7
                Repeater {
                    model: pv.cells()
                    delegate: Item {
                        width: parent.width / 7; height: 17
                        property bool isToday: !modelData.muted && modelData.n === pv.now.getDate()
                        Rectangle {
                            visible: isToday
                            anchors.centerIn: parent
                            width: 16; height: 16; radius: 8; color: "#3b82f6"
                        }
                        Text {
                            anchors.centerIn: parent
                            text: modelData.n
                            font.pixelSize: 11
                            font.weight: isToday ? Font.Bold : Font.Normal
                            color: isToday ? "#ffffff" : (modelData.muted ? "#d3d9e2" : "#6b7486")
                        }
                    }
                }
            }
        }
    }
}
