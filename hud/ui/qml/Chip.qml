import QtQuick

// Small outlined badge (limit / cruise / source).
Rectangle {
    id: chip
    property alias text: label.text
    property color tint: Style.dim
    property bool dashed: false
    property bool glowing: false
    property real size: 2.4

    implicitWidth: label.implicitWidth + 2 * Style.cw
    implicitHeight: label.implicitHeight + 0.6 * Style.ch
    color: "transparent"
    radius: 0.6 * Style.ch
    border.width: dashed ? 0 : 1
    border.color: tint

    // dashed outline (Rectangle can't dash its border)
    Canvas {
        anchors.fill: parent
        visible: chip.dashed
        onPaint: {
            const c = getContext("2d")
            c.reset()
            c.strokeStyle = chip.tint
            c.lineWidth = 1
            c.setLineDash([3, 3])
            c.strokeRect(0.5, 0.5, width - 1, height - 1)
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    GlowText {
        id: label
        anchors.centerIn: parent
        color: chip.tint
        glowAmount: chip.glowing ? Style.glow : 0
        size: chip.size * Style.ch
        font.weight: Font.DemiBold
        tracking: 0.22
    }
}
