# Changelog

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
