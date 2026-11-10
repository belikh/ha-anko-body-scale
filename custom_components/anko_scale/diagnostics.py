"""Diagnostics for the ANKO Body Scale integration."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AnkoScaleCoordinator

TO_REDACT = {
    "address",
    "display_name",
    "person_entity",
    "birth_date",
    "unique_id",
    "profile_id",
    "notify_service",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _integration_version() -> str:
    manifest = Path(__file__).parent / "manifest.json"
    return str(json.loads(manifest.read_text(encoding="utf-8")).get("version"))


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with the BLE address and health history redacted."""
    coordinator: AnkoScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    address_hex = coordinator.address.replace(":", "").lower()

    def _redact(raw: str | None) -> str | None:
        return raw.replace(address_hex, "<redacted>") if raw else raw

    raw = _redact(coordinator.last_raw_hex)
    return {
        "integration_version": await hass.async_add_executor_job(_integration_version),
        "entry": async_redact_data(
            {
                "data": dict(entry.data),
                "options": dict(entry.options),
                "unique_id": entry.unique_id,
                "version": entry.version,
            },
            TO_REDACT,
        ),
        "persons": [
            {
                "index": index,
                "has_person_entity": person.person_entity is not None,
                "history_length": len(coordinator.history.get(person.profile_id, [])),
                "last_measurement": _iso(
                    coordinator.last_measured.get(person.profile_id)
                ),
            }
            for index, person in enumerate(coordinator.persons)
        ],
        "counts": {
            "adverts": coordinator.frame_count,
            "stable_adverts": coordinator.stable_frame_count,
            "weigh_ins": coordinator.weigh_in_count,
            "pending": len(coordinator.pending),
            "unknown_weights": coordinator.unknown_weight_count,
        },
        "rssi": coordinator.rssi,
        "last_raw_frame": raw,
        "recent_frames": [
            {**frame, "hex": _redact(frame["hex"])}
            for frame in coordinator.recent_frames
        ],
    }
