import QtQuick

// Live diagnostics: every bus topic with value and age, refreshed 1×/s.
// Toggled with D, or persistently via cfg.debug (menu / phone settings).
Rectangle {
    id: panel
    color: Qt.rgba(0, 0, 0, 0.88)
    border.color: Style.faint
    radius: 4
    property var rows: []

    Timer {
        interval: 1000; running: panel.visible; repeat: true; triggeredOnStart: true
        onTriggered: panel.rows = bridge.debugRows()
    }

    Column {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 2
        Text {
            text: panel.rows.length + " topics · " + (topics.vehicle_source || "no vehicle")
            color: Style.accent
            font.family: "monospace"
            font.pixelSize: 11
        }
        Repeater {
            model: panel.rows
            Row {
                required property var modelData
                spacing: 6
                opacity: modelData[2] > 10 ? 0.45 : 1
                Text { width: panel.width * 0.45; elide: Text.ElideRight; text: modelData[0]; color: Style.dim; font.family: "monospace"; font.pixelSize: 10 }
                Text { width: panel.width * 0.38; elide: Text.ElideRight; text: modelData[1]; color: Style.fg; font.family: "monospace"; font.pixelSize: 10 }
                Text { text: modelData[2] < 2 ? "" : Math.round(modelData[2]) + "s"; color: Style.faint; font.family: "monospace"; font.pixelSize: 10 }
            }
        }
    }
}
