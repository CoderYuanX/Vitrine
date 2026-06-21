import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

// 选中日 日程卡(grid-area:agenda):读写本地事件库(context property `events`)。
// 点月历某日 → 显示该日事件,可增删。
Rectangle {
    id: card
    property int year: 2026
    property int month: 5          // 0-11
    property int day: 21
    property string selectedIso: ""
    property string dateLabel: "Tue, May 20"
    property color accent: "#2f6bff"
    property int rev: 0            // 事件变更计数,驱动列表重算
    property bool adding: false
    property string newCat: "work"

    readonly property var cats: [
        { key: "work",      label: "工作", color: "#2f6bff" },
        { key: "personal",  label: "个人", color: "#16a34a" },
        { key: "meeting",   label: "会议", color: "#7c3aed" },
        { key: "important", label: "重要", color: "#d97706" },
        { key: "holiday",   label: "假期", color: "#ec4899" }
    ]
    function _hasEvents() { return typeof events !== "undefined" && events }
    function dayList() {
        return (card.rev, card._hasEvents()) ? events.dayEvents(card.year, card.month, card.day) : []
    }
    function _catLabel(key) {
        var c = card.cats.filter(function (x) { return x.key === key })
        return c.length ? c[0].label : key
    }

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    Connections {
        target: card._hasEvents() ? events : null
        ignoreUnknownSignals: true
        function onChanged() { card.rev++ }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16; anchors.rightMargin: 16
        anchors.topMargin: 15; anchors.bottomMargin: 15
        spacing: 0

        // 标题 + 添加按钮
        RowLayout {
            Layout.fillWidth: true
            RowLayout {
                spacing: 4
                Text { text: "日程"; font.pixelSize: 14; font.weight: Font.Bold; color: "#1c2440" }
                Text { text: card.dateLabel ? "· " + card.dateLabel : ""
                       font.pixelSize: 14; color: "#9aa3b8" }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: 24; height: 24; radius: 7
                color: addMA.containsMouse ? "#eef2fb" : "transparent"
                Text { anchors.centerIn: parent; text: card.adding ? "×" : "+"
                       font.pixelSize: 18; font.weight: Font.Bold; color: card.accent }
                MouseArea {
                    id: addMA; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: card.adding = !card.adding
                }
            }
        }

        // 添加表单
        ColumnLayout {
            Layout.fillWidth: true
            Layout.topMargin: card.adding ? 10 : 0
            spacing: 8
            visible: card.adding

            TextField {
                id: titleField
                Layout.fillWidth: true
                placeholderText: "事件标题"
                font.pixelSize: 13
                color: "#1c2440"
                background: Rectangle { radius: 8; color: "#f4f6fb"; border.width: 1; border.color: "#e3e8f2" }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: timeField
                    Layout.preferredWidth: 70
                    placeholderText: "09:00"
                    font.pixelSize: 13
                    color: "#1c2440"
                    background: Rectangle { radius: 8; color: "#f4f6fb"; border.width: 1; border.color: "#e3e8f2" }
                }
                Repeater {
                    model: card.cats
                    delegate: Rectangle {
                        width: 18; height: 18; radius: 9
                        color: modelData.color
                        opacity: card.newCat === modelData.key ? 1.0 : 0.32
                        border.width: card.newCat === modelData.key ? 2 : 0
                        border.color: "#1c2440"
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: card.newCat = modelData.key
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    width: okT.implicitWidth + 22; height: 26; radius: 8
                    color: card.accent
                    Text { id: okT; anchors.centerIn: parent; text: "添加"
                           font.pixelSize: 12; font.weight: Font.Bold; color: "white" }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (card._hasEvents() && titleField.text.trim().length) {
                                events.add(card.selectedIso, titleField.text, card.newCat, timeField.text)
                                titleField.text = ""; timeField.text = ""; card.adding = false
                            }
                        }
                    }
                }
            }
        }

        // 事件列表
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 13
            clip: true
            spacing: 13
            model: card.dayList()
            delegate: RowLayout {
                width: ListView.view ? ListView.view.width : 0
                spacing: 11
                Text {
                    Layout.preferredWidth: 52; Layout.alignment: Qt.AlignTop
                    text: modelData.time ? modelData.time : "全天"
                    font.pixelSize: 12; font.weight: Font.Bold; color: "#2a3350"
                }
                Rectangle {
                    Layout.preferredWidth: 2; Layout.fillHeight: true
                    color: card._hasEvents() ? events.catColor(modelData.cat) : "#2f6bff"
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 3
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: modelData.title; font.pixelSize: 13; font.weight: Font.Bold
                            color: "#1c2440"; elide: Text.ElideRight
                        }
                        Item {
                            Layout.preferredWidth: 16; Layout.preferredHeight: 16
                            Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 11
                                   color: delMA.containsMouse ? "#ef4444" : "#c2c9d8" }
                            MouseArea {
                                id: delMA; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: if (card._hasEvents()) events.remove(modelData.id)
                            }
                        }
                    }
                    Item {
                        implicitWidth: tg.implicitWidth + 12; implicitHeight: tg.implicitHeight + 3
                        // 背景单独一层(低透明),避免文字被 opacity 继承变淡
                        Rectangle {
                            anchors.fill: parent; radius: 5; opacity: 0.14
                            color: card._hasEvents() ? events.catColor(modelData.cat) : "#2f6bff"
                        }
                        Text { id: tg; anchors.centerIn: parent; text: card._catLabel(modelData.cat)
                               font.pixelSize: 10; font.weight: Font.Bold
                               color: card._hasEvents() ? events.catColor(modelData.cat) : "#2f6bff" }
                    }
                }
            }
        }

        // 空状态
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: list.count === 0 && !card.adding
            Text {
                anchors.centerIn: parent
                text: "这一天还没有日程\n点右上角 + 添加"
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 12; color: "#aab2c0"; lineHeight: 1.4
            }
        }
    }
}
