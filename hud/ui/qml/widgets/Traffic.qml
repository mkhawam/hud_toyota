import QtQuick
import ".."

// Quiet unless traffic is ≥15% below free-flow (or the road is closed).
GlowText {
    id: w
    readonly property var flow: topics.traffic_flow
    readonly property int slowdown: flow ? Math.round((1 - flow.ratio) * 100) : 0
    readonly property bool heavy: !!flow && (flow.road_closed || slowdown >= 40)
    property bool shown: !!flow && (flow.road_closed || slowdown >= 15)
    text: flow && flow.road_closed ? "ROAD CLOSED" : "TRAFFIC −" + slowdown + "%"
    size: 3 * Style.ch
    font.weight: Font.Bold
    tracking: 0.18
    color: heavy ? Style.crit : Style.warn
    SequentialAnimation on opacity {
        running: w.heavy
        loops: Animation.Infinite
        onStopped: w.opacity = 1
        NumberAnimation { to: 0.45; duration: 600 }
        NumberAnimation { to: 1; duration: 600 }
    }
}
