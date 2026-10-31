"""Bridge between the bus and QML: config flattening, validated writes,
debug rows — plus a smoke test that the QML tree loads without errors."""

import asyncio
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from hud.core.bus import Bus  # noqa: E402
from hud.core.config import Config  # noqa: E402
from hud.ui.bridge import Bridge, flatten, qkey  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    return QCoreApplication.instance() or QGuiApplication([])


def make(tmp_path, qapp):
    cfg_path = tmp_path / "hud.yaml"
    cfg_path.write_text("units:\n  speed: mph\ntheme:\n  accent: '#3ce0ff'\n", encoding="utf-8")
    config = Config.load(cfg_path)
    bus = Bus()
    return Bridge(bus, config, asyncio.new_event_loop()), bus, config


def test_flatten_and_qkey():
    assert flatten({"theme": {"accent": "#fff", "glow": 1}, "mirror": True, "layout": [1]}) == {
        "theme_accent": "#fff", "theme_glow": 1, "mirror": True, "layout": [1],
    }
    assert qkey("vehicle.speed_kph") == "vehicle_speed_kph"


def test_config_and_topics_preinserted(tmp_path, qapp):
    bridge, _, _ = make(tmp_path, qapp)
    assert bridge.cfg.value("theme_accent") == "#3ce0ff"
    assert bridge.cfg.value("units_speed") == "mph"
    assert "vehicle_speed_kph" in bridge.topics.keys()   # binds before first data
    assert "net_ap" in bridge.topics.keys()


def test_batch_updates_topics(tmp_path, qapp):
    bridge, _, _ = make(tmp_path, qapp)
    bridge._apply_batch({"vehicle.rpm": 3200, "weather.current": {"temp_c": 21}})
    assert bridge.topics.value("vehicle_rpm") == 3200
    assert bridge.topics.value("weather_current")["temp_c"] == 21


def test_save_validates_persists_and_announces(tmp_path, qapp):
    bridge, bus, config = make(tmp_path, qapp)
    results = []
    bridge.saved.connect(lambda section, ok, msg: results.append((section, ok)))

    bridge._save_on_loop("theme", {**config.get("theme"), "accent": "#3cff9d"})
    assert config.get("theme.accent") == "#3cff9d"
    assert (tmp_path / "local.yaml").exists()
    assert bus.snapshot("config.updated")["config.updated"].value == {"section": "theme"}
    bridge._apply_config()
    assert bridge.cfg.value("theme_accent") == "#3cff9d"

    bridge._save_on_loop("theme", {"accent": "not-a-color"})   # rejected, nothing written
    assert config.get("theme.accent") == "#3cff9d"
    bridge._save_on_loop("server", {"port": 1})                 # not editable
    assert results == [("theme", True), ("theme", False), ("server", False)]


def test_debug_rows(tmp_path, qapp):
    bridge, bus, _ = make(tmp_path, qapp)
    bus.publish("vehicle.rpm", 1234.5)
    bus.publish("alerts.active", [{"id": "r0"}])
    rows = {r[0]: r for r in bridge.debugRows()}
    assert rows["vehicle.rpm"][1] == "1234.50"
    assert rows["alerts.active"][1].startswith("[{")
    assert rows["vehicle.rpm"][2] >= 0


def test_qml_loads_without_errors(tmp_path, qapp):
    """Every QML file compiles and Main.qml instantiates with real data."""
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from hud.ui.runner import QML_DIR, _load_fonts

    _load_fonts()
    bridge, _, _ = make(tmp_path, qapp)
    bridge.cfg.insert("layout", [
        {"widget": w, "slot": "center"} for w in (
            "speed", "rpm", "power", "clock", "coolant", "fuel", "alerts", "source",
            "weather", "traffic", "dtc", "trip", "zerosixty", "speedlimit", "lanes",
            "cruise", "transtemp", "intaketemp",
        )
    ])
    bridge._apply_batch({
        "vehicle.speed_kph": 80.0, "vehicle.rpm": 2500, "vehicle.gear": "D4",
        "weather.current": {"temp_c": 20, "code": 2, "is_day": True},
        "alerts.active": [{"id": "r0", "level": "warn", "message": "LOW FUEL"}],
        "road.limit": {"limit_kph": 72.4, "limit_mph": 45, "estimated": True},
    })

    warnings = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    ctx = engine.rootContext()
    for name, obj in (("topics", bridge.topics), ("cfg", bridge.cfg), ("bridge", bridge)):
        ctx.setContextProperty(name, obj)
    for name, val in (("settingsPort", 8000), ("windowW", 640), ("windowH", 480)):
        ctx.setContextProperty(name, val)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    for _ in range(20):
        qapp.processEvents()
    assert engine.rootObjects(), "Main.qml failed to load"
    assert warnings == [], "\n".join(warnings)
