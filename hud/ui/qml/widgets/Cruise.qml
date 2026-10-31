import QtQuick
import ".."

// ACC set-speed chip while cruise is engaged (range-gated until CACC's
// meaning is confirmed on-car).
Chip {
    readonly property var set: topics.vehicle_cruise_set
    property bool shown: (topics.vehicle_cruise_on || 0) > 0 && Style.has(set) && set >= 30 && set <= 200
    text: "SET " + (Style.has(set) ? Math.round(Style.speed(set)) : "")
    tint: Style.accent
    glowing: true
}
