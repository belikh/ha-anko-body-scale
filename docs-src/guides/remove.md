---
title: Remove the integration
summary: Delete the scale and people entries, then the integration files.
order: 80
audience: users
status: draft
---

1. Open **Settings > Devices & Services > ANKO Body Scale**.
2. On each scale entry, open the three-dot menu and select **Delete**. Home Assistant removes the scale device and its entities.
3. Delete **ANKO Body Scale people** the same way. Home Assistant removes every person device and the stored weight history.
4. Remove the integration in HACS, or delete the `custom_components/anko_scale` folder.
5. Restart Home Assistant.

:::see-also
- [[start/install]]
:::
