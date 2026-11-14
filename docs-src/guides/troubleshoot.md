---
title: Troubleshoot
summary: Causes and fixes for a scale that is not found, sensors with no value and wrong body-composition values.
order: 60
audience: users
status: draft
---

## The setup finds no scale

The setup stops with `No ANKO body scales were found on the network.`

The scale sends adverts only while it is awake. Step on it for a moment, then start the setup again. Check that `IF_B7` appears under **Settings > Devices & Services > Bluetooth**. If the Bluetooth adapter is far from the bathroom, put an ESPHome Bluetooth proxy near the scale.

## Person sensors show unknown

No [[term:Weigh-in]] has been assigned to the person yet. Check **Pending measurements** on the scale device. If it is above 0, follow [[guides/resolve-pending-measurements]]. For a new person with no starting weight, press **Weighing in** before the first weigh-in.

## Every weigh-in becomes pending

| Cause | Fix |
| --- | --- |
| Two people are within the margin (2 kg) of each other. | Press **Weighing in** before stepping on, or link a `person` entity to each person. |
| The person's weight moved more than the tolerance (5 kg or 7 %) since the last weigh-in. | Assign the pending measurement once. The history then follows the new weight. |
| The scale's people list is empty. | Select people under **Configure** on the scale entry. |
| Everyone on the scale is `not_home`. | Check the `person` entities, or remove the link under **Edit a person**. |

## The scale shows a weight and the person has no body fat

The scale device's **Weight** follows every advert. The person's sensors update once per weigh-in, after the reading settles. Stand still until **Reading stable** turns on.

## The method attribute is always bmi

The body-fat sensors carry a `method` attribute. `bmi` means the impedance route was rejected:

- The raw impedance code is 0: a foot missed a pad. Stand with bare feet on both pad pairs.
- The assumed impedance is outside 325 to 735 ohm. Enable **Impedance (raw)** on the person's device and check that the code is between 127 and 287.
- The person is under 16.

See [[concepts/body-composition]].

## Body composition looks wrong

Check the person's height, sex and birth date under **Configure > Edit a person**. Wet feet lower the impedance and socks block it.

## Values are old after a restart

Sensors restore their last value after a restart and keep it until the next weigh-in. Step on the scale to refresh them.

## A scale entry shows an error

| Message | Cause | Fix |
| --- | --- | --- |
| `The ANKO people entry is missing. Remove this scale and add it again to recreate it.` | The People entry was deleted. | Delete the scale entry and add the scale again. |
| `Waiting for the ANKO people entry to take over this scale's people.` | The 2.0 migration is running. | Wait a few seconds. Home Assistant retries. |
| `The ANKO people entry is not loaded.` | An action ran while the People entry was disabled or failed. | Enable or reload **ANKO Body Scale people**. |

:::see-also
- [[guides/report-a-problem]]
- [[concepts/limitations]]
:::
