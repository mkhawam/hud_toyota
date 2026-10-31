import QtQuick

// On-device quick settings, driven by Up/Down/Left/Right/OK (a keyboard-
// emulating button panel or any keyboard). Changes save immediately through
// the same validation as the phone settings page, so the HUD is adjustable
// in the car with no phone or network at all. Everything else lives in the
// web settings (reachable over the HUD's own Wi-Fi — see the last row).
Item {
    id: menu
    property bool open: false
    property int index: 0
    signal closed()
    signal calibrate()
    visible: open

    readonly property var presets: [
        { name: "Showroom", theme: { font: "chakra", accent: "#3ce0ff", glow: 0.85 } },
        { name: "Night Racer", theme: { font: "orbit", accent: "#b48cff", glow: 1.3 } },
        { name: "Terminal", theme: { font: "mono", accent: "#3cff9d", glow: 0.5 } },
        { name: "Classic", theme: { font: "chakra", accent: "#ffd23c", glow: 1.1 } },
        { name: "Soft", theme: { font: "round", accent: "#eaf6ff", glow: 0.4 } }
    ]
    function presetIndex() {
        for (let i = 0; i < presets.length; i++)
            if (presets[i].theme.accent === cfg.theme_accent && presets[i].theme.font === cfg.theme_font) return i
        return -1
    }
    function cycle(list, cur, dir) {
        const i = list.indexOf(cur)
        return list[((i < 0 ? 0 : i) + dir + list.length) % list.length]
    }

    readonly property var items: [
        { label: "Theme", value: presetIndex() >= 0 ? presets[presetIndex()].name : "Custom",
          step: (d) => bridge.patchSection("theme", presets[((presetIndex() < 0 ? 0 : presetIndex()) + d + presets.length) % presets.length].theme) },
        { label: "Speed units", value: Style.mph ? "MPH" : "KPH",
          step: (d) => bridge.patchSection("units", { speed: Style.mph ? "kph" : "mph" }) },
        { label: "Temperature", value: Style.fahrenheit ? "°F" : "°C",
          step: (d) => bridge.patchSection("units", { temp: Style.fahrenheit ? "c" : "f" }) },
        { label: "Night mode", value: String(cfg.theme_night_mode || "auto").toUpperCase(),
          step: (d) => bridge.patchSection("theme", { night_mode: cycle(["auto", "on", "off"], cfg.theme_night_mode || "auto", d) }) },
        { label: "Night brightness", value: Math.round((cfg.theme_night_brightness || 0.55) * 100) + "%",
          step: (d) => bridge.patchSection("theme", { night_brightness: Math.max(0.2, Math.min(1, Math.round(((cfg.theme_night_brightness || 0.55) + 0.05 * d) * 100) / 100)) }) },
        { label: "Glow", value: Math.round((Style.glow) * 100) + "%",
          step: (d) => bridge.patchSection("theme", { glow: Math.max(0, Math.min(2, Math.round((Style.glow + 0.1 * d) * 10) / 10)) }) },
        { label: "Mirror image", value: cfg.mirror === false ? "OFF" : "ON",
          step: (d) => bridge.saveSection("mirror", cfg.mirror === false) },
        { label: "Calibrate projection", value: "›", action: () => { menu.hide(); menu.calibrate() } },
        { label: "Debug overlay", value: cfg.debug === true ? "ON" : "OFF",
          step: (d) => bridge.saveSection("debug", cfg.debug !== true) },
        { label: "Reset trip", value: "›", action: () => { bridge.resetTrip(); toast.show("Trip reset") } },
        { label: "Phone settings", value: wifiText(), info: true },
        { label: "Close", value: "", action: () => menu.hide() }
    ]

    function wifiText() {
        const ap = topics.net_ap
        if (ap && ap.active)
            return "join " + ap.ssid + (ap.password ? " (" + ap.password + ")" : "") + " · " + ap.url.replace("http://", "")
        return ap && ap.url ? ap.url.replace("http://", "") : ("hud.local:" + settingsPort + "/settings")
    }

    function show() { index = 0; open = true; list.forceActiveFocus() }
    function hide() { open = false; closed() }

    Connections {
        target: bridge
        function onSaved(section, ok, msg) { if (!ok && menu.open) toast.show("Rejected: " + msg) }
    }

    Rectangle {   // dim the HUD behind the menu
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.82)
    }

    // The menu reads on the panel directly (driver adjusting while parked),
    // so it is drawn un-mirrored and full-panel, not in the projection box.
    Column {
        id: list
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.86, 560)
        spacing: 2
        focus: menu.open

        Keys.onPressed: (ev) => {
            const it = menu.items[menu.index]
            switch (ev.key) {
            case Qt.Key_Up: menu.index = (menu.index - 1 + menu.items.length) % menu.items.length; break
            case Qt.Key_Down: menu.index = (menu.index + 1) % menu.items.length; break
            case Qt.Key_Left: if (it.step) it.step(-1); break
            case Qt.Key_Right: if (it.step) it.step(1); else if (it.action) it.action(); break
            case Qt.Key_Return: case Qt.Key_Enter:
                if (it.action) it.action(); else if (it.step) it.step(1); break
            case Qt.Key_Escape: case Qt.Key_Back: menu.hide(); break
            default: return
            }
            ev.accepted = true
        }

        Text {
            text: "HUD MENU"
            color: Style.accent
            font.family: Style.fontText
            font.pixelSize: Math.round(menu.height * 0.045)
            font.weight: Font.Bold
            font.letterSpacing: 3
            bottomPadding: 6
        }
        Repeater {
            model: menu.items
            Rectangle {
                id: rowBg
                required property var modelData
                required property int index
                readonly property bool sel: index === menu.index
                width: list.width
                height: Math.round(menu.height * 0.062)
                radius: 4
                color: sel ? Qt.rgba(Style.accent.r, Style.accent.g, Style.accent.b, 0.18) : "transparent"
                border.color: sel ? Style.accent : "transparent"
                Text {
                    anchors.left: parent.left; anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: rowBg.modelData.label
                    color: rowBg.sel ? Style.fg : Style.dim
                    font.family: Style.fontText
                    font.pixelSize: Math.round(parent.height * 0.55)
                    font.weight: Font.DemiBold
                }
                Text {
                    anchors.right: parent.right; anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    width: rowBg.modelData.info ? parent.width * 0.62 : implicitWidth
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideLeft
                    text: (rowBg.sel && rowBg.modelData.step ? "‹  " : "") + rowBg.modelData.value
                          + (rowBg.sel && rowBg.modelData.step ? "  ›" : "")
                    color: rowBg.sel ? Style.accent : Style.fg
                    font.family: Style.fontText
                    font.pixelSize: Math.round(parent.height * (rowBg.modelData.info ? 0.42 : 0.55))
                    font.weight: Font.DemiBold
                }
            }
        }
        Text {
            text: "▲▼ select   ◀▶ change   OK apply   ESC close"
            color: Style.faint
            font.family: Style.fontText
            font.pixelSize: Math.round(menu.height * 0.032)
            topPadding: 6
        }
    }

    Rectangle {
        id: toast
        property string msg: ""
        function show(m) { msg = m; visible = true; toastTimer.restart() }
        visible: false
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: parent.height * 0.06
        width: toastText.implicitWidth + 24; height: toastText.implicitHeight + 12
        radius: 4
        color: Qt.rgba(0, 0, 0, 0.9)
        border.color: Style.dim
        Text { id: toastText; anchors.centerIn: parent; text: toast.msg; color: Style.fg; font.family: Style.fontText; font.pixelSize: Math.round(menu.height * 0.035) }
        Timer { id: toastTimer; interval: 2500; onTriggered: toast.visible = false }
    }
}
