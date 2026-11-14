---
title: Add a second scale
summary: Add another scale and choose which people it weighs.
order: 20
audience: users
status: draft
---

Every scale shares the people in the [[term:People entry]]. A person weighed on any scale updates the same sensors and the same weight history.

## Add the scale

1. Wake the new scale and go to **Settings > Devices & Services > Add Integration > ANKO Body Scale**.
2. Choose the scale from the **Device** list.
3. In **Who uses this scale?**, select the people and select **Submit**. With one person configured, this step is skipped.

| Selection | Result |
| --- | --- |
| Everyone (default) | Any person can be weighed on the scale, including people you add later. |
| Some people | The scale matches only those people. People you add later are left out until you select them. |
| One person | Every weigh-in on the scale goes to that person, with no matching. |

## Change who uses a scale

1. Select **Configure** on the scale entry.
2. Change the selection and select **Submit**. `Select at least one person.` appears when the list is empty.

## Actions with several scales

`assign_measurement`, `discard_measurement`, `set_next_person` and `capture_measurement` act on one scale. With more than one scale they need `config_entry_id`, and fail without it:

```text title="Error"
More than one scale is configured. Set config_entry_id.
```

`reassign_measurement` and `reset_person_history` act on a person and take no `config_entry_id`. A [[term:Pending measurement]] stays on the scale that measured it.

:::see-also
- [[reference/actions]]
- [[guides/manage-people]]
:::
