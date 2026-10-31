import QtQuick
import ".."

// Segmented RPM gauge with the gear inline. Range/redline from config.
Column {
    id: w
    property bool shown: true
    width: (cfg.theme_rpm_width || 44) * Style.cw
    spacing: 1 * Style.ch

    readonly property real maxRpm: cfg.gauges_rpm_max || 7000
    readonly property real redline: cfg.gauges_rpm_redline || 6200
    readonly property real rpm: topics.vehicle_rpm || 0
    readonly property int lit: Math.round(Math.min(rpm, maxRpm) / maxRpm * 32)

    Segments {
        width: parent.width
        count: 32
        colorAt: function (i) {
            const red = (i / 32) * w.maxRpm >= w.redline
            if (i >= w.lit) return red ? "#3b2023" : Style.faint
            return red ? Style.crit : Style.accent
        }
    }
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 1.2 * Style.cw
        GlowText {
            visible: Style.has(topics.vehicle_gear)
            text: topics.vehicle_gear || ""
            font.family: Style.fontDisplay
            size: 3.4 * Style.ch
            font.weight: Font.Bold
            color: Style.accent
            anchors.baseline: value.baseline
        }
        GlowText {
            id: value
            text: Math.round(w.rpm)
            size: 2.8 * Style.ch
            font.weight: Font.Medium
            glowAmount: 0
        }
        GlowText {
            text: "RPM"
            size: 2.2 * Style.ch
            tracking: 0.2
            color: Style.dim
            glowAmount: 0
            anchors.baseline: value.baseline
        }
    }
}
