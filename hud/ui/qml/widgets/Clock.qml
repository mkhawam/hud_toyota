import QtQuick
import ".."

GlowText {
    id: w
    property bool shown: true
    property date now: new Date()
    text: Qt.formatTime(now, "h:mm AP").toLowerCase()
    size: 4.6 * Style.ch
    font.weight: Font.DemiBold
    tracking: 0.08
    color: Style.dim
    glowAmount: 0
    Timer { interval: 1000; running: true; repeat: true; onTriggered: w.now = new Date() }
}
