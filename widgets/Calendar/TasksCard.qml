import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

// 任务卡(grid-area:tasks):读写本地任务库(context property `tasks`)。
Rectangle {
    id: card
    property string todayIso: ""
    property color accent: "#2f6bff"
    property int rev: 0
    property bool adding: false
    property string newCat: "work"

    readonly property var cats: [
        { key: "work",      label: "工作", color: "#2f6bff" },
        { key: "personal",  label: "个人", color: "#16a34a" },
        { key: "meeting",   label: "会议", color: "#7c3aed" },
        { key: "important", label: "重要", color: "#d97706" },
        { key: "holiday",   label: "假期", color: "#ec4899" }
    ]
    function _has() { return typeof tasks !== "undefined" && tasks }
    function todayList() { return (card.rev, card._has() && card.todayIso) ? tasks.today(card.todayIso) : [] }
    function weekList()  { return (card.rev, card._has() && card.todayIso) ? tasks.week(card.todayIso)  : [] }
    function _catLabel(key) {
        var c = card.cats.filter(function (x) { return x.key === key })
        return c.length ? c[0].label : key
    }

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    Connections {
        target: card._has() ? tasks : null
        ignoreUnknownSignals: true
        function onChanged() { card.rev++ }
    }

    component TaskRow: RowLayout {
        property string tid: ""
        property bool done: false
        property string text_: ""
        property string rightText: ""
        property color rightColor: "#9aa3b8"
        property bool isTag: false
        Layout.fillWidth: true
        spacing: 9
        Rectangle {
            Layout.preferredWidth: 17; Layout.preferredHeight: 17; Layout.alignment: Qt.AlignTop
            radius: 5
            color: done ? card.accent : "transparent"
            border.width: 1.8; border.color: done ? card.accent : "#c2c9d8"
            Text { anchors.centerIn: parent; visible: done; text: "✓"; color: "white"; font.pixelSize: 11; font.weight: Font.Bold }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                onClicked: if (card._has()) tasks.toggle(tid) }
        }
        Text {
            Layout.fillWidth: true; text: text_
            font.pixelSize: 13; wrapMode: Text.WordWrap
            color: done ? "#aeb4c4" : "#2a3350"; font.strikeout: done
        }
        Item {
            visible: isTag; Layout.alignment: Qt.AlignTop
            implicitWidth: tagT.implicitWidth + 14; implicitHeight: tagT.implicitHeight + 4
            Rectangle { anchors.fill: parent; radius: 6; color: rightColor; opacity: 0.13 }
            Text { id: tagT; anchors.centerIn: parent; text: rightText; font.pixelSize: 11; font.weight: Font.Bold; color: rightColor }
        }
        Text { visible: !isTag; Layout.alignment: Qt.AlignTop; text: rightText; font.pixelSize: 12; color: "#9aa3b8" }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16; anchors.rightMargin: 16
        anchors.topMargin: 15; anchors.bottomMargin: 15
        spacing: 0

        // 标题 + 添加
        RowLayout {
            Layout.fillWidth: true
            Text { text: "任务与提醒"; font.pixelSize: 15; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: 24; height: 24; radius: 7
                color: addMA.containsMouse ? "#eef2fb" : "transparent"
                Text { anchors.centerIn: parent; text: card.adding ? "×" : "+"; font.pixelSize: 18; font.weight: Font.Bold; color: card.accent }
                MouseArea { id: addMA; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: card.adding = !card.adding }
            }
        }

        // 添加表单
        ColumnLayout {
            Layout.fillWidth: true; Layout.topMargin: card.adding ? 10 : 0; spacing: 8
            visible: card.adding
            TextField {
                id: titleField
                Layout.fillWidth: true; placeholderText: "任务内容"; font.pixelSize: 13; color: "#1c2440"
                background: Rectangle { radius: 8; color: "#f4f6fb"; border.width: 1; border.color: "#e3e8f2" }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Repeater {
                    model: card.cats
                    delegate: Rectangle {
                        width: 18; height: 18; radius: 9; color: modelData.color
                        opacity: card.newCat === modelData.key ? 1.0 : 0.32
                        border.width: card.newCat === modelData.key ? 2 : 0; border.color: "#1c2440"
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: card.newCat = modelData.key }
                    }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    width: okT.implicitWidth + 22; height: 26; radius: 8; color: card.accent
                    Text { id: okT; anchors.centerIn: parent; text: "添加"; font.pixelSize: 12; font.weight: Font.Bold; color: "white" }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (card._has() && titleField.text.trim().length) {
                                tasks.add(titleField.text, card.newCat, card.todayIso)
                                titleField.text = ""; card.adding = false
                            }
                        }
                    }
                }
            }
        }

        // 今日待办
        RowLayout {
            Layout.topMargin: 12; Layout.bottomMargin: 6; spacing: 7
            Text { text: "今日待办"; font.pixelSize: 13; font.weight: Font.Bold; color: card.accent }
            Text { text: card.todayList().length; font.pixelSize: 11; color: "#9aa3b8" }
        }
        Repeater {
            model: card.todayList()
            delegate: TaskRow {
                Layout.topMargin: 4; Layout.bottomMargin: 4
                tid: modelData.id; done: modelData.done; text_: modelData.text
                isTag: true; rightText: card._catLabel(modelData.cat); rightColor: modelData.color
            }
        }
        Text { visible: card.todayList().length === 0; Layout.topMargin: 2
               text: "暂无待办"; font.pixelSize: 12; color: "#aab2c0" }

        // 本周
        RowLayout {
            Layout.topMargin: 10; Layout.bottomMargin: 4; spacing: 7
            Text { text: "本周"; font.pixelSize: 13; font.weight: Font.Bold; color: "#6471a8" }
            Text { text: card.weekList().length; font.pixelSize: 11; color: "#9aa3b8" }
        }
        Repeater {
            model: card.weekList()
            delegate: TaskRow {
                Layout.topMargin: 4; Layout.bottomMargin: 4
                tid: modelData.id; done: modelData.done; text_: modelData.text
                isTag: false; rightText: modelData.label
            }
        }

        Item { Layout.fillHeight: true }
        Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(120/255,130/255,160/255,0.16) }
        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 10
            Text { text: "查看全部"; font.pixelSize: 13; font.weight: Font.Bold; color: "#2a3350" }
            Item { Layout.fillWidth: true }
            Text { text: "›"; font.pixelSize: 16; font.weight: Font.Bold; color: card.accent }
        }
    }
}
