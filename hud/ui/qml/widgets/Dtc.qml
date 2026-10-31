import QtQuick
import ".."

// Diagnostic trouble codes — quiet unless the car reports some.
Column {
    id: w
    readonly property var codes: topics.vehicle_dtc_codes || []
    property bool shown: codes.length > 0
    GlowText {
        anchors.horizontalCenter: parent.horizontalCenter
        text: "CHECK ENGINE"
        size: 2.4 * Style.ch
        font.weight: Font.Bold
        tracking: 0.28
        color: Style.warn
    }
    Repeater {
        model: w.codes
        GlowText {
            required property var modelData
            anchors.horizontalCenter: parent.horizontalCenter
            text: modelData
            font.family: Style.fontDisplay
            size: 2.8 * Style.ch
            font.weight: Font.DemiBold
            glowAmount: 0
        }
    }
}
