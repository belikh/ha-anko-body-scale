---
title: Advert format
summary: The byte layout of the scale's manufacturer data and how the parser reads it.
order: 30
audience: developers
status: draft
---

The scale broadcasts its reading in the manufacturer data of each [[term:Advert]], under the local name `IF_B7`. The layout was reverse engineered from the MovingLife app and confirmed against nRF Connect captures. It belongs to the Senssun protocol family.

`parser.py` reads the payload after the 2-byte company ID, which Bleak and ESPHome move into the dictionary key. A payload shorter than 17 bytes is ignored.

| Bytes | Content | Decoding |
| --- | --- | --- |
| 10 to 11 | Weight | Big-endian, hundredths of a kg. `0x1FB8` is 81.20 kg. |
| 13 | Raw impedance code | 0 means no foot contact. |
| 14 | Status | `0x01` while measuring, `0xA1` once finished. |
| 15 to 16 | Frame counter and checksum | Not read. |

An advert with status `0x01` gives a weight, no impedance and `stable: false`. Any other status gives `stable: true` and the impedance code, or no impedance when the code is 0.

The integration is a passive listener (`iot_class: local_push`). It registers a Bluetooth callback for the scale's address and never connects.

:::see-also
- [[concepts/body-composition]]
- [[concepts/attribution]]
:::
