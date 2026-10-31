import QtQuick
import ".."

// 0–60 timer — quiet until a run has been recorded.
Column {
    id: w
    readonly property var zs: topics.trip_zero_sixty
    property bool shown: !!zs && (Style.has(zs.last_s) || Style.has(zs.best_s))
    GlowText {
        anchors.horizontalCenter: parent.horizontalCenter
        text: "0–60"
        size: 2 * Style.ch
        font.weight: Font.DemiBold
        tracking: 0.32
        color: Style.dim
        glowAmount: 0
    }
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 1 * Style.cw
        GlowText {
            id: last
            visible: !!w.zs && Style.has(w.zs.last_s)
            text: w.zs && Style.has(w.zs.last_s) ? w.zs.last_s.toFixed(2) + "s" : ""
            font.family: Style.fontDisplay
            size: 4 * Style.ch
            font.weight: Font.DemiBold
            color: Style.accent
        }
        GlowText {
            visible: !!w.zs && Style.has(w.zs.best_s)
            text: w.zs && Style.has(w.zs.best_s) ? "best " + w.zs.best_s.toFixed(2) + "s" : ""
            size: 2.2 * Style.ch
            color: Style.dim
            glowAmount: 0
            anchors.bottom: parent.bottom
        }
    }
}
