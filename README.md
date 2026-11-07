# ANKO Body Scale for Home Assistant

[![Add to Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=belikh&repository=ha-anko-body-scale&category=integration)

A custom integration for the **ANKO iF1012D Bluetooth body scale** (advertised
as `IF_B7`) in Home Assistant. It listens passively to the scale's BLE
advertisements — no connection, no polling, no cloud account — decodes weight,
bioelectrical impedance and reading stability directly from the manufacturer
data, and computes the full body-composition suite (body fat, muscle mass,
bone mass, body water, basal metabolic rate, metabolic age, visceral fat index
and ideal weight range) from the height / age / sex profile you enter at setup.

The advertisement layout was reverse engineered from the MovingLife app and
confirmed against nRF Connect captures (Senssun protocol family).

## Features

- **Setup via UI** with Bluetooth auto-discovery (no addresses to type).
- **Local push, passive BLE**: the scale broadcasts, Home Assistant listens —
  nothing is sent to the internet and no app or account is required.
- **Full body composition**: 14 sensors computed from each stable reading
  (see the table below), using the standard published BIA regression
  equations documented in `body_metrics.py`.
- **Options flow** to update height / age / sex without removing the entry.
- **Restored state** across restarts — the last reading survives a HA restart
  while the scale is out of range.
- **Bluetooth discovery** via the `bluetooth` matcher (`local_name: IF_B7`).

## Installation

1. Click the **Add to Home Assistant** button above and choose **Download**,
   or search for **ANKO Body Scale** in the Marketplace or HACS.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services**, add **ANKO Body Scale** and pick
   the scale from the list.

### Manual

1. Download the `custom_components/anko_scale` folder from this repository.
2. Copy it into the `custom_components` directory of your Home Assistant
   configuration.
3. Restart Home Assistant.

### Custom repository (fallback)

If the search returns nothing, open the Marketplace or HACS, use the three dots
(top right) → **Custom repositories**, add
`https://github.com/belikh/ha-anko-body-scale` with category **Integration**, then
install **ANKO Body Scale** and restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **ANKO Body Scale**.
   - If the scale is powered and in range, Home Assistant usually discovers it
     automatically via Bluetooth and you can start from the discovery card.
3. If you set it up manually, pick your scale (advertised as `IF_B7`) from the
   list of previously seen devices.
4. Enter the body profile of the person using the scale: **height (cm)**,
   **age (years)** and **sex**. These drive the body-composition maths and can
   be changed later via **Configure** on the config entry.
5. The scale appears as a device with all entities attached.

Step on the scale and wait for the stable reading — the sensors fill in from
the advertisement broadcast.

### Options

The integration's **Configure** flow lets you update the **height**, **age**
and **sex** used for the body-composition calculations. Changes reload the
entry automatically.

## Entities

| Platform | Entity | Category | Default | Description |
|---|---|---|---|---|
| `sensor` | Weight | — | enabled | Scale weight in kg |
| `sensor` | Impedance | Diagnostic | **disabled** | Bioelectrical impedance in Ω ( raw BIA input ) |
| `sensor` | BMI | — | enabled | Body mass index |
| `sensor` | Body fat | — | enabled | Body fat percentage |
| `sensor` | Fat mass | — | enabled | Fat mass in kg |
| `sensor` | Lean mass | — | enabled | Fat-free (lean) mass in kg |
| `sensor` | Muscle mass | — | enabled | Muscle mass in kg |
| `sensor` | Body water | — | enabled | Total body water percentage |
| `sensor` | Bone mass | — | enabled | Bone mineral mass in kg |
| `sensor` | Basal metabolic rate | — | enabled | BMR in kcal/day (Mifflin-St Jeor) |
| `sensor` | Metabolic age | — | enabled | Metabolic age in years |
| `sensor` | Visceral fat index | — | enabled | Visceral fat index (1–30 heuristic) |
| `sensor` | Ideal weight (min) | Diagnostic | enabled | Healthy minimum weight for your height (BMI 18.5) |
| `sensor` | Ideal weight (max) | Diagnostic | enabled | Healthy maximum weight for your height (BMI 24.9) |
| `binary_sensor` | Reading stable | Diagnostic | enabled | `on` when the most recent reading has settled |

> **Accuracy:** body-composition values from any single-frequency, foot-to-foot
> BIA device are estimates (typically within ±3–8 % of a DEXA scan) — the same
> caveat applies to premium smart scales using the same equations. Weight,
> impedance and reading stability are direct from the scale; everything else is
> computed.

## Troubleshooting

- **No ANKO scales found during setup** — the scale must be powered, out of
  its sleep state and in Bluetooth range during setup. Step on it briefly to
  wake it, or check it appears under **Settings → Devices & Services →
  Bluetooth**. A Bluetooth proxy (e.g. ESPHome) also works if the adapter is
  far away.
- **Sensors stay `unknown` / `unavailable`** — no stable reading has been
  received yet. The body-composition sensors only fill in when the reading is
  stable and carries a valid impedance. Step on the scale barefoot, stand
  still, and wait for the stable reading; the `reading_stable` binary sensor
  shows whether the last advertisement was settled.
- **Weight shows but body fat does not** — weight comes from every
  advertisement, body composition needs a settled impedance (`0x0001` is the
  settling sentinel). This is normal while the reading is still settling.
- **Body composition looks off** — check the profile under **Configure**
  (height / age / sex). BIA maths depends heavily on height and age; bare feet
  and dry skin also matter.
- **Readings stop after Home Assistant restarts** — the passive listener
  restarts with the entry. If the scale is out of range the last values are
  restored and marked available until a fresh reading arrives; step on the
  scale to refresh them.

## Reporting a problem

[Open an issue](https://github.com/belikh/ha-anko-body-scale/issues/new/choose) and
fill in the bug report form. It asks for the scale model and the debug log:

1. **Debug log.** Open **Settings > Devices & services > ANKO Body Scale**,
   choose **Enable debug logging** from the three-dot menu, repeat the problem,
   then choose **Disable debug logging**. The browser downloads
   `home-assistant_anko_scale_<date>.log`. The log holds only the period
   between the two clicks, but it can include your Bluetooth address, so read
   the file before posting.

To keep debug logging on across restarts, add this to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.anko_scale: debug
```

## Known limitations

- **One person per scale.** The profile is a single height / age / sex, so
  weigh-ins from other people compute against the wrong profile.
- **Single-frequency BIA only.** The scale reports one impedance value; the
  integration cannot segment limbs or use multi-frequency analysis.
- **Passive listening only.** The scale is never connected to — Home Assistant
  cannot trigger a weigh-in or read history; it only sees advertisements
  broadcast while you step on the scale.

## Removing the integration

Open **Settings → Devices & Services**, open the **ANKO Body Scale**
entry, click the three dots → **Delete**. This removes the config entry, its
device and entities. Optionally also remove the integration files (Marketplace/HACS or
`custom_components/anko_scale`) and restart Home Assistant.

## Development

Tests run against a pinned Home Assistant version with
[uv](https://docs.astral.sh/uv/):

```bash
uv sync          # create .venv from uv.lock
uv run pytest
uv run ruff check custom_components tests
uv run mypy
```

`pyproject.toml` carries the dev dependency group (pytest-homeassistant-custom-component,
ruff, mypy) and `uv.lock` pins the full tree, so the suite is reproducible.

## Credits

- **Jupiter Belic** — integration author. The advertisement layout was reverse
  engineered from the MovingLife app and confirmed against nRF Connect captures.
- Body-composition equations (see `body_metrics.py`):
  - **Mifflin et al.**, *A new predictive equation for resting energy
    expenditure*, Am J Clin Nutr 1990 (BMR).
  - **Kyle et al.**, *Bioelectrical impedance analysis*, Clin Nutr 2001
    (fat-free mass from the resistance index).
  - **Pace & Rathbun**, J Biol Chem 1945 (total body water ≈ 73 % of fat-free
    mass).
  - **American Council on Exercise** reference ranges for body fat percentage.
