"""Button platform: arm a one-shot assignment for the next weigh-in."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .attribution import PersonProfile
from .const import PERSON_UNIQUE_PREFIX
from .entity import person_device_info
from .people import HUB_KEY, PeopleHub

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one weigh-in button per person."""
    hub = hass.data[HUB_KEY]
    async_add_entities(AnkoWeighInButton(hub, p) for p in hub.persons)


class AnkoWeighInButton(ButtonEntity):
    """Assigns the next stable reading to this person (expires after 60 s)."""

    _attr_has_entity_name = True
    _attr_translation_key = "weighing_in"

    def __init__(self, hub: PeopleHub, profile: PersonProfile) -> None:
        """Initialise the button."""
        self._hub = hub
        self._profile_id = profile.profile_id
        self._attr_unique_id = f"{PERSON_UNIQUE_PREFIX}{profile.profile_id}_weighing_in"
        self._attr_device_info = person_device_info(profile)

    async def async_press(self) -> None:
        """Arm this person on every scale that allows them."""
        self._hub.arm_next(self._profile_id)
