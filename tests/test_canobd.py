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
