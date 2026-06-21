import QtQuick

Item {
    id: pv
    Column {
        anchors.left: parent.left
        anchors.top: parent.top
        spacing: 12
        Text { id: t; color: "#222c43"; font.pixelSize: 46; font.weight: Font.Bold
            font.letterSpacing: 1; text: "00:00" }
        Text { id: dl; color: "#9aa4b4"; font.pixelSize: 13; text: "" }
    }
    Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: {
            var d = new Date()
            var wk = ["日","一","二","三","四","五","六"]
            t.text = Qt.formatTime(d, "hh:mm")
            dl.text = (d.getMonth()+1) + "月" + d.getDate() + "日 星期" + wk[d.getDay()]
        }
    }
}
