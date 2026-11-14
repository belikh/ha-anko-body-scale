---
title: Actions
summary: The six actions of the anko_scale domain, with their fields, defaults and errors.
order: 20
audience: users
status: draft
---

| Action | Acts on | Admin only | Effect |
| --- | --- | --- | --- |
| `anko_scale.assign_measurement` | scale | no | Assigns a [[term:Pending measurement]] to a person and fires `anko_scale_weigh_in` with source `assigned`. |
| `anko_scale.discard_measurement` | scale | yes | Drops a pending measurement. |
| `anko_scale.set_next_person` | scale | no | Sends the next weigh-in on the scale to a person, for 60 seconds or one weigh-in. |
| `anko_scale.capture_measurement` | scale | no | Waits for the next weigh-in and returns it without assigning it. |
| `anko_scale.reassign_measurement` | person | no | Moves the last assigned weigh-in to another person. |
| `anko_scale.reset_person_history` | person | yes | Clears a person's stored weights. |

## Fields

| Action | Field | Required | Default | Value |
| --- | --- | --- | --- | --- |
| `assign_measurement` | `pending_id` | yes | none | ID from the **Pending measurements** sensor or the pending event. |
| `assign_measurement` | `person_id` | yes | none | The person's [[term:Profile ID]]. |
| `assign_measurement` | `config_entry_id` | with several scales | the only scale | The scale entry. |
| `discard_measurement` | `pending_id` | yes | none | ID of the pending measurement. |
| `discard_measurement` | `config_entry_id` | with several scales | the only scale | The scale entry. |
| `set_next_person` | `person_id` | no | empty | Profile ID. Empty clears the override. |
| `set_next_person` | `config_entry_id` | with several scales | the only scale | The scale entry. |
| `capture_measurement` | `timeout` | no | 60 | Seconds to wait, 5 to 300. |
| `capture_measurement` | `config_entry_id` | with several scales | the only scale | The scale entry. |
| `reassign_measurement` | `person_id` | yes | none | Profile ID of the new owner. |
| `reset_person_history` | `person_id` | yes | none | Profile ID. |

## Capture response

`capture_measurement` returns a response and must be called with `response_variable`.

```yaml title="Response"
weight_kg: 81.2
timestamp: "2026-11-07T02:40:11+00:00"
```

One capture can wait on a scale at a time.

## Reassign and reset

`reassign_measurement` restores the previous owner's sensor values and history, then publishes the weigh-in for the new person with source `reassigned`. The last weigh-in is held in memory, so the action has nothing to move after a restart.

`reset_person_history` leaves the person's sensors as they are. If the person has a starting weight, it becomes the [[term:Expected weight]] again.

## Errors

| Message | Cause |
| --- | --- |
| `No person with ID {person}.` | `person_id` matches no profile ID. |
| `No pending measurement with ID {pending_id}. It may have expired.` | The ID is unknown on that scale. |
| `There is no recent measurement to reassign.` | No weigh-in has been assigned since the restart. |
| `More than one scale is configured. Set config_entry_id.` | A scale action ran without `config_entry_id`. |
| `No loaded ANKO scale entry with ID {entry_id}.` | `config_entry_id` names an entry that is not a loaded scale. |
| `No settled weigh-in arrived before the timeout.` | `capture_measurement` timed out. |
| `Another capture is already waiting for a weigh-in.` | A second `capture_measurement` started on the same scale. |
| `The ANKO people entry is not loaded.` | The People entry is disabled or failed to load. |
| `No loaded scale allows this person.` | **Weighing in** was pressed for a person who is on no loaded scale. |

:::see-also
- [[reference/events]]
- [[guides/resolve-pending-measurements]]
:::
