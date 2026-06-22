import QtQuick
import QtQuick.Layouts

// 效率卡(grid-area:prod):三项统计全部派生自真实数据(events + tasks 桥)。
Rectangle {
    id: card
    property color accent: "#2f6bff"
    property string todayIso: ""
    property int year: 2026
    property int month: 5      // 0-11
    property int today: 1      // 当月日;-1 表示非当月
    property int rev: 0

    function _hasTasks()  { return typeof tasks  !== "undefined" && tasks }
    function _hasEvents() { return typeof events !== "undefined" && events }
    function meetingsToday() {
        if (!card._hasEvents() || card.today < 1) return 0
        var evs = (card.rev, events.dayEvents(card.year, card.month, card.today))
        var n = 0
        for (var i = 0; i < evs.length; i++) if (evs[i].cat === "meeting") n++
        return n
    }
    function doneWeek()   { return (card.rev, card._hasTasks() && card.todayIso) ? tasks.doneThisWeek(card.todayIso)   : 0 }
    function activeWeek() { return (card.rev, card._hasTasks() && card.todayIso) ? tasks.activeThisWeek(card.todayIso) : 0 }
    function totalWeek()  { return (card.rev, card._hasTasks() && card.todayIso) ? tasks.totalThisWeek(card.todayIso)  : 0 }
    function progress()   { var t = totalWeek(); return t > 0 ? doneWeek() / t : 0 }

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    Connections { target: card._hasTasks()  ? tasks  : null; ignoreUnknownSignals: true; function onChanged() { card.rev++ } }
    Connections { target: card._hasEvents() ? events : null; ignoreUnknownSignals: true; function onChanged() { card.rev++ } }

    component Stat: ColumnLayout {
        property string label: ""
        property string value: ""
        property string sub: ""
        spacing: 0
        Text { text: label; font.pixelSize: 11; color: "#9aa3b8" }
        Text { text: value; font.pixelSize: 26; font.weight: Font.Bold; color: "#1c2440" }
        Text { text: sub; font.pixelSize: 10; color: "#b3bacb" }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 15; anchors.rightMargin: 15
        anchors.topMargin: 14; anchors.bottomMargin: 14
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Text { text: "效率"; font.pixelSize: 13; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Text { text: "⋮"; font.pixelSize: 14; color: "#9aa3b8" }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 14
            Stat { label: "会议";    value: "" + card.meetingsToday(); sub: "今日" }
            Item { Layout.fillWidth: true }
            Stat { label: "完成任务"; value: "" + card.doneWeek();      sub: "本周" }
            Item { Layout.fillWidth: true }
            Stat { label: "待办";    value: "" + card.activeWeek();    sub: "本周" }
        }

        Item { Layout.fillHeight: true }
        Rectangle {
            Layout.fillWidth: true; height: 6; radius: 3
            color: Qt.rgba(120/255, 130/255, 160/255, 0.18)
            Rectangle { width: parent.width * card.progress(); height: parent.height; radius: 3; color: card.accent }
        }
        Text {
            text: card.progress() >= 0.7 ? "进展不错,继续保持!" : "继续加油!"
            font.pixelSize: 12; color: "#6471a8"; Layout.topMargin: 7
        }
    }
}
