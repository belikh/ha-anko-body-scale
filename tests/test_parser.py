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


def _mfg(weight_hundredths: int, impedance_hundredths: int) -> dict[int, bytes]:
    data = bytearray(17)
    data[10] = (weight_hundredths >> 8) & 0xFF
    data[11] = weight_hundredths & 0xFF
    data[13] = (impedance_hundredths >> 8) & 0xFF
    data[14] = impedance_hundredths & 0xFF
    return {0xFFFF: bytes(data)}


def test_local_name() -> None:
    assert LOCAL_NAME == "IF_B7"


def test_parse_stable_reading() -> None:
    reading = parse_manufacturer_data(_mfg(7205, 50100))
    assert reading is not None
    assert reading.weight_kg == 72.05
    assert reading.impedance_ohm == 501.0
    assert reading.stable is True


def test_parse_settling_reading() -> None:
    reading = parse_manufacturer_data(_mfg(7205, 0x0001))
    assert reading is not None
    assert reading.weight_kg == 72.05
    assert reading.impedance_ohm is None
    assert reading.stable is False


def test_parse_short_payload_returns_none() -> None:
    assert parse_manufacturer_data({0xFFFF: b"\x00" * 5}) is None
    assert parse_manufacturer_data({}) is None
