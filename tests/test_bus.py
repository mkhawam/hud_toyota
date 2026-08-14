import asyncio

from hud.core.bus import Bus, topic_matches


def test_topic_matching():
    assert topic_matches("*", "vehicle.rpm")
    assert topic_matches("vehicle.rpm", "vehicle.rpm")
    assert topic_matches("vehicle.*", "vehicle.rpm")
    assert not topic_matches("vehicle.*", "alerts.active")
    assert not topic_matches("vehicle.rpm", "vehicle.speed_kph")


async def test_publish_delivers_to_matching_subscribers():
    bus = Bus()
    sub = bus.subscribe("vehicle.*")
    bus.publish("vehicle.rpm", 3000)
    bus.publish("alerts.active", [])  # should not be delivered

    msg = await asyncio.wait_for(sub.__anext__(), timeout=1)
    assert msg.topic == "vehicle.rpm"
    assert msg.value == 3000
    assert sub._queue.empty()


async def test_replay_primes_with_last_values():
    bus = Bus()
    bus.publish("vehicle.rpm", 1000)
    bus.publish("vehicle.rpm", 2000)  # only latest survives

    sub = bus.subscribe("vehicle.*", replay=True)
    msg = await asyncio.wait_for(sub.__anext__(), timeout=1)
    assert msg.value == 2000


def test_snapshot_filters_by_pattern():
    bus = Bus()
    bus.publish("vehicle.rpm", 3000)
    bus.publish("alerts.active", [])
    snap = bus.snapshot("vehicle.*")
    assert set(snap) == {"vehicle.rpm"}


async def test_slow_consumer_drops_oldest():
    bus = Bus()
    sub = bus.subscribe("t", maxsize=2)
    bus.publish("t", 1)
    bus.publish("t", 2)
    bus.publish("t", 3)  # overflows: drops 1

    assert (await sub.__anext__()).value == 2
    assert (await sub.__anext__()).value == 3


async def test_unsubscribe_stops_delivery():
    bus = Bus()
    sub = bus.subscribe("t")
    bus.unsubscribe(sub)
    bus.publish("t", 1)
    assert sub._queue.empty()
