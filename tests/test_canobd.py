"""OBD-II over SocketCAN — decode/discovery helpers, using frames captured
from a 2025 Camry (engine ECU 0x7E8 plus four other ECUs)."""

import pytest

from hud.providers.vehicle.canobd import (
    PIDS,
    can_interfaces,
    choose_ecus,
    decode,
    parse_reply,
    request,
    supported_from_bitmap,
    parse_uds_reply,
    uds_request,
    uds_value,
)


def test_request_frame():
    assert request(0x0D) == bytes.fromhex("02010D0000000000")


def test_parse_real_camry_replies():
    assert parse_reply(bytes.fromhex("04410C0000000000")) == (0x0C, b"\x00\x00")
    assert parse_reply(bytes.fromhex("03410D0000000000")) == (0x0D, b"\x00")
    assert parse_reply(bytes.fromhex("0341055800000000")) == (0x05, b"\x58")


def test_parse_rejects_negative_and_multiframe():
    assert parse_reply(bytes.fromhex("037F011200000000")) is None  # negative response
    assert parse_reply(bytes.fromhex("1014490201315445")) is None  # ISO-TP first frame
    assert parse_reply(b"\x02") is None


@pytest.mark.parametrize(
    "channel,payload,expected",
    [
        ("coolant_c", b"\x58", 48.0),          # captured on-car
        ("speed_kph", b"\x58", 88.0),
        ("rpm", b"\x0b\xb8", 750.0),
        ("throttle_pct", b"\xff", 100.0),
        ("fuel_pct", b"\x80", 50.2),
        ("battery_v", b"\x36\xb0", 14.0),
        ("maf_gs", b"\x01\x2c", 3.0),
        ("ambient_c", b"\x28", 0.0),
    ],
)
def test_decode(channel, payload, expected):
    assert decode(channel, payload) == pytest.approx(expected, abs=0.01)


def test_decode_short_payload():
    assert decode("rpm", b"\x0b") is None


def test_supported_bitmap_real_engine_ecu():
    # 7E8 answered 01 00 with BE 1F A0 13
    pids = supported_from_bitmap(0x00, bytes.fromhex("BE1FA013"))
    assert {0x05, 0x0C, 0x0D, 0x0F, 0x10, 0x11, 0x20} <= pids
    assert 0x02 not in pids


def test_choose_prefers_engine_ecu():
    plan = choose_ecus({0x7EA: {0x0D, 0x2F}, 0x7E8: {0x0D, 0x0C}})
    assert plan[0x0D] == 0x7E8   # engine wins the shared PID
    assert plan[0x0C] == 0x7E8
    assert plan[0x2F] == 0x7EA   # only the other ECU has fuel level


def test_every_channel_has_a_pid():
    assert all(isinstance(pid, int) for pid, _ in PIDS.values())


def test_can_interfaces_filters_type_and_up(tmp_path):
    for name, typ, flags, rx in [("can0", "280", "0x40c1", "0"), ("can1", "280", "0x80", "9"),
                                 ("can2", "280", "0x40c1", "425"), ("wlan0", "1", "0x1003", "7")]:
        d = tmp_path / name
        (d / "statistics").mkdir(parents=True)
        (d / "type").write_text(typ + "\n")
        (d / "flags").write_text(flags + "\n")
        (d / "statistics" / "rx_packets").write_text(rx + "\n")
    # can1 is down, wlan0 isn't CAN; the busy can2 (wired to the car) goes first
    assert can_interfaces(str(tmp_path)) == ["can2", "can0"]


# ---- UDS DIDs (2025 Camry combination meter, 0x7C0 -> 0x7C8) ---------------

FUEL = {"ecu": 0x7C0, "did": 0x1022, "bytes": 2, "scale": 0.01, "percent_of": 50.0}


def test_uds_request_frame():
    assert uds_request(0x1022) == bytes.fromhex("0322102200000000")


def test_uds_parse_real_meter_reply():
    # captured: 05 62 10 22 0E C4 -> 37.80 L in a 50 L tank
    payload = parse_uds_reply(bytes.fromhex("056210220EC40000"), 0x1022)
    assert payload == bytes.fromhex("0EC4")
    assert uds_value(FUEL, payload) == pytest.approx(75.6)


def test_uds_parse_rejects_other_did_and_negative():
    assert parse_uds_reply(bytes.fromhex("0562102120EC4000"), 0x1022) is None
    assert parse_uds_reply(bytes.fromhex("037F223100000000"), 0x1022) is None


def test_uds_value_scaling_and_clamp():
    assert uds_value({"bytes": 1, "scale": 0.1}, b"\x8d") == pytest.approx(14.1)
    assert uds_value({"bytes": 1, "offset": -40}, b"\x5a") == 50.0
    assert uds_value({"bytes": 2, "scale": 0.01, "percent_of": 50}, b"\x17\x70") == 100.0
    assert uds_value({"bytes": 2}, b"\x01") is None


# ---- hybrid / odometer PIDs (captured on the 2025 Camry) -------------------


def test_decode_hybrid_battery_soc():
    assert decode("hv_battery_pct", b"\x9a") == pytest.approx(60.39)


def test_decode_odometer():
    assert decode("odometer_km", bytes.fromhex("000B66E3")) == pytest.approx(74723.5)


def test_decode_fuel_rate():
    assert decode("fuel_rate_lph", b"\x00\x00") == 0.0
    assert decode("fuel_rate_lph", b"\x00\x64") == 5.0


def test_decode_hybrid_power_from_9a():
    # FF 10 08 41 9A 0E 00 3F 00 + CF 21 00 1D: 252 V, +2.9 A → +0.73 kW
    assert decode("power_kw", bytes.fromhex("0E003F00001D")) == pytest.approx(0.73, abs=0.01)
    # regen: −40.0 A at 252 V → −10.08 kW
    assert decode("power_kw", bytes.fromhex("0E003F00FE70")) == pytest.approx(-10.08, abs=0.01)
    # voltage/current not supported by this ECU
    assert decode("power_kw", bytes.fromhex("01003F00001D")) is None


class FakeMsg:
    def __init__(self, arb, data):
        self.arbitration_id, self.data = arb, bytes.fromhex(data)


class FakeSock:
    def __init__(self, frames):
        self.frames, self.sent = list(frames), []

    def recv(self, timeout=None):
        return self.frames.pop(0) if self.frames else None

    def send(self, msg):
        self.sent.append(msg)


class FakeCan:
    class Message:
        def __init__(self, arbitration_id, data, is_extended_id):
            self.arbitration_id, self.data = arbitration_id, data


def test_two_frame_reply_is_reassembled_with_flow_control():
    from hud.core.bus import Bus
    from hud.core.config import Config
    from hud.providers.vehicle.canobd import CanObdVehicleSource

    src = CanObdVehicleSource(Bus(), Config())
    sock = FakeSock([
        FakeMsg(0x7EB, "1008419A06003F00"),   # other ECU's first frame: ignored
        FakeMsg(0x7EA, "1008419A0E003F00"),
        FakeMsg(0x7EA, "21001D0000000000"),
    ])
    out = src._collect(sock, 0x9A, 1.0, want=0x7EA, can_mod=FakeCan)
    assert out == [(0x7EA, bytes.fromhex("0E003F00001D"))]
    assert sock.sent[0].arbitration_id == 0x7E2
    assert sock.sent[0].data[0] == 0x30
