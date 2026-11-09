import asyncio
import time

import pytest

from hud.core.bus import Bus
from hud.core.config import Config
from hud.providers.vehicle.base import CHANNELS, VehicleSource
from hud.providers.vehicle.canbus import CanVehicleSource
from hud.providers.vehicle.canobd import OBD_CHANNELS
from hud.providers.vehicle.manager import ELM_COMPLEMENT, OBD_COMPLEMENT, AutoVehicleManager

CAN_CONFIG = Config(
    data={
        "providers": {
            "vehicle": {
                "can": {
                    "dbc": "dbc/toyota_2017_ref_pt.dbc",
                    "signals": {
                        "speed_kph": {"message": "VSC1S03", "signal": "SP1"},
                        "rpm": {"message": "ENG1F07", "signal": "NE1"},
                        "lane_left": {"message": "DS12F03", "signal": "LKAWLSL"},
                        "lane_right": {"message": "DS12F03", "signal": "LKAWLSR"},
                        "lda_buzzer": {"message": "DS12F03", "signal": "LDWBZ"},
                        "bsm_status": {"message": "BSR1S01", "signal": "BSD_STAT"},
                        "pcs_warn": {"message": "ACC1F01", "signal": "PCSWAR"},
                        "brake_hold": {"message": "ACC1F01", "signal": "BRKHLD"},
                        "trans_temp_c": {"message": "ECT1S92", "signal": "BV_THOCL"},
                        "odometer_km": {"message": "MET1S02_21", "signal": "ODO"},
                    },
                    "gear": {
                        "message": "ECT1S92",
                        "bits": {"P": "B_P", "R": "B_R", "N": "B_N", "D": "B_D"},
                    },
                }
            }
        }
    }
)


# ---- CAN decode against the real vendored DBC ----------------------------


@pytest.fixture
def can_source():
    src = CanVehicleSource(Bus(), CAN_CONFIG)
    src.load_dbc()
    return src


def encode(src: CanVehicleSource, name: str, data: dict) -> tuple[int, bytes]:
    msg = src._db.get_message_by_name(name)
    # fill unset signals with 0
    full = {s.name: 0 for s in msg.signals} | data
    return msg.frame_id, msg.encode(full, strict=False)


def test_can_decodes_speed(can_source: CanVehicleSource):
    frame_id, data = encode(can_source, "VSC1S03", {"SP1": 88.5})
    out = dict(can_source.handle_frame(frame_id, data))
    assert out["speed_kph"] == pytest.approx(88.5, abs=0.01)


def test_can_decodes_rpm(can_source: CanVehicleSource):
    frame_id, data = encode(can_source, "ENG1F07", {"NE1": 3000})
    out = dict(can_source.handle_frame(frame_id, data))
    assert out["rpm"] == pytest.approx(3000, abs=1)


def test_can_decodes_gear_bits(can_source: CanVehicleSource):
    frame_id, data = encode(can_source, "ECT1S92", {"B_D": 1})
    assert dict(can_source.handle_frame(frame_id, data))["gear"] == "D"
    frame_id, data = encode(can_source, "ECT1S92", {"B_P": 1})
    assert dict(can_source.handle_frame(frame_id, data))["gear"] == "P"


def test_can_ignores_unmapped_frames(can_source: CanVehicleSource):
    assert can_source.handle_frame(0x7FF, b"\x00" * 8) == []


def test_can_ignores_garbled_frames(can_source: CanVehicleSource):
    frame_id, _ = encode(can_source, "VSC1S03", {"SP1": 10})
    assert can_source.handle_frame(frame_id, b"\x00") == []  # truncated


def test_can_decodes_lane_status(can_source: CanVehicleSource):
    frame_id, data = encode(
        can_source, "DS12F03", {"LKAWLSL": 3, "LKAWLSR": 1, "LDWBZ": 1}
    )
    out = dict(can_source.handle_frame(frame_id, data))
    assert out["lane_left"] == 3
    assert out["lane_right"] == 1
    assert out["lda_buzzer"] == 1


def test_can_decodes_bsm_and_acc(can_source: CanVehicleSource):
    frame_id, data = encode(can_source, "BSR1S01", {"BSD_STAT": 2})
    assert dict(can_source.handle_frame(frame_id, data))["bsm_status"] == 2

    frame_id, data = encode(can_source, "ACC1F01", {"PCSWAR": 1, "BRKHLD": 1})
    out = dict(can_source.handle_frame(frame_id, data))
    assert out["pcs_warn"] == 1
    assert out["brake_hold"] == 1


def test_can_decodes_trans_temp_scaling(can_source: CanVehicleSource):
    # BV_THOCL: (0.625, -50) — encode 85 °C and expect it back
    frame_id, data = encode(can_source, "ECT1S92", {"BV_THOCL": 85.0})
    assert dict(can_source.handle_frame(frame_id, data))["trans_temp_c"] == pytest.approx(85.0, abs=0.7)


def test_can_decodes_29bit_meter_frame(can_source: CanVehicleSource):
    # MET1S02_21 had a malformed extended ID — the sanitizer must keep it
    frame_id, data = encode(can_source, "MET1S02_21", {"ODO": 48213})
    assert frame_id > 0x800  # really is an extended ID
    assert dict(can_source.handle_frame(frame_id, data))["odometer_km"] == 48213


def test_sanitizer_rewrites_extended_ids():
    dbc = (
        'BO_ 1075906065 FAKE_MSG: 8 XXX\n'
        ' SG_ VAL : 7|8@0+ (1,0) [0|0] "" XXX\n'
    )
    out = CanVehicleSource._sanitize_dbc(dbc)
    assert "FAKE_MSG" in out  # kept, not dropped
    rewritten_id = int(out.split()[1])
    assert rewritten_id & 0x80000000  # flagged extended
    assert rewritten_id & 0x1FFFFFFF == 1075906065 & 0x1FFFFFFF  # 29-bit id preserved


# ---- ELM327 value conversion ---------------------------------------------


def test_elm_convert_units():
    from pint import UnitRegistry

    from hud.providers.vehicle.elm327 import convert

    ureg = UnitRegistry()
    assert convert("speed_kph", 55 * ureg.mph) == pytest.approx(88.51, abs=0.01)
    assert convert("coolant_c", ureg.Quantity(90, ureg.degC)) == 90.0
    assert convert("rpm", 3000.0) == 3000.0  # plain magnitude passthrough


# ---- failover manager ----------------------------------------------------


class FakeSource(VehicleSource):
    """Controllable source: emits nothing, freshness set by tests."""

    def __init__(self, bus, config, name):
        super().__init__(bus, config)
        self.name = name
        self.channels: set = set()

    async def run(self):
        await asyncio.Event().wait()


async def test_manager_prefers_can_and_fails_over():
    bus = Bus()
    config = Config()
    can = FakeSource(bus, config, "vehicle-can")
    elm = FakeSource(bus, config, "vehicle-elm327")
    obd = FakeSource(bus, config, "vehicle-canobd")
    mgr = AutoVehicleManager(bus, config, can=can, elm=elm, obd=obd)

    sub = bus.subscribe("vehicle.source")
    mgr.start()
    try:
        # neither fresh → none
        msg = await asyncio.wait_for(sub.__anext__(), timeout=2)
        assert msg.value == "none"

        # CAN emitting → source=can, ELM restricted to the complement set
        can.last_emit_ts = time.time()
        msg = await asyncio.wait_for(sub.__anext__(), timeout=3)
        assert msg.value == "can"
        assert elm.channels == ELM_COMPLEMENT

        # CAN goes stale but ELM alive → source=elm327, ELM widens to all
        can.last_emit_ts = 0
        elm.last_emit_ts = time.time() + 100  # stays fresh through the check
        msg = await asyncio.wait_for(sub.__anext__(), timeout=6)
        assert msg.value == "elm327"
        assert elm.channels == set(CHANNELS)
    finally:
        await mgr.stop()


async def test_manager_uses_obd_over_can_when_broadcast_is_gated():
    """2025 Camry: no broadcast frames reach the OBD port, but OBD replies do."""
    bus = Bus()
    config = Config()
    can = FakeSource(bus, config, "vehicle-can")
    elm = FakeSource(bus, config, "vehicle-elm327")
    obd = FakeSource(bus, config, "vehicle-canobd")
    mgr = AutoVehicleManager(bus, config, can=can, elm=elm, obd=obd)

    sub = bus.subscribe("vehicle.source")
    mgr.start()
    try:
        msg = await asyncio.wait_for(sub.__anext__(), timeout=2)
        assert msg.value == "none"

        obd.last_emit_ts = time.time() + 100
        msg = await asyncio.wait_for(sub.__anext__(), timeout=3)
        assert msg.value == "can-obd"
        assert obd.channels == set(OBD_CHANNELS)
        assert elm.channels == {"dtc_codes"}  # ELM only adds what OBD-over-CAN can't

        # broadcast appears → it wins; OBD shrinks to what broadcast lacks
        can.last_emit_ts = time.time() + 100
        msg = await asyncio.wait_for(sub.__anext__(), timeout=3)
        assert msg.value == "can"
        assert obd.channels == OBD_COMPLEMENT
        assert "speed_kph" not in obd.channels
    finally:
        await mgr.stop()
