"""Select platform: choose who the next weigh-in belongs to."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnkoScaleCoordinator
from .entity import scale_device_info

PARALLEL_UPDATES = 0

AUTOMATIC = "Automatic"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the next-person select."""
    coordinator: AnkoScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AnkoNextPersonSelect(coordinator)])


class AnkoNextPersonSelect(SelectEntity):
    """One-shot manual assignment of the next stable reading."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_person"

    def __init__(self, coordinator: AnkoScaleCoordinator) -> None:
        """Initialise the select."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_next_person"
        self._attr_device_info = scale_device_info(coordinator.address)
        self._names = {p.profile_id: p.display_name for p in coordinator.persons}
        self._attr_options = [AUTOMATIC, *self._names.values()]

    @property
    def current_option(self) -> str:
        """Return the armed person, or Automatic."""
        profile_id = self._coordinator.next_person
        return self._names.get(profile_id, AUTOMATIC) if profile_id else AUTOMATIC

    async def async_select_option(self, option: str) -> None:
        """Arm a person for the next weigh-in, or clear the override."""
        for profile_id, name in self._names.items():
            if name == option:
                self._coordinator.async_set_next_person(profile_id)
                return
        self._coordinator.async_set_next_person(None)

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
