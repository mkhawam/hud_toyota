from fastapi.testclient import TestClient

from hud.core.bus import Bus
from hud.core.config import Config
from hud.drivelog.store import DriveStore, SessionTracker
from hud.server import create_app


def make_store(tmp_path) -> DriveStore:
    return DriveStore(tmp_path / "drives.db")


def test_drive_lifecycle_and_stats(tmp_path):
    store = make_store(tmp_path)
    did = store.start_drive(1000.0)
    for i in range(60):
        store.add_sample(did, 1000.0 + i, {"speed_kph": 50.0, "rpm": 2000})
    store.end_drive(did, 1060.0, {"distance_km": 0.83, "fuel_l": 0.05,
                                  "max_speed_kph": 50.0, "avg_moving_kph": 50.0})

    drives = store.list_drives()
    assert len(drives) == 1
    d = drives[0]
    assert d["sample_count"] == 60
    assert d["distance_km"] == 0.83
    assert d["ended_at"] == 1060.0
    store.close()


def test_samples_downsampling(tmp_path):
    store = make_store(tmp_path)
    did = store.start_drive(0.0)
    for i in range(1000):
        store.add_sample(did, float(i), {"speed_kph": float(i % 100)})
    out = store.get_samples(did, max_points=100)
    assert 100 <= len(out) <= 200  # stride-based, approximate
    assert out[0]["ts"] == 0.0
    store.close()


def test_prune_removes_old_drives(tmp_path):
    store = make_store(tmp_path)
    old = store.start_drive(0.0)
    store.add_sample(old, 1.0, {"speed_kph": 10})
    store.end_drive(old, 2.0, {})
    new = store.start_drive(100.0 * 86400)
    removed = store.prune(keep_days=30, now=100.0 * 86400)
    assert removed == 1
    ids = [d["id"] for d in store.list_drives()]
    assert ids == [new]
    assert store.get_samples(old) == []
    store.close()


def test_session_tracker():
    t = SessionTracker(idle_end_s=600)
    assert t.update(0.0, False) is None
    assert t.update(10.0, True) == "start"
    assert t.update(20.0, True) is None
    assert t.update(30.0, False) is None          # brief stop — still driving
    assert t.update(500.0, False) is None
    assert t.update(631.0, False) == "end"        # 600 s past last activity
    assert t.update(700.0, True) == "start"       # next drive


def test_drives_api(tmp_path):
    cfg_path = tmp_path / "hud.yaml"
    cfg_path.write_text(f"drivelog:\n  data_dir: {(tmp_path / 'data').as_posix()}\n")
    config = Config.load(cfg_path)

    store = DriveStore(tmp_path / "data" / "drives.db")
    did = store.start_drive(1000.0)
    store.add_sample(did, 1001.0, {"speed_kph": 42.0, "rpm": 1800})
    store.end_drive(did, 1002.0, {"distance_km": 0.01})
    store.close()

    client = TestClient(create_app(Bus(), config))
    drives = client.get("/api/drives").json()
    assert len(drives) == 1 and drives[0]["id"] == did

    samples = client.get(f"/api/drives/{did}/samples").json()
    assert samples[0]["speed_kph"] == 42.0
