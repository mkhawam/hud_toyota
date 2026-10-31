import QtQuick
import QtQuick.Window

// HUD shell. The content renders inside a projection box (config
// display.aspect, e.g. 3:1 for the windshield strip) that can be scaled and
// moved on the panel with the C-key calibration; everything outside it is
// pure black = invisible in the reflection.
//
// Keys (a keyboard-emulating button panel works the same):
//   OK/Enter  open the on-device menu      C  calibrate projection box
//   D         toggle debug overlay
Window {
    id: win
    width: windowW
    height: windowH
    visible: true
    color: "black"
    title: "HUD"

    readonly property var widgetFiles: ({
        speed: "Speed", rpm: "Rpm", power: "Power", clock: "Clock",
        coolant: "Coolant", fuel: "Fuel", alerts: "Alerts", source: "SourceBadge",
        weather: "Weather", traffic: "Traffic", dtc: "Dtc", trip: "Trip",
        zerosixty: "ZeroSixty", speedlimit: "SpeedLimit", lanes: "Lanes",
        cruise: "Cruise", transtemp: "TransTemp", intaketemp: "IntakeTemp"
    })

    // ---- calibration state (live while the C-mode is on) --------------------
    property bool calibrating: false
    property bool debugLocal: false
    property real calScale: cfg.display_scale || 1
    property real calX: cfg.display_offset_x || 0
    property real calY: cfg.display_offset_y || 0
    property string calNote: ""

    // dev/diagnostics: render one frame to a file, then quit (--screenshot)
    function saveShot(path) {
        root.grabToImage(function (r) {
            console.log("screenshot " + (r.saveToFile(path) ? "saved to " : "FAILED: ") + path)
            Qt.quit()
        })
    }
    // live capture for GET /api/screenshot (what the panel shows right now)
    Connections {
        target: bridge
        function onShotRequested(path) {
            root.grabToImage(function (r) { bridge.shotDone(path, r.saveToFile(path)) })
        }
    }

    function resetCal() {
        calScale = cfg.display_scale || 1
        calX = cfg.display_offset_x || 0
        calY = cfg.display_offset_y || 0
    }
    // phone/menu edits to display.* re-seed unless mid-calibration here
    readonly property var savedDisplay: [cfg.display_scale, cfg.display_offset_x, cfg.display_offset_y]
    onSavedDisplayChanged: if (!calibrating) resetCal()

    readonly property bool night: {
        const mode = cfg.theme_night_mode || "auto"
        if (mode !== "auto") return mode === "on"
        if (Style.has(topics.vehicle_lights_on)) return topics.vehicle_lights_on > 0
        const wx = topics.weather_current
        return !!wx && !wx.is_day
    }

    Item {
        id: root
        anchors.fill: parent
        focus: true

        Rectangle { anchors.fill: parent; color: "black" }  // so frame grabs are opaque too

        Keys.onPressed: (ev) => {
            if (menu.open) return
            const big = (ev.modifiers & Qt.ShiftModifier) ? 0.02 : 0.005
            if (ev.key === Qt.Key_C) { win.calibrating = !win.calibrating; if (!win.calibrating) win.resetCal(); ev.accepted = true; return }
            if (ev.key === Qt.Key_D) { win.debugLocal = !win.debugLocal; ev.accepted = true; return }
            if (!win.calibrating) {
                if (ev.key === Qt.Key_Return || ev.key === Qt.Key_Enter) { menu.show(); ev.accepted = true }
                return
            }
            switch (ev.key) {
            case Qt.Key_Left: win.calX -= big; break
            case Qt.Key_Right: win.calX += big; break
            case Qt.Key_Up: win.calY -= big; break
            case Qt.Key_Down: win.calY += big; break
            case Qt.Key_Plus: case Qt.Key_Equal: win.calScale = Math.min(1, win.calScale + 0.02); break
            case Qt.Key_Minus: case Qt.Key_Underscore: win.calScale = Math.max(0.1, win.calScale - 0.02); break
            case Qt.Key_S: case Qt.Key_Return: case Qt.Key_Enter:
                bridge.patchSection("display", { scale: win.calScale, offset_x: win.calX, offset_y: win.calY })
                win.calNote = "SAVED"; noteTimer.restart(); break
            case Qt.Key_Escape: win.calibrating = false; win.resetCal(); break
            default: return
            }
            ev.accepted = true
        }
        Timer { id: noteTimer; interval: 1500; onTriggered: win.calNote = "" }

        // ---- projection box ---------------------------------------------------
        Item {
            id: vp
            readonly property real ar: {
                const parts = String(cfg.display_aspect || "").split(":").map(Number)
                return (parts.length === 2 && parts[0] > 0 && parts[1] > 0) ? parts[0] / parts[1] : 0
            }
            width: ar ? Math.min(root.width, root.height * ar) : root.width
            height: ar ? Math.min(root.height, root.width / ar) : root.height
            x: (root.width - width) / 2 + win.calX * root.width
            y: (root.height - height) / 2 + win.calY * root.height
            scale: win.calScale

            Binding { target: Style; property: "ch"; value: vp.height / 100 }
            Binding { target: Style; property: "cw"; value: vp.width / 100 }

            Item {
                id: hud
                anchors.fill: parent
                // windshield reflection flips the image — flip it back
                transform: Scale { origin.x: hud.width / 2; xScale: cfg.mirror === false ? 1 : -1 }

                readonly property real padX: 2.5 * Style.cw
                readonly property real padY: 2 * Style.ch
                readonly property real colU: (width - 2 * padX) / 3.6
                readonly property var colX: [padX, padX + colU, padX + 2.6 * colU]
                readonly property var colW: [colU, 1.6 * colU, colU]
                readonly property real topH: Math.max(slotTL.contentH, slotTC.contentH, slotTR.contentH)
                readonly property real botH: Math.max(slotBL.contentH, slotBC.contentH, slotBR.contentH)
                readonly property var rowY: [padY, padY + topH, height - padY - botH]
                readonly property var rowH: [topH, height - 2 * padY - topH - botH, botH]

                Slot { id: slotTL; name: "top-left"; col: 0; row: 0 }
                Slot { id: slotTC; name: "top-center"; col: 1; row: 0 }
                Slot { id: slotTR; name: "top-right"; col: 2; row: 0 }
                Slot { name: "center-left"; col: 0; row: 1 }
                Slot { name: "center"; col: 1; row: 1 }
                Slot { name: "center-right"; col: 2; row: 1 }
                Slot { id: slotBL; name: "bottom-left"; col: 0; row: 2 }
                Slot { id: slotBC; name: "bottom-center"; col: 1; row: 2 }
                Slot { id: slotBR; name: "bottom-right"; col: 2; row: 2 }

                // blind-spot edge arrows (BSD_STAT side encoding unconfirmed:
                // until the on-car session, any nonzero lights both)
                readonly property int bsm: topics.vehicle_bsm_status || 0
                Repeater {
                    model: [{ side: "left", vals: [1, 3, 5, 7] }, { side: "right", vals: [2, 3, 6, 7] }]
                    GlowText {
                        required property var modelData
                        visible: hud.bsm > 0 && modelData.vals.indexOf(hud.bsm) >= 0
                        text: modelData.side === "left" ? "◀" : "▶"
                        x: modelData.side === "left" ? 0.5 * Style.cw : hud.width - width - 0.5 * Style.cw
                        anchors.verticalCenter: parent.verticalCenter
                        size: 6 * Style.ch
                        color: Style.warn
                    }
                }

                GlowText {   // internet widgets are showing cached data
                    visible: topics.net_online === false
                    text: "OFFLINE"
                    anchors.right: parent.right; anchors.bottom: parent.bottom
                    anchors.margins: 1.2 * Style.ch
                    size: 1.8 * Style.ch
                    font.weight: Font.DemiBold
                    tracking: 0.3
                    color: Style.faint
                    glowAmount: 0
                }
            }

            // night dim: a black veil is the cheap equivalent of brightness()
            Rectangle {
                anchors.fill: parent
                color: "black"
                opacity: win.night ? 1 - (cfg.theme_night_brightness || 0.55) : 0
                Behavior on opacity { NumberAnimation { duration: 800 } }
            }

            Rectangle {   // calibration frame
                anchors.fill: parent
                visible: win.calibrating
                color: "transparent"
                border.color: Style.accent
                border.width: 2
                Text {
                    anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottomMargin: 1 * Style.ch
                    color: Style.accent
                    font.family: Style.fontText
                    font.pixelSize: Math.max(10, 3 * Style.ch)
                    text: win.calNote || ("scale " + win.calScale.toFixed(2) + "  x " + win.calX.toFixed(3) + "  y " + win.calY.toFixed(3)
                                          + "   arrows move · +/− scale · OK save · C exit")
                }
            }
        }

        DebugPanel {
            visible: win.debugLocal || cfg.debug === true
            anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.margins: 6
            width: parent.width * 0.42
        }

        Menu {
            id: menu
            anchors.fill: parent
            onClosed: root.forceActiveFocus()
            onCalibrate: { win.calibrating = true; root.forceActiveFocus() }
        }
    }

    // one grid cell: stacks the widgets the layout assigns to it
    component Slot: Item {
        id: slot
        property string name
        property int col
        property int row
        readonly property real contentH: stack.implicitHeight
        x: hud.colX[col]
        y: hud.rowY[row]
        width: hud.colW[col]
        height: hud.rowH[row]

        readonly property var widgets: (cfg.layout || []).filter(it => it.slot === slot.name).map(it => it.widget)

        Column {
            id: stack
            anchors.centerIn: parent
            spacing: 1.6 * Style.ch
            Repeater {
                model: slot.widgets
                Loader {
                    required property var modelData
                    anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
                    source: win.widgetFiles[modelData] ? Qt.resolvedUrl("widgets/" + win.widgetFiles[modelData] + ".qml") : ""
                    visible: status === Loader.Ready && item && item.shown !== false
                }
            }
        }
    }
}
