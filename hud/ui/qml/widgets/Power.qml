import QtQuick
import ".."

// Hybrid power meter, stock-cluster style: CHG (regen) fills left of the
// zero mark, drive power fills right; the top 20% reads as PWR (red).
Column {
    id: w
    property bool shown: true
    width: (cfg.theme_rpm_width || 44) * Style.cw
    spacing: 1 * Style.ch

    readonly property int count: 48
    readonly property real maxKw: cfg.gauges_power_max_kw || 150
    readonly property real regenKw: cfg.gauges_power_regen_kw || 50
    readonly property real kw: topics.vehicle_power_kw || 0
    readonly property int zero: Math.round(regenKw / (regenKw + maxKw) * count)

    Item {
        width: parent.width
        height: gauge.implicitHeight
        Segments {
            id: gauge
            anchors.fill: parent
            count: w.count
            gapRatio: 0.6
            colorAt: function (i) {
                if (i < w.zero) {
                    const litFrom = w.zero - Math.min(w.zero, Math.ceil(Math.max(0, -w.kw) / w.regenKw * w.zero))
                    return i >= litFrom ? Style.regen : Style.faint
                }
                const drive = w.count - w.zero
                const lit = Math.min(drive, Math.ceil(Math.max(0, w.kw) / w.maxKw * drive))
                const pwr = (i - w.zero) / drive >= 0.8
                if (i - w.zero >= lit) return pwr ? "#3b2023" : Style.faint
                return pwr ? Style.crit : Style.accent
            }
        }
        Rectangle {   // zero mark
            x: w.zero * gauge.unit * (1 + gauge.gapRatio) - gauge.unit * gauge.gapRatio / 2 - width / 2
            y: -0.3 * Style.ch
            width: Math.max(1, 0.15 * Style.cw)
            height: parent.height + 0.6 * Style.ch
            color: Style.dim
        }
    }
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 1.2 * Style.cw
        GlowText { text: "CHG"; size: 1.8 * Style.ch; font.weight: Font.DemiBold; tracking: 0.2; color: Style.dim; glowAmount: 0; anchors.baseline: value.baseline }
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
            text: Math.abs(Math.round(w.kw))
            size: 2.8 * Style.ch
            font.weight: Font.Medium
            color: w.kw < -1 ? Style.regen : Style.fg
            glowAmount: 0
        }
        GlowText { text: "kW"; size: 2.2 * Style.ch; tracking: 0.2; color: Style.dim; glowAmount: 0; anchors.baseline: value.baseline }
        GlowText { text: "PWR"; size: 1.8 * Style.ch; font.weight: Font.DemiBold; tracking: 0.2; color: Style.crit; opacity: 0.75; glowAmount: 0; anchors.baseline: value.baseline }
        GlowText {   // hybrid battery state of charge
            visible: Style.has(topics.vehicle_hv_battery_pct)
            text: "HV " + Math.round(topics.vehicle_hv_battery_pct || 0) + "%"
            size: 1.8 * Style.ch; font.weight: Font.DemiBold; tracking: 0.2
            color: Style.dim; glowAmount: 0; anchors.baseline: value.baseline
        }
    }
}
