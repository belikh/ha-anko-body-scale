"""Button platform: arm a one-shot assignment for the next weigh-in."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .attribution import PersonProfile
from .const import DOMAIN
from .coordinator import AnkoScaleCoordinator
from .entity import person_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one weigh-in button per person."""
    coordinator: AnkoScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AnkoWeighInButton(coordinator, p) for p in coordinator.persons)


class AnkoWeighInButton(ButtonEntity):
    """Assigns the next stable reading to this person (expires after 60 s)."""

    _attr_has_entity_name = True
    _attr_translation_key = "weighing_in"

    def __init__(
        self, coordinator: AnkoScaleCoordinator, profile: PersonProfile
    ) -> None:
        """Initialise the button."""
        self._coordinator = coordinator
        self._profile_id = profile.profile_id
        self._attr_unique_id = f"{coordinator.address}_{profile.profile_id}_weighing_in"
        self._attr_device_info = person_device_info(coordinator.address, profile)

    async def async_press(self) -> None:
        """Arm this person for the next weigh-in."""
        self._coordinator.async_set_next_person(self._profile_id)
