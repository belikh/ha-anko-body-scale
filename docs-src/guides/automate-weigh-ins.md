---
title: Automate weigh-ins
summary: Trigger an automation on a weigh-in, show the sensors on a dashboard and use the example files.
order: 40
audience: users
status: draft
---

The `anko_scale_weigh_in` event fires once for each assigned [[term:Weigh-in]]. Use it as an automation trigger.

## Notify on a weigh-in

```yaml title="Automation"
triggers:
  - trigger: event
    event_type: anko_scale_weigh_in
    event_data:
      person_id: jupiter
actions:
  - action: notify.mobile_app_phone
    data:
      message: "{{ trigger.event.data.person_name }}: {{ trigger.event.data.weight_kg }} kg"
```

Replace `jupiter` with the person's [[term:Profile ID]] and `notify.mobile_app_phone` with your notify action.

## Show the sensors on a dashboard

```yaml title="Entities card"
type: entities
title: Weigh-ins
entities:
  - sensor.jupiter_weight
  - sensor.jupiter_body_fat
  - sensor.sarah_weight
  - sensor.sarah_body_fat
  - sensor.anko_body_scale_pending_measurements
  - select.anko_body_scale_next_person
```

Entity IDs follow the names you chose for the people and the scale.

## Weigh something without a person

`anko_scale.capture_measurement` waits for the next weigh-in and returns it. The weigh-in is assigned to nobody and joins no history.

```yaml title="Script step"
- action: anko_scale.capture_measurement
  data:
    timeout: 60
  response_variable: reading
- action: notify.mobile_app_phone
  data:
    message: "{{ reading.weight_kg }} kg"
```

The action fails with `No settled weigh-in arrived before the timeout.` when nobody steps on the scale in time.

## Example files

The [`examples`](https://github.com/belikh/ha-anko-body-scale/tree/main/examples) folder of the repository holds three files to copy and edit. They use people named Jupiter and Sarah.

| File | Content |
| --- | --- |
| `dashboard.yaml` | A dashboard with one view per person and a scale view. Paste it into the raw configuration editor of a new dashboard. |
| `weight_loss_leaderboard.yaml` | Statistics sensors for the 30-day weight change and a template sensor that ranks people by kilograms lost and by share of their goal. |
| `pet_weighing.yaml` | A script that weighs you with the pet, then alone, and stores the difference in a helper. It uses `capture_measurement`. |

:::see-also
- [[reference/events]]
- [[reference/actions]]
:::
