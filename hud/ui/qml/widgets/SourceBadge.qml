import QtQuick
import ".."

// Which vehicle source is live (auto manager): CAN / OBD / NO VEHICLE.
Chip {
    readonly property var src: topics.vehicle_source
    property bool shown: Style.has(src)
    readonly property var labels: ({ can: "CAN", "can-obd": "CAN·OBD", elm327: "OBD", none: "NO VEHICLE" })
    text: labels[src] || String(src || "")
    tint: src === "none" ? Style.warn : Style.dim
    size: 2
}
