---
title: How readings are assigned
summary: The steps that turn the scale's adverts into one weigh-in and choose the person it belongs to.
order: 10
audience: users
status: draft
---

The scale reports a weight and an impedance code. It does not say who is standing on it, so the integration chooses the person by weight.

## From adverts to a weigh-in

The scale sends adverts while someone stands on it. The settling buffer turns them into one [[term:Weigh-in]]:

1. It collects adverts that carry the stable status.
2. Three stable adverts within 0.5 kg and 5 seconds make a weigh-in.
3. If the scale goes quiet for 5 seconds first, the last stable adverts make the weigh-in.

One step on the scale gives one set of values.

## Choosing the person

1. If **Weighing in**, **Next person** or `set_next_person` named a person in the last 60 seconds, that person gets the weigh-in.
2. The integration sets aside people whose `person` entity is `not_home`.
3. If the scale has one person, that person gets the weigh-in.
4. Each remaining person with an [[term:Expected weight]] becomes a candidate. The distance is the difference between the weigh-in and the expected weight.
5. The closest candidate wins when two conditions hold. The distance is within the tolerance, `max(5 kg, 7 % of the expected weight)`. The next candidate is at least the margin, 2 kg, further away.
6. Any other weigh-in becomes a [[term:Pending measurement]].

## Worked example

Jupiter has an expected weight of 81.0 kg and Sarah 64.0 kg.

| Weigh-in | Distance to Jupiter | Distance to Sarah | Result |
| --- | --- | --- | --- |
| 80.2 kg | 0.8 kg | 16.2 kg | Jupiter, source `weight_match`. |
| 72.5 kg | 8.5 kg | 8.5 kg | Pending, reason `no_match`: Jupiter's tolerance is 5.67 kg and Sarah's is 5 kg. |
| 95.0 kg | 14.0 kg | 31.0 kg | Pending, reason `no_match`, and a repair to add a person. |

With Jupiter at 70.0 kg and Sarah at 68.0 kg, a weigh-in of 69.2 kg is 0.8 kg from Jupiter and 1.2 kg from Sarah. Both are within tolerance and the gap is 0.4 kg, so the weigh-in is pending with reason `ambiguous`.

## Expected weight

The expected weight is an exponentially weighted average of the person's stored weights, oldest first, with alpha 0.3:

```text title="Update for each stored weight"
expected = 0.3 × weight + 0.7 × expected
```

The history holds the last 50 weights. A starting weight is the first item of the history. Every assigned weigh-in joins the history, including forced and assigned ones, so one press of **Weighing in** seeds a new person.

A person with an empty history has no expected weight and is never a candidate.

## Why weight

The advert carries no user slot, and the integration never connects to the scale to read one. Weight is the only signal in the advert that differs between people. The `person` entity filter and the **Weighing in** button cover the cases where weight is not enough.

:::see-also
- [[reference/settings]]
- [[guides/resolve-pending-measurements]]
- [[reference/events]]
:::
