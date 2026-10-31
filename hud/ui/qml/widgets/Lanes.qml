import QtQuick
import QtQuick.Shapes
import ".."

// Cluster-style lane indicator from the Toyota camera (status only — no
// geometry is broadcast). LKAWLSL/R: 0 none, 1/2 detected, 3 departure;
// refine after the on-car candump session.
Item {
    id: w
    readonly property var laneL: topics.vehicle_lane_left
    readonly property var laneR: topics.vehicle_lane_right
    readonly property bool buzzer: (topics.vehicle_lda_buzzer || 0) > 0
    property bool shown: Style.has(laneL) || Style.has(laneR)

    readonly property int detectedMin: 1
    readonly property int alertValue: 3

    implicitWidth: 15 * Style.cw
    implicitHeight: implicitWidth * 44 / 120

    function state(v) {
        if (!Style.has(v) || v < detectedMin) return "none"
        if (v === alertValue || buzzer) return "alert"
        return "detected"
    }
    function tone(s) { return s === "alert" ? Style.warn : s === "detected" ? Style.accent : Style.dim }

    Shape {
        width: 120
        height: 44
        scale: w.width / 120
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer

        ShapePath {   // car marker
            strokeColor: "transparent"
            fillColor: Style.dim
            PathSvg { path: "M57 36h6a2 2 0 0 1 2 2v2a2 2 0 0 1 -2 2h-6a2 2 0 0 1 -2 -2v-2a2 2 0 0 1 2 -2z" }
        }
        ShapePath {
            readonly property string s: w.state(w.laneL)
            strokeColor: w.tone(s)
            strokeWidth: 2.5
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            strokeStyle: s === "none" ? ShapePath.DashLine : ShapePath.SolidLine
            dashPattern: [2.4, 1.6]
            PathSvg { path: "M38 42 L52 4" }
        }
        ShapePath {
            readonly property string s: w.state(w.laneR)
            strokeColor: w.tone(s)
            strokeWidth: 2.5
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            strokeStyle: s === "none" ? ShapePath.DashLine : ShapePath.SolidLine
            dashPattern: [2.4, 1.6]
            PathSvg { path: "M82 42 L68 4" }
        }
    }
    opacity: (state(laneL) === "none" && state(laneR) === "none") ? 0.35 : 1
}
