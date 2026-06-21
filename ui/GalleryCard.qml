import QtQuick
import QtQuick.Effects

Item {
    id: cardRoot
    property string wid: ""
    property string title: ""
    property bool enabled: false
    property bool implemented: true
    property string previewQml: ""

    HoverHandler { id: hover; enabled: cardRoot.implemented }

    // 投影层(在卡片背后渲染)
    MultiEffect {
        source: cardBg
        anchors.fill: cardBg
        shadowEnabled: true
        shadowColor: hover.hovered ? Qt.rgba(40/255,78/255,160/255,0.10) : Qt.rgba(20/255,40/255,90/255,0.04)
        shadowVerticalOffset: hover.hovered ? 6 : 1
        shadowBlur: hover.hovered ? 0.5 : 0.15
    }

    // 背景卡片
    Rectangle {
        id: cardBg
        anchors.fill: parent
        radius: 14
        color: "#ffffff"
        border.width: 1; border.color: "#eef1f6"
        opacity: cardRoot.implemented ? 1.0 : 0.6

        // 头部:卡片名称(锚定版)
        Text { id: nameText
            text: cardRoot.title; color: "#8a93a3"; font.pixelSize: 13; font.weight: Font.DemiBold
            anchors.left: parent.left; anchors.leftMargin: 17
            anchors.top: parent.top; anchors.topMargin: 15 }

        // 开关图标 20×20(仅 implemented 时可见)
        Item {
            width: 20; height: 20
            anchors.right: parent.right; anchors.rightMargin: 17
            anchors.top: parent.top; anchors.topMargin: 15
            visible: cardRoot.implemented
            Rectangle { anchors.fill: parent; radius: 10
                color: cardRoot.enabled ? "#3b82f6" : "transparent"
                border.width: cardRoot.enabled ? 0 : 1.6
                border.color: "#ced6e2" }
            Canvas { anchors.fill: parent; visible: cardRoot.enabled
                onPaint: { var c=getContext("2d"); c.strokeStyle="#fff"; c.lineWidth=2.2; c.lineCap="round"; c.lineJoin="round"
                    c.beginPath(); c.moveTo(5.8,10.3); c.lineTo(8.6,13.0); c.lineTo(14.2,7.5); c.stroke() } }
            TapHandler { onTapped: catalog.toggle(cardRoot.wid, !cardRoot.enabled) }
        }

        // 预览/占位槽,Task 11/12 填充
        Loader {
            id: bodyLoader
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.topMargin: 44
            anchors.bottom: parent.bottom
            anchors.leftMargin: 17; anchors.rightMargin: 17; anchors.bottomMargin: 15
        }

        // "即将推出"占位(仅 not implemented 时可见)
        Text {
            anchors.centerIn: bodyLoader
            visible: !cardRoot.implemented
            text: "即将推出"; color: "#aab2c0"; font.pixelSize: 13
        }
    }
}
