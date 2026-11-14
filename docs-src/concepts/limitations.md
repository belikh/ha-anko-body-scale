---
title: Limitations
summary: What the integration cannot do, and the reason for each limit.
order: 40
audience: users
status: draft
---

| Limit | Reason | What to do |
| --- | --- | --- |
| People with similar weights produce pending measurements. | Weight is the only signal that tells people apart. | Press **Weighing in** first, or link a `person` entity to each person. |
| Body fat from impedance is provisional. | The conversion of the raw impedance code to ohms is assumed (2.56 ohm per count). | Follow the trend of one person over weeks. |
| Socks, shoes or one foot off the pads give `method: bmi`. | The scale reports code 0 without contact on both pad pairs. | Weigh in with bare feet. |
| One impedance value per weigh-in. | The scale measures foot to foot at one frequency. It cannot measure arms or the trunk separately. | None. |
| Home Assistant cannot start a weigh-in or read the scale's memory. | The integration listens to adverts and never connects. | Step on the scale. |
| A weigh-in out of Bluetooth range is lost. | The scale sends adverts only while someone stands on it. | Put a Bluetooth proxy near the scale. |
| `reassign_measurement` fails after a restart. | The last weigh-in is held in memory. | Reassign before you restart. |
| One model is supported. | The parser was checked against the ANKO iF1012D (`IF_B7`) only. | Open an issue with a diagnostics file for another Senssun scale. |

:::see-also
- [[concepts/body-composition]]
- [[guides/troubleshoot]]
:::
