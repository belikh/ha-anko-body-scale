---
title: ANKO Body Scale
summary: A Home Assistant integration that reads weight and body composition from the ANKO iF1012D Bluetooth body scale.
---

The integration reads the ANKO iF1012D body scale, sold by Kmart Australia and advertised over Bluetooth as `IF_B7`. Home Assistant listens to the scale's [[term:Advert]] broadcasts. It opens no connection to the scale and sends nothing to the internet.

Each [[term:Weigh-in]] gives a weight and a raw impedance code. The integration assigns the weigh-in to a [[term:Person]] by weight and computes 12 body-composition values from that person's height, age and sex.

[![Add to Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=belikh&repository=ha-anko-body-scale&category=integration)

## What you get

- Setup from the UI with Bluetooth discovery.
- One device per person with 14 sensors. They cover weight, BMI, body fat, fat mass, lean mass, muscle mass, body water, bone mass, basal metabolic rate, metabolic age and visceral fat index.
- People shared by every scale. Each scale can be limited to some of the people.
- A [[term:Pending measurement]] for a weigh-in that fits two people or nobody, with actions, events and phone notifications to resolve it.
- Six actions, two events and a repair that adds a person from an unknown weight.
- Weight history and pending measurements that survive a restart.
- A diagnostics download with names, birth dates and the Bluetooth address redacted.

## Where to start

:::see-also
- [[start/install]]
- [[start/set-up]]
- [[guides/manage-people]]
- [[reference/entities]]
- [[guides/troubleshoot]]
:::
