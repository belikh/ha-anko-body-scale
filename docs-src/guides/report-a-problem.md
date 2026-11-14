---
title: Report a problem
summary: Collect a debug log and a diagnostics file for a bug report.
order: 70
audience: users
status: draft
---

Open an [issue](https://github.com/belikh/ha-anko-body-scale/issues/new/choose) and fill in the bug report form. It asks for the scale model, the integration version and the debug log.

## Collect the debug log

1. Open **Settings > Devices & Services > ANKO Body Scale**.
2. Choose **Enable debug logging** from the three-dot menu.
3. Repeat the problem.
4. Choose **Disable debug logging**. The browser downloads `home-assistant_anko_scale_<date>.log`.

The log covers only the time between the two clicks. It can include your Bluetooth address, so read the file before you post it.

To keep debug logging on across restarts, add this to `configuration.yaml`:

```yaml title="configuration.yaml"
logger:
  logs:
    custom_components.anko_scale: debug
```

## Download diagnostics

1. Open **Settings > Devices & Services > ANKO Body Scale**.
2. Choose **Download diagnostics** from the three-dot menu of the scale entry.

| Content | Detail |
| --- | --- |
| `integration_version` | Version from `manifest.json`. |
| `entry` | Entry data and options. Names, birth dates, `person` entities, profile IDs, the notify action and the Bluetooth address are redacted. |
| `counts` | Adverts, stable adverts, weigh-ins, pending measurements and unknown weights since the entry loaded. |
| `rssi` | Signal strength of the last advert. |
| `last_raw_frame`, `recent_frames` | The last advert and the last 30 distinct adverts as hex, with the Bluetooth address redacted. |

The diagnostics of the People entry list each person by index with the length of their history and the time of their last weigh-in. The file holds no weight history. `recent_frames` holds the parsed weight of each advert.

:::see-also
- [[guides/troubleshoot]]
:::
