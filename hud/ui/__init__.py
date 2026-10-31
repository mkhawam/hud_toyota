"""Native HUD display: PySide6 + QML in the same process as the backend.

The asyncio backend (bus, providers, settings web server) runs in a worker
thread; the bus is bridged straight into QML property maps on the Qt main
thread — no WebSocket, no browser. On the Pi, Qt's eglfs platform draws
directly to the display (no compositor), so there is no cursor, no window
manager, and no keyring dialog to fight.
"""
