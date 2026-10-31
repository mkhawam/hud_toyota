import QtQuick
import ".."

// Centerpiece: big digits, unit, and the limit chip. Overspeed turns the
// digits amber (>3 kph over) then pulsing red (>12 over). A camera-read
// sign (Road Sign Assist, TSS 2.5+) beats the OSM limit and shows without "~".
Column {
    id: w
    property bool shown: true
    spacing: 0

    // RSA enums — confirm on-car (sign-type id for a limit sign, mph unit id)
    readonly property int rsaSpeedSign: 1
    readonly property int rsaUnitMph: 1

    readonly property var kph: topics.vehicle_speed_kph
    readonly property var cameraLimitKph: {
        if (topics.vehicle_rsa_sign !== rsaSpeedSign) return null
        const v = topics.vehicle_rsa_value
        if (!Style.has(v) || v < 1 || v > 199) return null
        return topics.vehicle_rsa_unit === rsaUnitMph ? v * 1.609344 : v
    }
    readonly property var limitKph: Style.has(cameraLimitKph) ? cameraLimitKph : topics.road_speed_limit_kph
    readonly property real over: (Style.has(limitKph) && Style.has(kph)) ? kph - limitKph : 0

    readonly property var chip: {
        if (Style.has(cameraLimitKph))
            return { text: String(Math.round(Style.speed(cameraLimitKph))), estimated: false }
        const l = topics.road_limit
        if (!l) return null
        const n = Style.mph ? l.limit_mph : Math.round(l.limit_kph)
        return { text: (l.estimated ? "~" : "") + n, estimated: l.estimated }
    }

    GlowText {
        id: digits
        anchors.horizontalCenter: parent.horizontalCenter
        text: Style.has(w.kph) ? Math.round(Style.speed(w.kph)) : "--"
        font.family: Style.fontDisplay
        size: (cfg.theme_speed_size || 36) * Style.ch
        font.weight: Font.Bold
        lineHeight: 0.92
        color: w.over > 12 ? Style.crit : w.over > 3 ? Style.warn : Style.fg
        glowColor: w.over > 3 ? color : Style.accent

        SequentialAnimation on opacity {
            running: w.over > 12
            loops: Animation.Infinite
            onStopped: digits.opacity = 1
            NumberAnimation { to: 0.45; duration: 600; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1; duration: 600; easing.type: Easing.InOutSine }
        }
    }
    GlowText {
        anchors.horizontalCenter: parent.horizontalCenter
        text: Style.speedUnit.toUpperCase()
        size: 4 * Style.ch
        font.weight: Font.DemiBold
        tracking: 0.55
        color: Style.dim
        glowAmount: 0
    }
    Item { width: 1; height: w.chip ? 1 * Style.ch : 0 }
    Chip {
        anchors.horizontalCenter: parent.horizontalCenter
        visible: w.chip !== null
        text: w.chip ? "LIMIT " + w.chip.text : ""
        dashed: w.chip ? w.chip.estimated : false
        size: 2.6
    }
}
