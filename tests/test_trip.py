import pytest

from hud.core.bus import Bus
from hud.core.config import Config
from hud.providers.trip import SIXTY_MPH_KPH, TripProvider, TripState, ZeroSixty

# ---- integration math -----------------------------------------------------


def test_distance_integration_constant_speed():
    s = TripState()
    for i in range(61):  # 60 s at 120 km/h → exactly 2 km
        s.on_speed(float(i), 120.0)
    assert s.distance_km == pytest.approx(2.0, rel=1e-6)
    assert s.moving_s == pytest.approx(60.0)


def test_fuel_integration_constant_maf():
    s = TripState()
    # 14.7 g/s MAF → 1 g/s fuel → 3600/737 L/h; over 3600 s → 4.884 L
    for i in range(3601):
        s.on_maf(float(i), 14.7)
    assert s.fuel_l == pytest.approx(3600 / 737, rel=1e-3)


def test_avg_economy():
    s = TripState()
    s.distance_km = 10.0
    s.fuel_l = 0.8
    assert s.avg_lp100k == pytest.approx(8.0)


def test_avg_economy_none_when_no_distance():
    assert TripState().avg_lp100k is None


def test_gap_does_not_integrate():
    s = TripState()
    s.on_speed(0.0, 100.0)
    s.on_speed(100.0, 100.0)  # 100 s gap > MAX_GAP_S — ignored
    assert s.distance_km == 0.0


# ---- 0-60 state machine ---------------------------------------------------


def run_profile(zs: ZeroSixty, profile: list[tuple[float, float]]) -> list[float]:
    recorded = []
    for ts, kph in profile:
        if zs.update(ts, kph):
            recorded.append(zs.last_s)
    return recorded


def test_clean_run_records():
    zs = ZeroSixty()
    profile = [(0.0, 0.0), (1.5, 0.0)]  # standstill 1.5 s → armed
    profile += [(2.0 + i * 0.5, 15.0 * (i + 1)) for i in range(7)]  # 15..105 kph
    runs = run_profile(zs, profile)
    assert len(runs) == 1
    # launch at t=2.0, crossed 96.56 at the 105 kph sample (t=5.0)
    assert runs[0] == pytest.approx(3.0, abs=0.01)
    assert zs.best_s == runs[0]


def test_rolling_start_not_recorded():
    zs = ZeroSixty()
    profile = [(float(i), 30.0 + i * 10) for i in range(10)]  # never at standstill
    assert run_profile(zs, profile) == []


def test_aborted_run_then_clean_run():
    zs = ZeroSixty()
    profile = [(0.0, 0.0), (1.5, 0.0), (2.0, 20.0), (3.0, 40.0), (4.0, 0.0), (5.5, 0.0)]
    assert run_profile(zs, profile) == []  # aborted — back to standstill
    profile2 = [(6.0, 50.0), (7.0, 100.0)]  # re-armed during 4.0-5.5 standstill
    runs = run_profile(zs, profile2)
    assert len(runs) == 1


def test_best_keeps_minimum():
    zs = ZeroSixty()
    run_profile(zs, [(0, 0), (1.5, 0), (2.0, 50), (6.0, 100)])   # 4.0 s
    run_profile(zs, [(10, 0), (11.5, 0), (12.0, 50), (15.0, 100)])  # 3.0 s
    assert zs.best_s == pytest.approx(3.0)
    assert zs.last_s == pytest.approx(3.0)


# ---- persistence ----------------------------------------------------------


def test_cache_roundtrip(tmp_path):
    config = Config(data={"cache_dir": str(tmp_path)})
    provider = TripProvider(Bus(), config)
    state = TripState(distance_km=12.3, fuel_l=1.1, moving_s=900, last_ts=1000.0)
    zs = ZeroSixty(best_s=7.42)
    provider._save(state, zs)

    state2, zs2 = provider._load()
    assert state2.distance_km == 12.3
    assert state2.fuel_l == 1.1
    assert zs2.best_s == 7.42


def test_load_missing_cache(tmp_path):
    provider = TripProvider(Bus(), Config(data={"cache_dir": str(tmp_path)}))
    state, zs = provider._load()
    assert state.distance_km == 0.0
    assert zs.best_s is None


def test_sixty_constant():
    assert SIXTY_MPH_KPH == pytest.approx(60 * 1.609344, abs=0.01)


def test_ecu_fuel_rate_overrides_maf():
    from hud.providers.trip import TripState

    s = TripState()
    for t in range(0, 11):
        s.on_speed(float(t), 72.0)
        s.on_fuel_rate(float(t), 3.6)      # 3.6 L/h → 1 mL/s
        s.on_maf(float(t), 50.0)           # would be ~16 L/h — must be ignored
    assert s.fuel_l == pytest.approx(0.01, rel=1e-6)
    assert s.instant_lp100k == pytest.approx(5.0, rel=0.01)  # 3.6 L/h at 72 km/h
