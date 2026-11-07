"""The ANKO Body Scale integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AGE,
    CONF_DISPLAY_NAME,
    CONF_HEIGHT_CM,
    CONF_PERSONS,
    CONF_PROFILE_ID,
    CONF_SEX,
    DEFAULT_AGE,
    DEFAULT_HEIGHT_CM,
    DEFAULT_SEX,
    DOMAIN,
    LEGACY_DISPLAY_NAME,
    LEGACY_PROFILE_ID,
    SERVICE_ASSIGN,
    SERVICE_CAPTURE,
    SERVICE_REASSIGN,
    SERVICE_RESET_HISTORY,
    SERVICE_SET_NEXT_PERSON,
)
from .coordinator import AnkoScaleCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_DISCARD = "discard_measurement"
_ENTRY: dict[Any, Any] = {vol.Optional("config_entry_id"): cv.string}
ASSIGN_SCHEMA = vol.Schema(
    {**_ENTRY, vol.Required("pending_id"): cv.string, vol.Required("person_id"): str}
)
DISCARD_SCHEMA = vol.Schema({**_ENTRY, vol.Required("pending_id"): cv.string})
PERSON_SCHEMA = vol.Schema({**_ENTRY, vol.Required("person_id"): cv.string})
CAPTURE_SCHEMA = vol.Schema(
    {
        **_ENTRY,
        vol.Optional("timeout", default=60): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
    }
)
NEXT_PERSON_SCHEMA = vol.Schema({**_ENTRY, vol.Optional("person_id"): cv.string})


def _coordinator_for(hass: HomeAssistant, call: ServiceCall) -> AnkoScaleCoordinator:
    """Return the coordinator a service call targets."""
    coordinators: dict[str, AnkoScaleCoordinator] = hass.data.get(DOMAIN, {})
    entry_id = call.data.get("config_entry_id")
    if entry_id is not None:
        if entry_id not in coordinators:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_entry",
                translation_placeholders={"entry_id": entry_id},
            )
        return coordinators[entry_id]
    if len(coordinators) == 1:
        return next(iter(coordinators.values()))
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="entry_required"
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration services (once, independent of config entries)."""

    async def _assign(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_assign_pending(
            call.data["pending_id"], call.data["person_id"]
        )

    async def _discard(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_discard_pending(call.data["pending_id"])

    async def _reassign(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_reassign_last(call.data["person_id"])

    async def _set_next(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_set_next_person(call.data.get("person_id"))

    async def _reset(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_reset_person_history(call.data["person_id"])

    async def _capture(call: ServiceCall) -> ServiceResponse:
        return await _coordinator_for(hass, call).async_capture_measurement(
            call.data["timeout"]
        )

    hass.services.async_register(DOMAIN, SERVICE_ASSIGN, _assign, ASSIGN_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE,
        _capture,
        CAPTURE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(DOMAIN, SERVICE_DISCARD, _discard, DISCARD_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REASSIGN, _reassign, PERSON_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_NEXT_PERSON, _set_next, NEXT_PERSON_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RESET_HISTORY, _reset, PERSON_SCHEMA)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a v1 entry (single profile) to v2 (list of persons).

    entry.data, the unique id and the entry id are left untouched, so entity
    unique ids and entity ids of the scale device stay the same.
    """
    if entry.version > 2:
        return False

    if entry.version == 1:
        old = dict(entry.options)
        person = {
            CONF_PROFILE_ID: LEGACY_PROFILE_ID,
            CONF_DISPLAY_NAME: LEGACY_DISPLAY_NAME,
            CONF_HEIGHT_CM: old.get(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM),
            CONF_AGE: old.get(CONF_AGE, DEFAULT_AGE),
            CONF_SEX: old.get(CONF_SEX, DEFAULT_SEX),
        }
        hass.config_entries.async_update_entry(
            entry, options={CONF_PERSONS: [person]}, version=2
        )
        _LOGGER.info("Migrated ANKO scale entry %s to version 2", entry.entry_id)

    return True


# Scale-level body-composition sensors removed in 1.3.0; they duplicated the
# person sensors and showed whoever weighed in last.
_REMOVED_SCALE_SENSOR_KEYS = (
    "bmi",
    "body_fat_percent",
    "fat_mass",
    "lean_mass",
    "muscle_mass",
    "body_water",
    "bone_mass",
    "bmr",
    "metabolic_age",
    "visceral_fat_index",
    "ideal_weight_min",
    "ideal_weight_max",
)


@callback
def _remove_scale_body_sensors(
    hass: HomeAssistant, entry: ConfigEntry, address: str
) -> None:
    """Delete the retired scale-level body-composition entities."""
    registry = er.async_get(hass)
    stale = {f"{address}_{key}" for key in _REMOVED_SCALE_SENSOR_KEYS}
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == "sensor" and entity.unique_id in stale:
            registry.async_remove(entity.entity_id)


@callback
def _register_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: AnkoScaleCoordinator
) -> None:
    """Register the scale and one device per person; drop deleted people.

    The scale device keeps the 1.x identifier and name, so existing entities
    stay attached to it. Person devices point at it through via_device_id.
    """
    registry = dr.async_get(hass)
    scale = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.address)},
        name="ANKO Body Scale",
        manufacturer="ANKO",
        model="iF1012D",
    )
    keep: set[str] = set()
    for person in coordinator.persons:
        identifier = f"{coordinator.address}:{person.profile_id}"
        keep.add(identifier)
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, identifier)},
            name=person.display_name,
            manufacturer="ANKO",
            model="iF1012D person",
            via_device_id=scale.id,
        )

    prefix = f"{coordinator.address}:"
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN or not identifier.startswith(prefix):
                continue
            if identifier not in keep:
                registry.async_update_device(
                    device.id, remove_config_entry_id=entry.entry_id
                )
            break


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the ANKO Body Scale from a config entry."""
    coordinator = AnkoScaleCoordinator(hass, entry)
    await coordinator.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    _register_devices(hass, entry, coordinator)
    _remove_scale_body_sensors(hass, entry, coordinator.address)
    coordinator.async_start()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(coordinator.async_stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options (persons, settings) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
