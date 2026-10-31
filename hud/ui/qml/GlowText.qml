import QtQuick
import QtQuick.Effects

// Text with the HUD's soft bloom. Glow strength follows the theme; at 0 the
// effect layer is skipped entirely (no GPU cost).
Text {
    id: t
    property color glowColor: color
    property real glowAmount: Style.glow
    property real tracking: 0          // letter-spacing in em (like the CSS)
    // Pixel size lives here, not in `font`: deriving letter-spacing from
    // font.pixelSize would be a binding loop (any font change re-triggers it).
    property real size: 12

    color: Style.fg
    font.family: Style.fontText
    font.pixelSize: Math.max(1, size)
    font.letterSpacing: tracking * size
    renderType: Text.QtRendering

    layer.enabled: glowAmount > 0.05
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: Qt.rgba(t.glowColor.r, t.glowColor.g, t.glowColor.b, Math.min(1, 0.7 * t.glowAmount))
        shadowBlur: 0.55
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 0
        blurMax: 32
    }
}
