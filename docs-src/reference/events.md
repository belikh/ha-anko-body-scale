---
title: Events
summary: The two events the integration fires, with every field of their data.
order: 30
audience: users
status: draft
---

## anko_scale_weigh_in

Fires once for each [[term:Weigh-in]] that is assigned to a person.

```yaml title="Event data"
entry_id: 01KV25DSCCM1DXPM40CFMM4H0W
person_id: jupiter
person_name: Jupiter
weight_kg: 81.2
impedance_raw: 165
confidence: 1.0
source: weight_match
timestamp: "2026-11-07T02:40:11+00:00"
```

| Field | Value |
| --- | --- |
| `entry_id` | Config entry ID of the scale that measured. |
| `person_id` | The person's [[term:Profile ID]]. |
| `person_name` | The person's name. |
| `weight_kg` | Weight in kg. |
| `impedance_raw` | Raw impedance code, or null when a foot missed a pad. |
| `confidence` | 0 to 1. See below. |
| `source` | How the person was chosen. See below. |
| `timestamp` | Time of the weigh-in, ISO 8601. |

| `source` | Meaning |
| --- | --- |
| `weight_match` | The weight matched the person's [[term:Expected weight]]. |
| `single_person` | The scale has one person. |
| `forced` | **Weighing in**, **Next person** or `set_next_person` chose the person. |
| `assigned` | `assign_measurement` or a phone notification assigned a pending measurement. |
| `reassigned` | `reassign_measurement` moved the weigh-in. |

`confidence` is 1.0 for every source except `weight_match` with two or more candidates. There it is the gap between the two closest people divided by twice the margin, capped at 1.0. With the default margin of 2 kg, a gap of 3 kg gives 0.75.

## anko_scale_pending_measurement

Fires when a weigh-in becomes a [[term:Pending measurement]].

```yaml title="Event data"
entry_id: 01KV25DSCCM1DXPM40CFMM4H0W
pending_id: 3fa91c0b
weight_kg: 74.3
impedance_raw: 150
candidates:
  - person_id: jupiter
    distance_kg: 1.2
  - person_id: sarah
    distance_kg: 2.1
reason: ambiguous
timestamp: "2026-11-07T02:40:11+00:00"
```

| Field | Value |
| --- | --- |
| `entry_id` | Config entry ID of the scale that measured. |
| `pending_id` | Eight hex characters. Pass it to `assign_measurement` or `discard_measurement`. |
| `weight_kg` | Weight in kg. |
| `impedance_raw` | Raw impedance code, or null. |
| `candidates` | People with an expected weight, closest first, each with `person_id` and `distance_kg`. |
| `reason` | Why the weigh-in is pending. See below. |
| `timestamp` | Time of the weigh-in, ISO 8601. |

| `reason` | Meaning |
| --- | --- |
| `ambiguous` | The closest person is within tolerance, and the next person is less than the margin further away. |
| `no_match` | Nobody is within tolerance. With two or more people this also creates a repair. |
| `no_eligible_person` | The scale's people list is empty, or everyone on it is `not_home`. |

:::see-also
- [[guides/automate-weigh-ins]]
- [[concepts/attribution]]
:::
