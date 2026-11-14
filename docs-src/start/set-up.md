---
title: Set up a scale
summary: Add the scale to Home Assistant, enter the first person and take the first weigh-in.
order: 20
audience: users
status: draft
---

Add the scale from **Settings > Devices & Services**. The scale must be awake and in Bluetooth range: step on it for a moment before you start.

## Add the scale

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=anko_scale)

1. Select the badge above, or go to **Settings > Devices & Services > Add Integration** and search for **ANKO Body Scale**. If Home Assistant shows a discovery card for the scale, select **Add** on the card and confirm that the scale is yours.
2. Choose the scale, advertised as `IF_B7`, from the **Device** list.
3. Enter the first person and select **Submit**.

| Field | Required | Range | Use |
| --- | --- | --- | --- |
| Name | yes | text | Names the person's device. Its slug is the [[term:Profile ID]]. |
| Height (cm) | yes | 100 to 250, default 170 | Used in every body-composition value. |
| Sex | yes | Male or Female, default Male | Used in every body-composition value. |
| Birth date | one of the two | `YYYY-MM-DD`, in the past | The age follows the calendar. |
| Age in years | one of the two | 5 to 120 | Used only when no birth date is set. |
| Person entity | no | a `person` entity | The person is skipped while the entity is `not_home`. |
| Starting weight in kg | no | 10 to 300 | Seeds the [[term:Expected weight]]. |

Home Assistant creates two entries. The scale entry has the scale device. The [[term:People entry]], named **ANKO Body Scale people**, has one device per person.

When two or more people exist already, the setup of a new scale asks **Who uses this scale?** in place of the person form. See [[guides/add-a-second-scale]].

## Take the first weigh-in

1. Step on the scale with bare feet. Each foot covers both metal pads on its side.
2. Stand still until the display stops changing.
3. Open the person's device. **Weight** and the body-composition sensors show the values of this weigh-in.

## Setup messages

| Message | Cause | Fix |
| --- | --- | --- |
| `No ANKO body scales were found on the network.` | Home Assistant has not seen an `IF_B7` advert. | Step on the scale to wake it, then start the setup again. |
| `This scale is already configured.` | The scale has an entry already. | Open the existing entry. |
| `Enter a name.` | The name is empty. | Type a name. |
| `Another person already has this name.` | The name gives a profile ID that is taken. | Choose another name. |
| `Enter a past date as YYYY-MM-DD, for example 1985-03-27.` | The birth date is malformed or in the future. | Type the date as year, month, day. |
| `Enter a birth date or an age.` | Both fields are empty. | Fill in one of them. |

:::see-also
- [[guides/manage-people]]
- [[guides/resolve-pending-measurements]]
- [[reference/entities]]
:::
