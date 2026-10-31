import QtQuick
import QtQuick.Effects

// Row of tick segments (EV-cluster gauge). `colorAt(i)` decides each
// segment's color; the parent widget owns the logic.
Item {
    id: seg
    property int count: 32
    property real gapRatio: 0.37      // gap / segment width
    property var colorAt: function (i) { return Style.faint }

    readonly property real unit: width / (count + (count - 1) * gapRatio)
    implicitHeight: 2.6 * Style.ch

    Row {
        id: row
        anchors.fill: parent
        spacing: seg.unit * seg.gapRatio
        Repeater {
            model: seg.count
            Rectangle {
                width: seg.unit
                height: row.height
                radius: Math.min(width, height) * 0.17
                color: seg.colorAt(index)
            }
        }
    }

    layer.enabled: Style.glow > 0.05
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: Qt.rgba(Style.accent.r, Style.accent.g, Style.accent.b, 0.45 * Style.glow)
        shadowBlur: 0.25
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 0
        blurMax: 16
    }
}
