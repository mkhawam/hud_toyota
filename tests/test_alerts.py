import asyncio

import pytest

from hud.alerts.engine import AlertsEngine
from hud.core.bus import Bus
from hud.core.config import Config

RULES = {
    "alerts": {
        "rules": [
            {"topic": "vehicle.coolant_c", "above": 110, "level": "critical", "message": "COOLANT HOT"},
            {"topic": "vehicle.fuel_pct", "below": 10, "level": "warn", "message": "LOW FUEL"},
        ]
    }
}


@pytest.fixture
async def engine_bus():
    bus = Bus()
    engine = AlertsEngine(bus, Config(data=RULES))
    engine.start()
    await asyncio.sleep(0)  # let the engine subscribe
    yield bus
    await engine.stop()


async def latest_active(sub):
    """Drain to the most recent alerts.active value."""
    msg = await asyncio.wait_for(sub.__anext__(), timeout=1)
    while not sub._queue.empty():
        msg = await sub.__anext__()
    return msg.value


async def test_above_rule_raises_and_clears(engine_bus: Bus):
    bus = engine_bus
    sub = bus.subscribe("alerts.active", replay=True)
    assert await latest_active(sub) == []

    bus.publish("vehicle.coolant_c", 115)
    await asyncio.sleep(0.05)
    active = await latest_active(sub)
    assert [a["message"] for a in active] == ["COOLANT HOT"]
    assert active[0]["level"] == "critical"

    bus.publish("vehicle.coolant_c", 90)
    await asyncio.sleep(0.05)
    assert await latest_active(sub) == []


async def test_hysteresis_prevents_flapping(engine_bus: Bus):
    bus = engine_bus
    sub = bus.subscribe("alerts.active", replay=True)
    await latest_active(sub)

    bus.publish("vehicle.coolant_c", 111)   # raise (>110)
    await asyncio.sleep(0.05)
    assert len(await latest_active(sub)) == 1

    bus.publish("vehicle.coolant_c", 109)   # inside 3% margin — stays active
    await asyncio.sleep(0.05)
    assert sub._queue.empty(), "no re-publish expected inside the hysteresis band"


async def test_below_rule(engine_bus: Bus):
    bus = engine_bus
    sub = bus.subscribe("alerts.active", replay=True)
    await latest_active(sub)

    bus.publish("vehicle.fuel_pct", 8)
    await asyncio.sleep(0.05)
    active = await latest_active(sub)
    assert [a["message"] for a in active] == ["LOW FUEL"]


async def test_two_topic_rule_raises_and_clears():
    bus = Bus()
    config = Config(
        data={"alerts": {"rules": [
            {"topic": "vehicle.speed_kph", "above_topic": "road.speed_limit_kph",
             "tolerance": 8, "level": "warn", "message": "OVERSPEED"},
        ]}}
    )
    engine = AlertsEngine(bus, config)
    engine.start()
    await asyncio.sleep(0)
    sub = bus.subscribe("alerts.active", replay=True)
    assert await latest_active(sub) == []

    bus.publish("road.speed_limit_kph", 72.4)  # 45 mph zone
    bus.publish("vehicle.speed_kph", 78.0)     # under limit+8 → quiet
    await asyncio.sleep(0.05)
    assert sub._queue.empty()

    bus.publish("vehicle.speed_kph", 82.0)     # over 80.4 → raise
    await asyncio.sleep(0.05)
    assert [a["message"] for a in await latest_active(sub)] == ["OVERSPEED"]

    bus.publish("vehicle.speed_kph", 75.0)     # well back under → clear
    await asyncio.sleep(0.05)
    assert await latest_active(sub) == []
    await engine.stop()


async def test_two_topic_reference_update_triggers():
    bus = Bus()
    config = Config(
        data={"alerts": {"rules": [
            {"topic": "vehicle.speed_kph", "above_topic": "road.speed_limit_kph",
             "tolerance": 8, "level": "warn", "message": "OVERSPEED"},
        ]}}
    )
    engine = AlertsEngine(bus, config)
    engine.start()
    await asyncio.sleep(0)
    sub = bus.subscribe("alerts.active", replay=True)
    await latest_active(sub)

    bus.publish("road.speed_limit_kph", 104.6)
    bus.publish("vehicle.speed_kph", 100.0)    # fine on the highway
    await asyncio.sleep(0.05)
    assert sub._queue.empty()

    # exit ramp: limit drops while speed is cached → alert on the ref update
    bus.publish("road.speed_limit_kph", 72.4)
    await asyncio.sleep(0.05)
    assert [a["message"] for a in await latest_active(sub)] == ["OVERSPEED"]

    # drive off the map: reference gone → alert retires
    bus.publish("road.speed_limit_kph", None)
    await asyncio.sleep(0.05)
    assert await latest_active(sub) == []
    await engine.stop()


async def test_rules_hot_reload():
    bus = Bus()
    config = Config(
        data={"alerts": {"rules": [
            {"topic": "vehicle.rpm", "above": 5000, "level": "warn", "message": "OLD"},
        ]}}
    )
    engine = AlertsEngine(bus, config)
    engine.start()
    await asyncio.sleep(0)
    sub = bus.subscribe("alerts.active", replay=True)
    assert await latest_active(sub) == []

    # settings page saves new rules → engine rebuilds without restart
    config.data["alerts"]["rules"] = [
        {"topic": "vehicle.rpm", "above": 3000, "level": "critical", "message": "NEW"},
    ]
    bus.publish("config.updated", {"section": "alerts.rules"})
    await asyncio.sleep(0.05)

    bus.publish("vehicle.rpm", 4000)  # below the old threshold, above the new one
    await asyncio.sleep(0.05)
    active = await latest_active(sub)
    assert [a["message"] for a in active] == ["NEW"]
    await engine.stop()
