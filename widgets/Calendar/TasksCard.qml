import QtQuick
import QtQuick.Layouts
import "DemoData.js" as Demo

// 任务卡(grid-area:tasks)。todayModel 为可切换 done 的 ListModel(根注入)。
Rectangle {
    id: card
    property var todayModel          // ListModel: {text,tag,tc,tb,done}
    property color accent: "#2f6bff"
    property int rev: 0              // 切换计数,驱动 dueCount 重算
    property int dueCount: {
        rev;                         // 依赖,任务切换时重算
        if (!todayModel) return 0;
        var c = 0;
        for (var i = 0; i < todayModel.count; i++)
            if (!todayModel.get(i).done) c++;
        return c;
    }

    radius: 18
    color: Qt.rgba(252/255, 253/255, 255/255, 0.92)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.55)

    component TaskRow: RowLayout {
        id: row
        Layout.fillWidth: true
        property bool done: false
        property string text_: ""
        property string rightText: ""
        property color rightColor: "#9aa3b8"
        property bool isTag: false
        signal toggled()
        spacing: 9

        Rectangle {
            Layout.preferredWidth: 17; Layout.preferredHeight: 17
            Layout.alignment: Qt.AlignTop
            radius: 5
            color: row.done ? card.accent : "transparent"
            border.width: 1.8
            border.color: row.done ? card.accent : "#c2c9d8"
            Text {
                anchors.centerIn: parent; visible: row.done
                text: "✓"; color: "white"; font.pixelSize: 11; font.weight: Font.Bold
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: row.toggled() }
        }
        Text {
            Layout.fillWidth: true
            text: row.text_
            font.pixelSize: 13; wrapMode: Text.WordWrap
            color: row.done ? "#aeb4c4" : "#2a3350"
            font.strikeout: row.done
        }
        Item {
            visible: isTag
            Layout.alignment: Qt.AlignTop
            implicitWidth: tagT.implicitWidth + 14; implicitHeight: tagT.implicitHeight + 4
            // 背景单独一层(低透明),避免文字被 opacity 继承变淡 / rgba 字符串解析失败变黑
            Rectangle { anchors.fill: parent; radius: 6; color: row.rightColor; opacity: 0.13 }
            Text { id: tagT; anchors.centerIn: parent; text: row.rightText
                   font.pixelSize: 11; font.weight: Font.Bold; color: row.rightColor }
        }
        Text {
            visible: !isTag
            Layout.alignment: Qt.AlignTop
            text: rightText; font.pixelSize: 12; color: "#9aa3b8"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16; anchors.rightMargin: 16
        anchors.topMargin: 15; anchors.bottomMargin: 15
        spacing: 0

        // 标题
        RowLayout {
            Layout.fillWidth: true
            Text { text: "任务与提醒"; font.pixelSize: 15; font.weight: Font.Bold; color: "#1c2440" }
            Item { Layout.fillWidth: true }
            Text { text: "+"; font.pixelSize: 20; font.weight: Font.Bold; color: card.accent }
        }

        // Due Today
        RowLayout {
            Layout.topMargin: 12; Layout.bottomMargin: 6; spacing: 7
            Text { text: "今日待办"; font.pixelSize: 13; font.weight: Font.Bold; color: card.accent }
            Text { text: card.dueCount; font.pixelSize: 11; color: "#9aa3b8" }
        }
        Repeater {
            model: card.todayModel
            delegate: TaskRow {
                Layout.topMargin: 4; Layout.bottomMargin: 4
                done: model.done
                text_: model.text
                isTag: true
                rightText: model.tag
                rightColor: model.tc
                onToggled: { card.todayModel.setProperty(index, "done", !model.done); card.rev++ }
            }
        }

        // This Week
        RowLayout {
            Layout.topMargin: 10; Layout.bottomMargin: 4; spacing: 7
            Text { text: "本周"; font.pixelSize: 13; font.weight: Font.Bold; color: "#6471a8" }
            Text { text: Demo.TASKS_WEEK.length; font.pixelSize: 11; color: "#9aa3b8" }
        }
        Repeater {
            model: Demo.TASKS_WEEK
            delegate: TaskRow {
                Layout.topMargin: 4; Layout.bottomMargin: 4
                text_: modelData.text
                isTag: false
                rightText: modelData.date
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
