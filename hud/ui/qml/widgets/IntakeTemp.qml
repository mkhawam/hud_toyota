import QtQuick
import ".."

Stat {
    readonly property var c: topics.vehicle_intake_temp_c
    icon: "thermo"
    label: "INTAKE"
    value: Style.has(c) ? Style.temp(c) : "--°"
    warn: Style.has(c) && c >= 70
}
