import asyncio

import pytest

from hud.core.bus import Bus
from hud.core.config import Config
from hud.providers.speedlimit import SpeedLimitProvider
from hud.roads.db import RoadDB, pack_coords, split_chunks, unpack_coords
from hud.roads.matcher import RoadMatcher
from hud.roads.maxspeed import MPH_TO_KPH, parse_maxspeed, resolve_limit

# ---- maxspeed parsing ----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("25 mph", pytest.approx(40.2, abs=0.1)),
        ("65 mph", pytest.approx(104.6, abs=0.1)),
        ("50", 50.0),
        ("30 mph;25 mph", pytest.approx(48.3, abs=0.1)),  # first of a list
        ("none", None),
        ("signals", None),
        ("walk", None),
        ("", None),
        (None, None),
        ("garbage", None),
        ("1", None),      # below sanity range
        ("500", None),    # above sanity range
    ],
)
def test_parse_maxspeed(raw, expected):
    assert parse_maxspeed(raw) == expected


def test_resolve_limit_tagged_wins():
    assert resolve_limit(40.2, "residential") == (40.2, False)


def test_resolve_limit_fallback_estimated():
    kph, estimated = resolve_limit(None, "residential")
    assert estimated is True
    assert kph == pytest.approx(25 * MPH_TO_KPH, abs=0.1)


def test_resolve_limit_unknown_class():
    assert resolve_limit(None, "cycleway") == (None, True)


def test_resolve_limit_config_override():
    kph, _ = resolve_limit(None, "residential", {"residential": 30})
    assert kph == pytest.approx(30 * MPH_TO_KPH, abs=0.1)


# ---- coord packing + chunking --------------------------------------------


def test_pack_roundtrip():
    pts = [(40.4862, -74.4518), (40.4870, -74.4500), (-33.1, 151.2)]
    out = unpack_coords(pack_coords(pts))
    for (a1, b1), (a2, b2) in zip(pts, out):
        assert a1 == pytest.approx(a2, abs=1e-7)
        assert b1 == pytest.approx(b2, abs=1e-7)


def test_split_chunks_point_cap():
    pts = [(40.0 + i * 1e-5, -74.0) for i in range(40)]
    chunks = split_chunks(pts, max_pts=16)
    assert all(len(c) <= 16 for c in chunks)
    # consecutive chunks share an endpoint — no segment lost
    for a, b in zip(chunks, chunks[1:]):
        assert a[-1] == b[0]
    total_pts = sum(len(c) for c in chunks) - (len(chunks) - 1)
    assert total_pts == 40


def test_split_chunks_too_short():
    assert split_chunks([(40.0, -74.0)]) == []


# ---- matcher --------------------------------------------------------------

# A tiny synthetic town near New Brunswick:
#  - "Main St" runs east-west along lat 40.5000 (residential, 25 mph tagged)
#  - "Cross Ave" runs north-south along lon -74.4500 (residential, untagged)
#  - "Highway" runs east-west along lat 40.50045 (~50 m north, motorway 65 mph)
#    — close enough that a point between them has both in the 35 m search radius
MAIN_ST = 1
CROSS_AVE = 2
HIGHWAY = 3


@pytest.fixture
def db(tmp_path):
    db = RoadDB(tmp_path / "roads.sqlite")
    lon_span = [-74.4520 + i * 0.0004 for i in range(11)]
    db.insert_way(MAIN_ST, "residential", 40.2, "Main St",
                  [(40.5000, lon) for lon in lon_span])
    lat_span = [40.4990 + i * 0.0002 for i in range(11)]
    db.insert_way(CROSS_AVE, "residential", None, "Cross Ave",
                  [(lat, -74.4500) for lat in lat_span])
    db.insert_way(HIGHWAY, "motorway", 104.6, "Highway",
                  [(40.50045, lon) for lon in lon_span])
    db.commit()
    yield db
    db.close()


def test_matches_nearest_road(db):
    m = RoadMatcher(db)
    match = m.match(40.50002, -74.4510, heading=90.0, speed_kph=40.0)
    assert match is not None and match.way_id == MAIN_ST
    assert match.dist_m < 5
    assert match.maxspeed_kph == 40.2


def test_intersection_does_not_flap(db):
    m = RoadMatcher(db)
    # drive east along Main St through the Cross Ave intersection
    for i, lon in enumerate([-74.4516, -74.4508, -74.4501, -74.4500, -74.4499, -74.4492]):
        match = m.match(40.50001, lon, heading=90.0, speed_kph=40.0)
        assert match is not None and match.way_id == MAIN_ST, f"flapped at fix {i}"


def test_nearest_of_two_parallel_candidates_wins(db):
    # point between Main St (31 m) and Highway (19 m), both in range and both
    # parallel to the heading — plain distance decides
    m = RoadMatcher(db)
    match = m.match(40.50028, -74.4510, heading=90.0, speed_kph=60.0)
    assert match is not None and match.way_id == HIGHWAY


def test_bearing_penalty_beats_close_cross_street(db):
    # on Cross Ave heading north, right at Main St: Main St is as close but
    # perpendicular — bearing keeps us on Cross Ave
    m = RoadMatcher(db)
    match = m.match(40.50003, -74.45001, heading=0.0, speed_kph=30.0)
    assert match is not None and match.way_id == CROSS_AVE


def test_gap_coasts_then_none(db):
    m = RoadMatcher(db)
    first = m.match(40.5000, -74.4510, heading=90.0, speed_kph=40.0)
    assert first is not None
    # drive off the map: coasts HOLD_FIXES times, then honestly None
    off = (41.0, -75.0)
    for _ in range(RoadMatcher.HOLD_FIXES):
        assert m.match(*off, heading=90.0, speed_kph=40.0) is not None
    assert m.match(*off, heading=90.0, speed_kph=40.0) is None


def test_sticky_switch_needs_consecutive_wins(db):
    m = RoadMatcher(db)
    assert m.match(40.5000, -74.4510, 90.0, 40.0).way_id == MAIN_ST
    # drift to where Highway (17 m) clearly beats Main St (33 m, still in
    # range as the incumbent) — must win twice before the switch
    m1 = m.match(40.50030, -74.4510, 90.0, 40.0)
    assert m1.way_id == MAIN_ST  # first better fix: incumbent still holds
    m2 = m.match(40.50030, -74.4510, 90.0, 40.0)
    assert m2.way_id == HIGHWAY  # second consecutive win → switch


# ---- provider end-to-end over the bus -------------------------------------


async def test_speedlimit_provider_publishes(db, tmp_path):
    db.commit()
    bus = Bus()
    config = Config(data={"providers": {"speedlimit": {"db": str(tmp_path / "roads.sqlite")}}})
    provider = SpeedLimitProvider(bus, config)
    sub = bus.subscribe("road.*")
    provider.start()
    try:
        await asyncio.sleep(0.05)
        bus.publish("gps.heading", 90.0)
        bus.publish("gps.speed_kph", 40.0)
        # on Main St (tagged 25 mph)
        bus.publish("gps.position", {"lat": 40.50001, "lon": -74.4510})
        await asyncio.sleep(0.1)
        snap = bus.snapshot("road.*")
        assert snap["road.speed_limit_kph"].value == pytest.approx(40.2, abs=0.1)
        limit = snap["road.limit"].value
        assert limit["limit_mph"] == 25
        assert limit["estimated"] is False
        assert limit["name"] == "Main St"

        # onto untagged Cross Ave → estimated NJ default
        # (matcher needs SWITCH_FIXES consecutive wins plus clearance from Main St)
        for _ in range(3):
            bus.publish("gps.position", {"lat": 40.49920, "lon": -74.45001})
            await asyncio.sleep(0.05)
        limit = bus.snapshot("road.limit")["road.limit"].value
        assert limit["estimated"] is True
        assert limit["limit_mph"] == 25  # residential fallback
        assert limit["name"] == "Cross Ave"
    finally:
        await provider.stop()
