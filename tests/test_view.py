"""Terminal HUD (hud-view) rendering."""

from hud.view import big_number, render, speed_text, temp_text

SNAP = {
    "vehicle.source": "can-obd",
    "vehicle.speed_kph": 88.5,
    "vehicle.rpm": 2100.0,
    "vehicle.throttle_pct": 20.0,
    "vehicle.coolant_c": 90.0,
    "vehicle.battery_v": 14.32,
    "vehicle.can_obd": {"iface": "can1", "channels": ["rpm", "speed_kph"]},
    "alerts.active": [{"message": "COOLANT HOT", "level": "critical"}],
    "trip.distance_km": 16.09,
    "trip.time_s": 1500,
}
CFG = {"units": {"speed": "mph", "temp": "f"}}


def test_units():
    assert speed_text(88.5, mph=True) == "55"
    assert speed_text(88.5, mph=False) == "88"
    assert speed_text(None, mph=True) == "--"
    assert temp_text(90.0, True) == "194°F"
    assert temp_text(None, True) == "--"


def test_big_digits_are_five_rows():
    rows = big_number("55")
    assert len(rows) == 5 and all(rows)


def test_render_plain_frame():
    text = "\n".join(render(SNAP, CFG, 80, color=False))
    assert "\x1b" not in text
    assert "CAN·OBD" in text
    assert "COOLANT HOT" in text
    assert "mph" in text
    assert "2100" in text
    assert "Coolant: 194°F" in text
    assert "Battery: 14.3 V" in text
    assert "Fuel: --" in text
    assert "Trip 10.0 mi  0:25" in text
    assert "OBD over can1" in text


def test_render_without_backend():
    text = "\n".join(render({}, {}, 80, color=False, error="Connection refused"))
    assert "NO VEHICLE" in text
    assert "backend unreachable" in text
