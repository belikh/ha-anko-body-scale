"""Binary sensor platform for the ANKO Body Scale integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import AnkoScaleCoordinator
from .entity import scale_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ANKO Body Scale binary sensor from a config entry."""
    coordinator: AnkoScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AnkoScaleStableBinarySensor(coordinator)])


class AnkoScaleStableBinarySensor(BinarySensorEntity, RestoreEntity):
    """Whether the most recent scale reading has settled."""

    _attr_has_entity_name = True
    _attr_translation_key = "reading_stable"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AnkoScaleCoordinator) -> None:
        """Initialise the reading-stable binary sensor."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_reading_stable"
        self._attr_device_info = scale_device_info(coordinator.address)
        self._restored_is_on: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return whether the most recent reading has settled."""
        if self._coordinator.reading is not None:
            return self._coordinator.reading.stable
        return self._restored_is_on

    @property
    def available(self) -> bool:
        """Return whether any reading has been received or restored."""
        if self._coordinator.reading is not None:
            return True
        return self._restored_is_on is not None

    async def async_added_to_hass(self) -> None:
        """Restore the last state and subscribe to new readings."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in ("on", "off"):
            self._restored_is_on = last_state.state == "on"
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
