# Changelog

## 1.3.0

### Added

*   **Unknown-weight repair.** A weigh-in that matches nobody (two or more
    people configured) raises a repair whose fix form adds the person with the
    observed weight as their starting weight. Detections are logged and
    counted in diagnostics.
*   **`anko_scale.capture_measurement`.** Returns the next settled weight as
    an action response without assigning it to anyone.
*   **Examples** in `examples/`: dashboard, weight-loss leaderboard and a
    pet-weighing script.

### Removed

*   **Scale-level body-composition sensors.** BMI, body fat, fat mass, lean
    mass, muscle mass, body water, bone mass, basal metabolic rate, metabolic
    age, visceral fat index and the two ideal-weight sensors are gone from the
    scale device. Each person device has them. They are deleted from the entity
    registry on startup, so dashboards and automations that use
    `sensor.<scale name>_body_fat` and the like must switch to the person's
    sensor. The scale keeps weight, impedance (raw), reading stable, last
    person, pending measurements and next person.

### Changed

*   **Impedance decode.** Captured frames show byte 13 is a raw code (0 with
    no foot contact) and byte 14 is a status flag, not an ohm value split
    across two bytes. The impedance sensor is now "Impedance (raw)" with no
    unit, and events and pending measurements carry `impedance_raw` instead
    of `impedance_ohm`. The raw code is still converted to ohms with an
    assumed factor of 2.56 for the body-fat equation; those results carry
    `method: bia_assumed`. A weigh-in with no foot contact is recorded with
    BMI-based body fat.

### Fixed

*   **Diagnostics leaked person names.** `profile_id` (a slug of the display
    name) and `notify_service` are now redacted in the entry options. The
    `persons` list reports an `index` instead of the `profile_id`.

## 1.2.1

### Added

*   Diagnostics list the last 30 distinct raw adverts (hex with the BLE
    address redacted, parsed weight and impedance, stable flag, RSSI) to
    help check how the impedance bytes are decoded.

## 1.2.0

### Changed

*   **Body-fat model.** Fat-free mass now uses the Wu et al. 2015
    foot-to-foot equation instead of a hand-to-foot equation. **Body fat,
    fat mass, lean mass, muscle mass, bone mass and body water will change
    for existing users.**
*   Impedance outside 325 to 735 Ω, an age under 16, or a result outside
    50 to 95 % of body weight no longer gets clamped. Body fat comes from
    BMI (Deurenberg et al. 1991) instead. Affected sensors carry
    `method: bmi`; the impedance route carries `method: bia`.

## 1.1.1

### Changed

*   Birth date is a text field (`YYYY-MM-DD`) instead of a calendar picker
    that moved one month at a time.
*   Age is optional and only needed when no birth date is given.

## 1.1.0

### Added

*   **Multiple people on one scale.** Each settled reading is attributed to
    the person with the closest expected weight (EWMA of recent readings,
    tolerance `max(5 kg, 7 %)`, 2 kg margin). Ambiguous readings become
    pending measurements instead of corrupting a profile.
*   **Per-person devices and sensors**, linked to the scale device with
    `via_device_id`. Unique ID format `<address>_<profile_id>_<key>`.
*   **Settling buffer.** One weigh-in produces one set of values: 3 stable
    adverts within 0.5 kg and 5 s, or the last stable adverts after 5 s of
    silence.
*   **Persistent state.** Expected-weight history and the pending queue are
    stored per entry and survive restarts.
*   **Overrides.** Per-person **Weighing in** button, **Next person** select
    and a `person` entity filter that excludes people who are `not_home`.
*   **Actions** `assign_measurement`, `discard_measurement`,
    `reassign_measurement`, `set_next_person`, `reset_person_history`.
*   **Events** `anko_scale_weigh_in` and `anko_scale_pending_measurement`,
    a persistent notification for pending readings and optional actionable
    mobile notifications.
*   **Options flow** to add, edit and delete people and tune attribution.
*   New scale sensors **Last person** and **Pending measurements**.
*   Diagnostics download with the BLE address, names and birth dates redacted.

### Changed

*   Config entry version 2. A v1 entry upgrades in place: the old profile
    becomes **Person 1** (`legacy`). Entry data, unique IDs and the scale
    device are unchanged, so existing entity IDs and history are kept.
*   Scale-level body-composition sensors now show the metrics of the most
    recently assigned person and update once per weigh-in, not on every
    stable advert.
*   Requires Home Assistant 2026.9.0 or newer.

## 1.0.0

### Added

*   **Initial release.** Passive BLE listener for the ANKO iF1012D (advertised
    as `IF_B7`, Senssun protocol). Decodes weight, bioelectrical impedance
    and reading stability from the scale's manufacturer advertisements and
    computes the full body-composition suite (BMI, body fat, muscle mass,
    bone mass, body water, BMR, metabolic age, visceral fat index and ideal
    weight range) from the configured height / age / sex profile.
*   **Config flow** with Bluetooth discovery and a body-profile step, plus
    an options flow to update the profile without removing the entry.
*   **Entities**: 14 sensors (`weight`, `impedance`, `bmi`, `body_fat_percent`,
    `fat_mass`, `lean_mass`, `muscle_mass`, `body_water`, `bone_mass`, `bmr`,
    `metabolic_age`, `visceral_fat_index`, `ideal_weight_min`,
    `ideal_weight_max`) and a `reading_stable` binary sensor, with restored
    state across restarts.
