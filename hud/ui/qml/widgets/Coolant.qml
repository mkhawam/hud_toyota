import QtQuick
import ".."

Stat {
    readonly property var c: topics.vehicle_coolant_c
    icon: "thermo"
    label: "COOLANT"
    value: Style.has(c) ? Style.temp(c) : "--°"
    warn: Style.has(c) && c >= 105
}
