import QtQuick
import ".."

Stat {
    readonly property var pct: topics.vehicle_fuel_pct
    icon: "fuel"
    label: "FUEL"
    value: Style.has(pct) ? Math.round(pct) + "%" : "--%"
    warn: Style.has(pct) && pct <= 10
}
