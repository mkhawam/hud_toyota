import QtQuick
import ".."

// Trip computer: average + instant economy, distance and moving time.
Column {
    id: w
    property bool shown: Style.has(topics.trip_distance_km)

    function econ(lp100k) {
        if (!Style.has(lp100k) || lp100k <= 0) return "--"
        return Style.mph ? (235.215 / lp100k).toFixed(1) : lp100k.toFixed(1)
    }
    readonly property string distance: {
        const km = topics.trip_distance_km || 0
        return Style.mph ? (km * 0.621371).toFixed(1) + " mi" : km.toFixed(1) + " km"
    }
    readonly property string duration: {
        const s = topics.trip_time_s || 0
        return Math.floor(s / 3600) + ":" + String(Math.floor((s % 3600) / 60)).padStart(2, "0")
    }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 0.8 * Style.cw
        GlowText {
            id: avg
            text: w.econ(topics.trip_avg_lp100k)
            font.family: Style.fontDisplay
            size: 4.6 * Style.ch
            font.weight: Font.DemiBold
            glowAmount: 0
        }
        GlowText {
            text: Style.mph ? "MPG" : "L/100"
            size: 2 * Style.ch
            font.weight: Font.DemiBold
            tracking: 0.18
            color: Style.dim
            glowAmount: 0
            anchors.baseline: avg.baseline
        }
        GlowText {
            text: w.econ(topics.trip_instant_lp100k) + " now"
            size: 2.2 * Style.ch
            color: Style.dim
            glowAmount: 0
            anchors.baseline: avg.baseline
        }
    }
    GlowText {
        anchors.horizontalCenter: parent.horizontalCenter
        text: w.distance + " · " + w.duration
        size: 2.2 * Style.ch
        font.weight: Font.Medium
        tracking: 0.06
        color: Style.dim
        glowAmount: 0
    }
}
