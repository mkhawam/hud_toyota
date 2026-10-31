import QtQuick
import ".."

// US-style speed limit sign; dashed + "~" when the limit is estimated.
Rectangle {
    id: w
    readonly property var lim: topics.road_limit
    property bool shown: !!lim
    implicitWidth: col.implicitWidth + 2.8 * Style.cw
    implicitHeight: col.implicitHeight + 1.6 * Style.ch
    color: "transparent"
    radius: 1 * Style.ch
    border.width: 0.35 * Style.ch
    border.color: Style.fg
    Column {
        id: col
        anchors.centerIn: parent
        GlowText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "SPEED LIMIT"
            size: 1.7 * Style.ch
            font.weight: Font.DemiBold
            tracking: 0.18
            color: Style.dim
            glowAmount: 0
        }
        GlowText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: w.lim ? (w.lim.estimated ? "~" : "") + (Style.mph ? w.lim.limit_mph : Math.round(w.lim.limit_kph)) : ""
            font.family: Style.fontDisplay
            size: 5.6 * Style.ch
            font.weight: Font.Bold
        }
    }
}
