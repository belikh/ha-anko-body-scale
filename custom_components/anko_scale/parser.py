"""Parser for ANKO/Senssun-protocol BLE bathroom scale advertisements."""

from __future__ import annotations

from dataclasses import dataclass

# Advertised local name for the ANKO iF1012D (Senssun-protocol) scale.
LOCAL_NAME = "IF_B7"


@dataclass
class ScaleReading:
    """A single decoded advertisement from the scale."""

    weight_kg: float
    impedance_ohm: float | None
    stable: bool


def parse_manufacturer_data(mfg_data: dict[int, bytes]) -> ScaleReading | None:
    """Decode weight/impedance/stability from BLE manufacturer data.

    Byte layout (after the 2-byte company ID, which both Bleak and
    ESPHome strip into the dict key) was reverse engineered from the
    MovingLife app and confirmed against nRF Connect captures:
      - bytes[10:12]: weight, big-endian, hundredths of a kg
      - bytes[13:15]: impedance, big-endian, hundredths of an ohm,
        or the sentinel 0x0001 while the reading is still settling
    """
    for data in mfg_data.values():
        if len(data) < 17:
            continue

        weight_kg = ((data[10] << 8) | data[11]) / 100.0

        raw_impedance = (data[13] << 8) | data[14]
        if raw_impedance == 0x0001:
            return ScaleReading(weight_kg=weight_kg, impedance_ohm=None, stable=False)

        return ScaleReading(
            weight_kg=weight_kg,
            impedance_ohm=raw_impedance / 100.0,
            stable=True,
        )

    return None
