# Changelog

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
