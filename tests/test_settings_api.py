import asyncio

import yaml
from fastapi.testclient import TestClient

from hud.core.bus import Bus
from hud.core.config import Config
from hud.server import create_app


def make_client(tmp_path):
    cfg_path = tmp_path / "hud.yaml"
    cfg_path.write_text("units:\n  speed: mph\n  temp: f\n", encoding="utf-8")
    config = Config.load(cfg_path)
    bus = Bus()
    return TestClient(create_app(bus, config)), config, bus, tmp_path


def test_valid_units_save(tmp_path):
    client, config, bus, tmp = make_client(tmp_path)
    r = client.post("/api/settings/units", json={"speed": "kph", "temp": "c"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "value": {"speed": "kph", "temp": "c"}}
    assert config.get("units.speed") == "kph"
    assert yaml.safe_load((tmp / "local.yaml").read_text())["units"]["speed"] == "kph"
    # change announced on the bus for live HUD reload
    assert bus.snapshot("config.updated")["config.updated"].value == {"section": "units"}


def test_invalid_payload_writes_nothing(tmp_path):
    client, config, _, tmp = make_client(tmp_path)
    r = client.post("/api/settings/layout", json=[{"widget": "speed", "slot": "nowhere"}])
    assert r.status_code == 422
    assert not (tmp / "local.yaml").exists()
    r2 = client.post("/api/settings/units", json={"speed": "warp"})
    assert r2.status_code == 422
    assert config.get("units.speed") == "mph"


def test_unknown_section_404(tmp_path):
    client, *_ = make_client(tmp_path)
    assert client.post("/api/settings/server", json={"port": 1}).status_code == 404
    assert client.post("/api/settings/providers.vehicle", json={}).status_code == 404


def test_alert_rules_roundtrip(tmp_path):
    client, config, *_ = make_client(tmp_path)
    rules = [
        {"topic": "vehicle.coolant_c", "above": 110, "level": "critical", "message": "HOT"},
        {"topic": "vehicle.speed_kph", "above_topic": "road.speed_limit_kph",
         "tolerance": 8, "level": "warn", "message": "OVERSPEED"},
    ]
    r = client.post("/api/settings/alerts.rules", json=rules)
    assert r.status_code == 200
    assert config.get("alerts.rules")[1]["above_topic"] == "road.speed_limit_kph"

    # a rule with both above and below is rejected
    bad = [{"topic": "vehicle.rpm", "above": 1, "below": 2, "message": "X"}]
    assert client.post("/api/settings/alerts.rules", json=bad).status_code == 422


def test_snapshot_endpoint(tmp_path):
    client, _, bus, _ = make_client(tmp_path)
    bus.publish("gps.position", {"lat": 40.5, "lon": -74.4})
    r = client.get("/api/snapshot", params={"pattern": "gps.*"})
    assert r.json() == {"gps.position": {"lat": 40.5, "lon": -74.4}}


def test_mirror_scalar_section(tmp_path):
    client, config, *_ = make_client(tmp_path)
    assert client.post("/api/settings/mirror", json=False).status_code == 200
    assert config.get("mirror") is False
