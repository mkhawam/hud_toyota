import QtQuick
import ".."

Column {
    id: w
    readonly property var wx: topics.weather_current
    property bool shown: !!wx
    property real nowS: Date.now() / 1000
    readonly property real ageMin: (wx && wx.fetched_at) ? (nowS - wx.fetched_at) / 60 : 0
    opacity: ageMin > 30 ? 0.6 : 1
    spacing: 0.4 * Style.ch

    Timer { interval: 60000; running: true; repeat: true; onTriggered: w.nowS = Date.now() / 1000 }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 0.8 * Style.cw
        Icon {
            name: w.wx ? Style.weatherIcon(w.wx.code) : "cloud"
            size: 5
            anchors.verticalCenter: parent.verticalCenter
        }
        GlowText {
            text: w.wx ? Style.temp(w.wx.temp_c) : ""
            font.family: Style.fontDisplay
            size: 6.4 * Style.ch
            font.weight: Font.DemiBold
            glowAmount: 0
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    GlowText {
        anchors.horizontalCenter: parent.horizontalCenter
        text: w.wx ? Style.weatherLabel(w.wx.code) : ""
        size: 2 * Style.ch
        font.weight: Font.DemiBold
        tracking: 0.28
        color: Style.dim
        glowAmount: 0
    }
    GlowText {
        anchors.horizontalCenter: parent.horizontalCenter
        visible: w.ageMin > 30
        text: Math.round(w.ageMin) + "m ago"
        size: 1.8 * Style.ch
        color: Style.warn
        glowAmount: 0
    }
}
