"""Parser for ANKO/Senssun-protocol BLE bathroom scale advertisements."""

from __future__ import annotations

from dataclasses import dataclass

# Advertised local name for the ANKO iF1012D (Senssun-protocol) scale.
LOCAL_NAME = "IF_B7"

# Byte 14 of the manufacturer data is a status flag.
STATUS_SETTLING = 0x01

# The scale reports a raw code in byte 13, not ohms. The code is 0 with no
# foot contact and rose with body size in the frames captured so far
# (117 to 128 for a 61.5 kg man, 165 for a 71.65 kg man). The conversion to
# ohms is unknown. Until it is calibrated, the code is multiplied by this
# factor, which is the scaling the 1.x parser applied (word / 100).
ASSUMED_OHM_PER_COUNT = 2.56


@dataclass
class ScaleReading:
    """A single decoded advertisement from the scale."""

    weight_kg: float
    impedance_raw: int | None
    stable: bool


def assumed_ohms(impedance_raw: float | None) -> float | None:
    """Return the assumed impedance in ohms for a raw code (unverified)."""
    if impedance_raw is None:
        return None
    return impedance_raw * ASSUMED_OHM_PER_COUNT


def parse_manufacturer_data(mfg_data: dict[int, bytes]) -> ScaleReading | None:
    """Decode weight, raw impedance code and settled state from adverts.

    Byte layout (after the 2-byte company ID, which both Bleak and
    ESPHome strip into the dict key), from frames captured on the scale:
      - bytes[10:12]: weight, big-endian, hundredths of a kg
      - byte[13]: raw impedance code. 0 means no foot contact.
      - byte[14]: status. 0x01 while measuring, 0xA1 once finished.
      - bytes[15:17]: frame counter and checksum, not part of the reading
    """
    for data in mfg_data.values():
        if len(data) < 17:
            continue

        weight_kg = ((data[10] << 8) | data[11]) / 100.0

        if data[14] == STATUS_SETTLING:
            return ScaleReading(weight_kg=weight_kg, impedance_raw=None, stable=False)

        raw = data[13]
        return ScaleReading(
            weight_kg=weight_kg,
            impedance_raw=raw if raw else None,
            stable=True,
        )

    return None
