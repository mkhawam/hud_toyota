import QtQuick

// Icon + value + tracked label (coolant, fuel, trans/intake temps).
Row {
    id: stat
    property string icon: "thermo"
    property string value: "--"
    property string label: ""
    property bool warn: false
    property bool shown: true

    spacing: 1 * Style.cw

    Icon {
        anchors.verticalCenter: parent.verticalCenter
        name: stat.icon
        color: stat.warn ? Style.warn : Style.dim
    }
    Column {
        anchors.verticalCenter: parent.verticalCenter
        GlowText {
            text: stat.value
            font.family: Style.fontDisplay
            size: 5.4 * Style.ch
            font.weight: Font.DemiBold
            color: stat.warn ? Style.warn : Style.fg
            glowAmount: stat.warn ? Style.glow : 0
        }
        GlowText {
            text: stat.label
            size: 2 * Style.ch
            font.weight: Font.DemiBold
            tracking: 0.32
            color: Style.dim
            glowAmount: 0
        }
    }
}
