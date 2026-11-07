"""Persistent state (expected-weight history, pending queue) for one entry."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SAVE_DELAY_S = 5


class AnkoScaleStore:
    """Thin wrapper around helpers.storage.Store that never raises."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Create the store for one config entry."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}"
        )

    async def async_load(self) -> dict[str, Any]:
        """Load stored data, returning an empty dict on any failure."""
        try:
            data = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Could not load stored ANKO scale data; starting empty")
            return {}
        return data if isinstance(data, dict) else {}

    def async_schedule_save(self, data_func: Any) -> None:
        """Save after a short delay; later calls within the delay coalesce."""
        self._store.async_delay_save(data_func, SAVE_DELAY_S)

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save immediately, logging instead of raising."""
        try:
            await self._store.async_save(data)
        except Exception:
            _LOGGER.exception("Could not save ANKO scale data")
