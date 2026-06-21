import QtQuick

Rectangle {
    id: side
    width: 186
    color: "#ffffff"
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: "#f1f3f7" }

    Column {
        anchors.fill: parent
        anchors.margins: 12
        anchors.topMargin: 14
        anchors.bottomMargin: 14 + 36 + 14  // reserve space for bottom settings item
        spacing: 3

        Repeater {
            model: catalog.categories
            NavItem {
                width: parent.width
                label: modelData.label
                active: catalog.activeCategory === modelData.key
                onClicked: catalog.setCategory(modelData.key)
            }
        }
    }
    NavItem {                            // 底部"设置"
        label: "设置"; muted: true
        width: parent.width - 24
        anchors.left: parent.left; anchors.leftMargin: 12
        anchors.bottom: parent.bottom; anchors.bottomMargin: 14
        onClicked: catalog.setCategory("settings")
    }
}
