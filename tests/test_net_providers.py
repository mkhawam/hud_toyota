import json

import pytest

from hud.core.bus import Bus
from hud.core.config import Config
from hud.providers.gps import parse_tpv
from hud.providers.traffic import parse_flow
from hud.providers.weather import WeatherProvider, parse_current

# ---- weather --------------------------------------------------------------

OPEN_METEO_PAYLOAD = {
    "current": {
        "temperature_2m": 24.3,
        "apparent_temperature": 26.1,
        "weather_code": 61,
        "wind_speed_10m": 14.2,
        "is_day": 1,
    }
}


def test_parse_current():
    out = parse_current(OPEN_METEO_PAYLOAD)
    assert out == {
        "temp_c": 24.3,
        "feels_c": 26.1,
        "code": 61,
        "wind_kph": 14.2,
        "is_day": True,
    }


def test_weather_cache_roundtrip(tmp_path):
    config = Config(data={"cache_dir": str(tmp_path)})
    provider = WeatherProvider(Bus(), config)
    data = {"temp_c": 20.0, "code": 0, "fetched_at": 123.0}
    provider._save_cache(data)
    assert provider._load_cache() == data


def test_weather_cache_missing_or_corrupt(tmp_path):
    config = Config(data={"cache_dir": str(tmp_path)})
    provider = WeatherProvider(Bus(), config)
    assert provider._load_cache() is None
    provider.cache_file.write_text("{not json")
    assert provider._load_cache() is None


def test_weather_location_prefers_gps_fix():
    bus = Bus()
    provider = WeatherProvider(bus, Config(data={"location": {"lat": 1.0, "lon": 2.0}}))
    assert provider._location() == (1.0, 2.0)
    bus.publish("gps.position", {"lat": 40.74, "lon": -74.17})
    assert provider._location() == (40.74, -74.17)


# ---- gpsd TPV parsing -----------------------------------------------------


def test_parse_tpv_full_fix():
    line = json.dumps(
        {"class": "TPV", "mode": 3, "lat": 40.5, "lon": -74.45, "speed": 27.0, "track": 92.3}
    )
    assert parse_tpv(line) == {
        "lat": 40.5,
        "lon": -74.45,
        "speed_kph": 97.2,
        "heading": 92.3,
    }


@pytest.mark.parametrize(
    "line",
    [
        json.dumps({"class": "SKY", "satellites": []}),      # not TPV
        json.dumps({"class": "TPV", "mode": 1}),              # no fix
        json.dumps({"class": "TPV", "mode": 3}),              # fix but no coords
        "not json at all",
    ],
)
def test_parse_tpv_rejects_unusable(line):
    assert parse_tpv(line) is None


# ---- traffic flow ---------------------------------------------------------


def test_parse_flow():
    payload = {"flowSegmentData": {"currentSpeed": 45, "freeFlowSpeed": 90, "roadClosure": False}}
    out = parse_flow(payload)
    assert out["ratio"] == 0.5
    assert out["road_closed"] is False


def test_parse_flow_zero_freeflow():
    payload = {"flowSegmentData": {"currentSpeed": 0, "freeFlowSpeed": 0}}
    assert parse_flow(payload)["ratio"] == 1.0
