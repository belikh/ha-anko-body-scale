"""Tests for the Senssun-protocol advertisement parser."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PARSER_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "anko_scale"
    / "parser.py"
)
_spec = importlib.util.spec_from_file_location("anko_parser", _PARSER_PATH)
assert _spec is not None and _spec.loader is not None
_parser = importlib.util.module_from_spec(_spec)
sys.modules["anko_parser"] = _parser
_spec.loader.exec_module(_parser)

LOCAL_NAME = _parser.LOCAL_NAME
parse_manufacturer_data = _parser.parse_manufacturer_data


def _mfg(weight_hundredths: int, raw: int, status: int) -> dict[int, bytes]:
    data = bytearray(17)
    data[10] = (weight_hundredths >> 8) & 0xFF
    data[11] = weight_hundredths & 0xFF
    data[13] = raw
    data[14] = status
    return {0xFFFF: bytes(data)}


def test_local_name() -> None:
    assert LOCAL_NAME == "IF_B7"


def test_parse_stable_reading() -> None:
    reading = parse_manufacturer_data(_mfg(7205, 165, 0xA1))
    assert reading is not None
    assert reading.weight_kg == 72.05
    assert reading.impedance_raw == 165
    assert reading.stable is True


def test_parse_settling_reading() -> None:
    reading = parse_manufacturer_data(_mfg(7205, 0, 0x01))
    assert reading is not None
    assert reading.weight_kg == 72.05
    assert reading.impedance_raw is None
    assert reading.stable is False


def test_parse_no_foot_contact() -> None:
    # Captured: weight settles but the raw code is 0 when the feet miss the pads.
    reading = parse_manufacturer_data(_mfg(6150, 0, 0xA1))
    assert reading is not None
    assert reading.stable is True
    assert reading.impedance_raw is None


def test_parse_captured_frame() -> None:
    payload = bytes.fromhex("020311" + "aabbccddeeff" + "0218060075a1e81e")
    reading = parse_manufacturer_data({0x0100: payload})
    assert reading is not None
    assert reading.weight_kg == 61.5
    assert reading.impedance_raw == 0x75
    assert reading.stable is True


def test_assumed_ohms() -> None:
    assert _parser.assumed_ohms(None) is None
    assert _parser.assumed_ohms(165) == 165 * _parser.ASSUMED_OHM_PER_COUNT


def test_parse_short_payload_returns_none() -> None:
    assert parse_manufacturer_data({0xFFFF: b"\x00" * 5}) is None
    assert parse_manufacturer_data({}) is None
