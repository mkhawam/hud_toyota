import QtQuick
import QtQuick.Shapes

// Minimal 24×24 stroke icons (same drawings as the web HUD had), tinted by
// `color` so warn states and night-dim apply for free.
Item {
    id: icon
    property string name: "warn"
    property color color: Style.dim
    property real size: 4.2

    implicitWidth: size * Style.ch
    implicitHeight: size * Style.ch

    readonly property var shapes: ({
        sun: { s: "M8 12a4 4 0 1 0 8 0a4 4 0 1 0 -8 0M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.5 1.5M16.9 16.9l1.5 1.5M18.4 5.6l-1.5 1.5M7.1 16.9l-1.5 1.5", f: "" },
        partly: { s: "M4.9 7.5a2.6 2.6 0 1 0 5.2 0a2.6 2.6 0 1 0 -5.2 0M7.5 2.8v1.4M2.8 7.5h1.4M4.2 4.2l1 1M9 19h8.2a3.4 3.4 0 0 0 .36-6.78A4.6 4.6 0 0 0 8.8 11.5 3.7 3.7 0 0 0 9 19Z", f: "" },
        cloud: { s: "M6.5 17h9.5a3.8 3.8 0 0 0 .4-7.58A5.2 5.2 0 0 0 6.3 8.5 4.1 4.1 0 0 0 6.5 17Z", f: "" },
        fog: { s: "M7 12.5h10.5a3.2 3.2 0 0 0 .3-6.38A4.6 4.6 0 0 0 8.9 5.4 3.4 3.4 0 0 0 7 12.5ZM5 16.5h14M7 20h10", f: "" },
        rain: { s: "M7 14h9.5a3.4 3.4 0 0 0 .36-6.78A4.7 4.7 0 0 0 7.8 6.3 3.6 3.6 0 0 0 7 14ZM9 17l-1 3M13 17l-1 3M17 17l-1 3", f: "" },
        snow: { s: "M7 14h9.5a3.4 3.4 0 0 0 .36-6.78A4.7 4.7 0 0 0 7.8 6.3 3.6 3.6 0 0 0 7 14Z",
                f: "M8.4 18a.6 .6 0 1 0 1.2 0a.6 .6 0 1 0 -1.2 0M12.4 20a.6 .6 0 1 0 1.2 0a.6 .6 0 1 0 -1.2 0M15.9 17.5a.6 .6 0 1 0 1.2 0a.6 .6 0 1 0 -1.2 0" },
        storm: { s: "M7 13h9.5a3.4 3.4 0 0 0 .36-6.78A4.7 4.7 0 0 0 7.8 5.3 3.6 3.6 0 0 0 7 13ZM13 13l-2.5 4h3L11 21", f: "" },
        thermo: { s: "M10.5 4.5a1.8 1.8 0 0 1 3.6 0v8.2a4 4 0 1 1-3.6 0ZM12.3 9v6.5", f: "" },
        fuel: { s: "M5.9 4h6.2a1.4 1.4 0 0 1 1.4 1.4v13.2a1.4 1.4 0 0 1 -1.4 1.4h-6.2a1.4 1.4 0 0 1 -1.4 -1.4v-13.2a1.4 1.4 0 0 1 1.4 -1.4ZM7 8h4M13.5 10h1.6l2.4 2.4V18a1.6 1.6 0 0 1-3.2 0v-3.5h-0.8", f: "" },
        warn: { s: "M12 4 21.5 20h-19ZM12 10v4.5", f: "M11.5 17a.5 .5 0 1 0 1 0a.5 .5 0 1 0 -1 0" }
    })
    readonly property var shape: shapes[name] || shapes.warn

    Shape {
        width: 24
        height: 24
        scale: icon.width / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: icon.color
            strokeWidth: 1.8
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: icon.shape.s }
        }
        ShapePath {
            strokeColor: "transparent"
            fillColor: icon.shape.f ? icon.color : "transparent"
            PathSvg { path: icon.shape.f || "M0 0" }
        }
    }
}
