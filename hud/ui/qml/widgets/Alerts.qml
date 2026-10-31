import QtQuick
import ".."

// Active alerts, critical first, pulsing.
Column {
    id: w
    readonly property var list: {
        const a = topics.alerts_active || []
        return a.slice().sort((x, y) => (x.level === "critical" ? 0 : 1) - (y.level === "critical" ? 0 : 1))
    }
    property bool shown: list.length > 0
    spacing: 0.8 * Style.ch

    Repeater {
        model: w.list
        Row {
            id: alertRow
            required property var modelData
            readonly property color tone: modelData.level === "critical" ? Style.crit : Style.warn
            spacing: 0.8 * Style.cw
            Icon { name: "warn"; size: 3.6; color: alertRow.tone; anchors.verticalCenter: parent.verticalCenter }
            GlowText {
                text: alertRow.modelData.message
                size: 3.4 * Style.ch
                font.weight: Font.Bold
                tracking: 0.22
                color: alertRow.tone
                anchors.verticalCenter: parent.verticalCenter
            }
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { to: 0.45; duration: 600; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1; duration: 600; easing.type: Easing.InOutSine }
            }
        }
    }
}
