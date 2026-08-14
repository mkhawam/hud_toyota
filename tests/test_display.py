import yaml
from fastapi.testclient import TestClient

from hud.core.bus import Bus
from hud.core.config import Config
from hud.server import create_app


def make_config(tmp_path):
    cfg_path = tmp_path / "hud.yaml"
    cfg_path.write_text("display:\n  aspect: '3:1'\n  scale: 1.0\n")
    return cfg_path, Config.load(cfg_path)


def test_save_display_clamps_filters_and_persists(tmp_path):
    cfg_path, config = make_config(tmp_path)
    client = TestClient(create_app(Bus(), config))

    r = client.post(
        "/api/display",
        json={"scale": 5, "offset_x": 0.25, "offset_y": "bogus", "junk": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scale"] == 1.0        # clamped to max
    assert body["offset_x"] == 0.25
    assert "junk" not in body
    assert "offset_y" not in body      # unparseable → dropped

    saved = yaml.safe_load((tmp_path / "local.yaml").read_text())
    assert saved["display"]["offset_x"] == 0.25


def test_display_overlay_merges_on_reload(tmp_path):
    cfg_path, config = make_config(tmp_path)
    config.save_display({"offset_x": -0.1, "scale": 0.8})

    reloaded = Config.load(cfg_path)
    assert reloaded.get("display.offset_x") == -0.1
    assert reloaded.get("display.scale") == 0.8
    assert reloaded.get("display.aspect") == "3:1"  # hand-edited key survives
