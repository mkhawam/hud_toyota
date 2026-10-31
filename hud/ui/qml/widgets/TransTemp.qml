import QtQuick
import ".."

Stat {
    readonly property var c: topics.vehicle_trans_temp_c
    icon: "thermo"
    label: "TRANS"
    value: Style.has(c) ? Style.temp(c) : "--°"
    warn: Style.has(c) && c >= 110
}
