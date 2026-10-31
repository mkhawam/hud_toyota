"""Run the HUD with the native display.

Qt owns the main thread; the asyncio backend (providers, alerts, settings
web server) runs in a worker thread with its own event loop. The Bridge
forwards bus traffic into QML and carries menu writes back.

Platform selection:
- Pi (no desktop session): Qt's ``eglfs`` platform renders straight to the
  display via KMS — no compositor, no cursor. The KMS device is resolved
  to the card that actually has the HDMI connector (the Pi 5 has a separate
  render-only card that eglfs would otherwise pick).
- Desktop (Windows/macOS/Linux with a session): a normal 640×480 window,
  for development.
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path

from ..core.bus import Bus
from ..core.config import Config

log = logging.getLogger(__name__)

QML_DIR = Path(__file__).resolve().parent / "qml"
FONT_DIR = Path(__file__).resolve().parents[2] / "web" / "src" / "assets" / "fonts"


def _configure_platform(size: str | None) -> None:
    """Pick eglfs on a bare Linux console; leave desktops alone."""
    if sys.platform != "linux":
        return
    if "QT_QPA_PLATFORM" not in os.environ:
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
            return  # desktop session: normal window
        os.environ["QT_QPA_PLATFORM"] = "eglfs"
    if os.environ["QT_QPA_PLATFORM"] != "eglfs":
        return
    os.environ.setdefault("QT_QPA_EGLFS_HIDECURSOR", "1")
    os.environ.setdefault("QT_QPA_EGLFS_INTEGRATION", "eglfs_kms")
    if "QT_QPA_EGLFS_KMS_CONFIG" not in os.environ:
        # /sys/class/drm/card1-HDMI-A-1 → card1 (the card that owns the connector)
        cards = sorted({Path(p).name.split("-")[0]
                        for p in glob.glob("/sys/class/drm/card*-HDMI-A-*")})
        if cards:
            cfg = {"device": f"/dev/dri/{cards[0]}", "hwcursor": False}
            path = Path(tempfile.gettempdir()) / "hud-eglfs-kms.json"
            path.write_text(json.dumps(cfg))
            os.environ["QT_QPA_EGLFS_KMS_CONFIG"] = str(path)
            log.info("eglfs on %s", cfg["device"])


def _load_fonts() -> None:
    from PySide6.QtGui import QFontDatabase

    for ttf in sorted(FONT_DIR.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(ttf)) < 0:
            log.warning("font failed to load: %s", ttf.name)


def run_with_ui(
    config: Config,
    source: str,
    size: str | None = None,
    screenshot: str | None = None,
    screenshot_after: float = 4.0,
    press: str | None = None,
) -> int:
    _configure_platform(size)

    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from ..app import serve
    from .bridge import Bridge

    app = QGuiApplication(sys.argv)
    app.setApplicationName("hud")
    _load_fonts()

    bus = Bus()
    loop = asyncio.new_event_loop()
    stop = asyncio.Event()
    bridge = Bridge(bus, config, loop)

    def backend() -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(serve(bus, config, source, stop, extra=[bridge.forward()],
                                          screenshot=bridge.screenshot))
        except Exception:
            log.exception("backend crashed")
            app.exit(1)  # thread-safe; systemd restarts the whole thing

    thread = threading.Thread(target=backend, name="hud-backend", daemon=True)
    thread.start()

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("topics", bridge.topics)
    ctx.setContextProperty("cfg", bridge.cfg)
    ctx.setContextProperty("bridge", bridge)
    ctx.setContextProperty("settingsPort", int(config.get("server.port", 8000)))
    engine.addImportPath(str(QML_DIR.parent))

    w, h = 640, 480
    if size:
        w, h = (int(v) for v in size.lower().split("x"))
    ctx.setContextProperty("windowW", w)
    ctx.setContextProperty("windowH", h)

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        log.error("QML failed to load")
        loop.call_soon_threadsafe(stop.set)
        return 1
    window = engine.rootObjects()[0]

    if press:
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent

        def send_keys() -> None:
            # dev/testing: synthesize key presses (e.g. "Return,Down,Down")
            for name in press.split(","):
                key = getattr(Qt.Key, f"Key_{name.strip()}")
                for etype in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                    QGuiApplication.sendEvent(window, QKeyEvent(etype, key, Qt.KeyboardModifier.NoModifier))

        QTimer.singleShot(1500, send_keys)

    if screenshot:
        from PySide6.QtCore import Q_ARG, QMetaObject

        def grab() -> None:
            # Main.qml's saveShot() uses grabToImage and quits when written —
            # works on eglfs too, where screen grabs may not.
            QMetaObject.invokeMethod(window, "saveShot", Q_ARG("QVariant", str(Path(screenshot).resolve())))
            QTimer.singleShot(5000, app.quit)  # safety net

        QTimer.singleShot(int(screenshot_after * 1000), grab)

    code = app.exec()
    loop.call_soon_threadsafe(stop.set)
    thread.join(timeout=5)
    return code
