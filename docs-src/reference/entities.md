---
title: Entities
summary: Every entity of the scale device and the person devices, with its category, default state and unit.
order: 10
audience: users
status: draft
---

Each scale is one device. Each [[term:Person]] is one device that all scales share.

## Scale device

| Platform | Entity | Category | Default | Description |
| --- | --- | --- | --- | --- |
| `sensor` | Weight | none | enabled | Weight of the latest advert, in kg. It changes while the reading settles. |
| `sensor` | Impedance (raw) | diagnostic | disabled | Raw impedance code of the latest advert, with no unit. Empty when a foot missed a pad. |
| `sensor` | Last person | none | enabled | Name of the person who got the last weigh-in on this scale. |
| `sensor` | Pending measurements | diagnostic | enabled | Count of pending measurements. The `pending` attribute lists them. |
| `binary_sensor` | Reading stable | diagnostic | enabled | On when the scale has finished measuring (status byte `0xA1`). |
| `select` | Next person | none | enabled | Sends the next weigh-in on this scale to the chosen person. `Automatic` clears it. |

The `pending` attribute of **Pending measurements** is a list. Each item has `pending_id`, `weight_kg`, `timestamp` and `candidates`.

## Person device

Each sensor shows the value of the person's last assigned [[term:Weigh-in]]. Entity IDs follow the person's name, for example `sensor.jupiter_body_fat`.

| Platform | Entity | Unit | Category | Default | Description |
| --- | --- | --- | --- | --- | --- |
| `sensor` | Weight | kg | none | enabled | Weight of the weigh-in. |
| `sensor` | Impedance (raw) | none | diagnostic | disabled | Raw impedance code of the weigh-in. |
| `sensor` | BMI | none | none | enabled | Body mass index. |
| `sensor` | Body fat | % | none | enabled | Fat mass as a share of weight. |
| `sensor` | Fat mass | kg | none | enabled | Weight minus lean mass. |
| `sensor` | Lean mass | kg | none | enabled | Fat-free mass. |
| `sensor` | Muscle mass | kg | none | enabled | Lean mass minus bone mass. |
| `sensor` | Body water | % | none | enabled | 73.2 % of lean mass, as a share of weight. |
| `sensor` | Bone mass | kg | none | enabled | 5.21 % of lean mass for men, 4.90 % for women. |
| `sensor` | Basal metabolic rate | kcal/d | none | enabled | Mifflin-St Jeor equation. |
| `sensor` | Metabolic age | yr | none | enabled | Age shifted by body fat, 15 at least. |
| `sensor` | Visceral fat index | none | none | enabled | 1 to 30, from BMI, age and sex. |
| `sensor` | Ideal weight (min) | kg | diagnostic | enabled | Weight at BMI 18.5 for the person's height. |
| `sensor` | Ideal weight (max) | kg | diagnostic | enabled | Weight at BMI 24.9 for the person's height. |
| `button` | Weighing in | none | none | enabled | Sends the next weigh-in to this person, on every scale that allows them, for 60 seconds. |

## The method attribute

Every person sensor except **Weight** and **Impedance (raw)** has a `method` attribute.

| Value | Meaning |
| --- | --- |
| `bia_assumed` | Lean mass comes from the impedance equation, with the assumed conversion of the raw code to ohms. |
| `bmi` | Body fat comes from BMI, age and sex. |

[[concepts/body-composition]] explains both routes.

## Restored state

Sensors and **Reading stable** restore their last value after a restart. They stay available with that value until the next weigh-in.

:::see-also
- [[reference/actions]]
- [[concepts/body-composition]]
:::
