---
title: Manage people
summary: Add, edit and delete people, and send a weigh-in to a person by hand.
order: 10
audience: users
status: draft
---

People live in the [[term:People entry]]. Open **Settings > Devices & Services > ANKO Body Scale**, find **ANKO Body Scale people** and select **Configure**.

| Menu item | Result |
| --- | --- |
| Add a person | Opens the person form from [[start/set-up]]. |
| Add from a Home Assistant person | Asks for a `person` entity, then opens the form with the name filled in and the entity linked. |
| Edit a person | Changes the same fields. The [[term:Profile ID]] and the entity IDs stay the same. |
| Delete a person | Removes the person's device, entities and weight history. |
| Attribution settings | Opens the settings in [[reference/settings]]. |

Saving reloads the entry.

## Add a person

1. Select **Configure** on **ANKO Body Scale people**, then **Add a person**.
2. Fill in the name, height, sex and a birth date or an age.
3. Type a **Starting weight** if you know it. A person with no starting weight and no history cannot be matched by weight.
4. Select **Submit**. The new device appears with 14 sensors and a **Weighing in** button.

A scale set to everyone includes the new person. A scale limited to some people does not: add the person under **Configure** on that scale.

## Send the next weigh-in to a person

Use this for a first weigh-in with no starting weight, or when two people have similar weights.

1. Press **Weighing in** on the person's device, or choose the person in **Next person** on the scale device.
2. Step on the scale within 60 seconds.

The next [[term:Weigh-in]] goes to that person and joins their weight history. The override ends after one weigh-in or 60 seconds. **Weighing in** arms every scale that allows the person. **Next person** arms one scale.

## Skip a person who is away

1. Select **Configure** on **ANKO Body Scale people**, then **Edit a person**.
2. Choose the person's `person` entity in **Person entity** and select **Submit**.

While that entity is `not_home`, the integration never assigns a weigh-in to the person automatically.

## Delete a person

1. Select **Configure** on **ANKO Body Scale people**, then **Delete a person**.
2. Choose the person and select **Submit**.

:::warning History is deleted
Deleting a person removes their device, entities and stored weights. The weight history cannot be recovered.
:::

The deleted person leaves every scale's list. A scale left with no people holds each weigh-in as a [[term:Pending measurement]] until you pick people under **Configure** on that scale.

:::see-also
- [[guides/add-a-second-scale]]
- [[guides/resolve-pending-measurements]]
- [[concepts/attribution]]
:::
