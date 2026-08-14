import yaml

from hud.core.config import Config, deep_merge

HUD_YAML = """\
# hand-written comment that must survive
units:
  speed: mph
  temp: f
layout:
  - { widget: speed, slot: center }
alerts:
  rules:
    - { topic: vehicle.rpm, above: 5800, level: warn, message: "HIGH RPM" }
"""


def write_hud(tmp_path):
    p = tmp_path / "hud.yaml"
    p.write_text(HUD_YAML, encoding="utf-8")
    return p


def test_deep_merge_semantics():
    base = {"units": {"speed": "mph", "temp": "f"}, "layout": [1, 2], "mirror": True}
    overlay = {"units": {"speed": "kph"}, "layout": [3]}
    out = deep_merge(base, overlay)
    assert out["units"] == {"speed": "kph", "temp": "f"}  # dicts merge key-wise
    assert out["layout"] == [3]                            # lists replace wholesale
    assert out["mirror"] is True


def test_save_section_persists_and_applies_live(tmp_path):
    cfg = Config.load(write_hud(tmp_path))
    cfg.save_section("units", {"speed": "kph", "temp": "c"})

    assert cfg.get("units.speed") == "kph"  # live
    saved = yaml.safe_load((tmp_path / "local.yaml").read_text())
    assert saved == {"units": {"speed": "kph", "temp": "c"}}

    reloaded = Config.load(tmp_path / "hud.yaml")
    assert reloaded.get("units.speed") == "kph"
    assert reloaded.get("layout")[0]["widget"] == "speed"  # untouched sections intact


def test_save_dotted_section(tmp_path):
    cfg = Config.load(write_hud(tmp_path))
    rules = [{"topic": "vehicle.coolant_c", "above": 110, "level": "critical", "message": "HOT"}]
    cfg.save_section("alerts.rules", rules)
    assert cfg.get("alerts.rules") == rules
    assert Config.load(tmp_path / "hud.yaml").get("alerts.rules") == rules


def test_hud_yaml_never_rewritten(tmp_path):
    p = write_hud(tmp_path)
    before = p.read_bytes()
    cfg = Config.load(p)
    cfg.save_section("mirror", False)
    cfg.save_section("units", {"speed": "kph"})
    assert p.read_bytes() == before


def test_corrupt_overlay_is_ignored(tmp_path):
    p = write_hud(tmp_path)
    (tmp_path / "local.yaml").write_text("{not: valid: yaml: [", encoding="utf-8")
    cfg = Config.load(p)  # must not raise
    assert cfg.get("units.speed") == "mph"


def test_legacy_display_yaml_still_merges(tmp_path):
    p = write_hud(tmp_path)
    (tmp_path / "display.yaml").write_text("display:\n  scale: 0.8\n", encoding="utf-8")
    assert Config.load(p).get("display.scale") == 0.8
