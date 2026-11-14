---
title: Settings
summary: The attribution settings and the fixed timing values, with ranges and defaults.
order: 40
audience: users
status: draft
---

## Attribution settings

Open **Configure** on **ANKO Body Scale people** and choose **Attribution settings**. The settings apply to every scale.

| Setting | Default | Range | Effect |
| --- | --- | --- | --- |
| Tolerance (kg) | 5 | 1 to 50, step 0.5 | A weigh-in matches a person within this distance of their [[term:Expected weight]]. |
| Tolerance (% of expected weight) | 7 | 1 to 50, step 0.5 | The larger of the two tolerances applies. |
| Margin to runner-up (kg) | 2 | 0 to 20, step 0.5 | The closest person must be this much closer than the next person. |
| Readings kept per person | 50 | 5 to 200 | Size of the weight history behind the expected weight. |
| Pending timeout (minutes) | 60 | 1 to 1440 | Life of a [[term:Pending measurement]]. |
| Notify action | empty | text | A notify action such as `notify.mobile_app_phone`. It receives each pending measurement with answer buttons. |

For a person with an expected weight of 80 kg, the default tolerance is `max(5, 80 × 7 %)` = 5.6 kg.

## Fixed values

These values are constants in `const.py` and `coordinator.py`.

| Value | Constant | Meaning |
| --- | --- | --- |
| 3 adverts | `SETTLE_FRAMES` | Stable adverts that make a weigh-in. |
| 0.5 kg | `SETTLE_SPREAD_KG` | Largest spread between those adverts. |
| 5 s | `SETTLE_WINDOW_S` | Time window for those adverts. |
| 5 s | `SETTLE_TIMEOUT_S` | Silence after which the last stable adverts become the weigh-in. |
| 0.3 | `EWMA_ALPHA` | Weight of the newest reading in the expected weight. |
| 60 s | `FORCE_ASSIGN_TIMEOUT_S` | Life of a **Weighing in** or **Next person** override. |
| 10 | `MAX_PENDING` | Pending measurements kept per scale. |
| 30 | `MAX_RECENT_FRAMES` | Distinct adverts kept for diagnostics. |

The person fields and their ranges are in [[start/set-up]].

:::see-also
- [[concepts/attribution]]
- [[guides/manage-people]]
:::
