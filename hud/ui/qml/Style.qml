pragma Singleton
import QtQuick

// Theme + units for the whole HUD. Everything here derives from the `cfg`
// property map (config, flattened), so a settings change restyles the HUD
// live. `ch`/`cw` are 1% of the projection box's height/width — the QML
// equivalent of the old CSS cqh/cqw units — set by Main.qml.
QtObject {
    // projection-box units (Main.qml binds these)
    property real ch: 4.8
    property real cw: 6.4

    // palette — pure black is load-bearing: black is invisible in the
    // windshield reflection, so only lit pixels appear to float.
    readonly property color bg: "#000000"
    readonly property color fg: "#f2f9ff"
    readonly property color accent: cfg.theme_accent || "#3ce0ff"
    readonly property color warn: "#ffb300"
    readonly property color crit: "#ff3b30"
    readonly property color dim: "#5b7683"
    readonly property color faint: "#31444e"
    readonly property color regen: "#3cff9d"

    readonly property real glow: cfg.theme_glow === undefined ? 0.85 : cfg.theme_glow

    // font packs: a display face for numerals + a text face for labels
    readonly property var fonts: ({
        chakra: { display: "Chakra Petch", text: "Rajdhani" },
        orbit: { display: "Orbitron", text: "Rajdhani" },
        mono: { display: "JetBrains Mono", text: "JetBrains Mono" },
        round: { display: "Quicksand", text: "Quicksand" }
    })
    readonly property var pack: fonts[cfg.theme_font] || fonts.chakra
    readonly property string fontDisplay: pack.display
    readonly property string fontText: pack.text

    // units
    readonly property bool mph: cfg.units_speed !== "kph"
    readonly property bool fahrenheit: cfg.units_temp !== "c"
    readonly property string speedUnit: mph ? "mph" : "kph"

    function speed(kph) { return mph ? kph * 0.621371 : kph }
    function temp(c) {
        return fahrenheit ? Math.round(c * 1.8 + 32) + "°" : Math.round(c) + "°"
    }
    function has(v) { return v !== undefined && v !== null }

    // WMO weather code → icon name / label
    function weatherIcon(code) {
        if (code === 0) return "sun"
        if (code <= 2) return "partly"
        if (code === 3) return "cloud"
        if (code <= 48) return "fog"
        if (code <= 67) return "rain"
        if (code <= 77) return "snow"
        if (code <= 82) return "rain"
        if (code <= 86) return "snow"
        return "storm"
    }
    function weatherLabel(code) {
        if (code === 0) return "CLEAR"
        if (code <= 2) return "PARTLY CLOUDY"
        if (code === 3) return "OVERCAST"
        if (code <= 48) return "FOG"
        if (code <= 57) return "DRIZZLE"
        if (code <= 67) return "RAIN"
        if (code <= 77) return "SNOW"
        if (code <= 82) return "SHOWERS"
        if (code <= 86) return "SNOW SHOWERS"
        return "THUNDERSTORM"
    }
}
