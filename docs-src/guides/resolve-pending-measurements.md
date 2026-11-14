---
title: Resolve pending measurements
summary: Assign or discard a weigh-in that the integration could not match to one person.
order: 30
audience: users
status: draft
---

A [[term:Pending measurement]] is a [[term:Weigh-in]] that fits two people, fits nobody, or arrived when nobody was eligible. The integration publishes no per-person values for it. Each one creates a persistent notification titled `ANKO scale: who was that?` that contains its `pending_id`.

A scale keeps 10 pending measurements at most and drops the oldest first. Each one expires after the pending timeout, 60 minutes by default. The integration checks for expired ones every 5 minutes and at each weigh-in.

## Find the pending ID

Open **Pending measurements** on the scale device. The `pending` attribute lists each one:

```yaml title="Attributes of sensor.anko_body_scale_pending_measurements"
pending:
  - pending_id: 3fa91c0b
    weight_kg: 74.3
    timestamp: "2026-11-07T02:40:11+00:00"
    candidates:
      - person_id: jupiter
        distance_kg: 1.2
      - person_id: sarah
        distance_kg: 2.1
```

The `anko_scale_pending_measurement` event carries the same ID.

## Assign it to a person

Run the action from **Developer tools > Actions**:

```yaml title="Assign a pending measurement"
action: anko_scale.assign_measurement
data:
  pending_id: 3fa91c0b
  person_id: jupiter
```

The person's sensors update and the weight joins their history. The notification closes.

## Discard a guest's weigh-in

```yaml title="Discard a pending measurement"
action: anko_scale.discard_measurement
data:
  pending_id: 3fa91c0b
```

Only an administrator can run `discard_measurement`. A discarded weigh-in creates no person.

## Answer from your phone

1. Select **Configure** on **ANKO Body Scale people**, then **Attribution settings**.
2. Type the notify action of your phone in **Notify action**, for example `notify.mobile_app_phone`, and select **Submit**.

Each pending measurement then sends a notification with up to three buttons. `I'm <name>` appears for the two closest people and assigns the weigh-in. `Not me` discards it.

## Add a person from an unknown weight

When two or more people exist and a weigh-in is outside everyone's tolerance, Home Assistant shows the repair **A weigh-in matched nobody**.

1. Open **Settings > System > Repairs** and select the repair.
2. Fill in the person form. **Starting weight** holds the observed weight.
3. Select **Submit**. The integration adds the person and drops the pending weigh-in.

The next weigh-in is the first one published for the new person. A weight that is close to two people creates a pending measurement and no repair.

## Move the last weigh-in to another person

```yaml title="Reassign the last weigh-in"
action: anko_scale.reassign_measurement
data:
  person_id: sarah
```

The previous owner's sensors and history return to their earlier values. The action works on the most recent assigned weigh-in since the last restart.

## Errors

| Message | Cause | Fix |
| --- | --- | --- |
| `No pending measurement with ID {pending_id}. It may have expired.` | The ID is wrong, or the pending timeout passed. | Read the ID from the sensor again. Raise the pending timeout in [[reference/settings]]. |
| `No person with ID {person}.` | `person_id` is not a [[term:Profile ID]]. | Use the slug of the person's name, for example `jupiter`. |
| `There is no recent measurement to reassign.` | No weigh-in has been assigned since the restart. | Weigh in again. |

:::see-also
- [[concepts/attribution]]
- [[reference/actions]]
- [[reference/events]]
:::
