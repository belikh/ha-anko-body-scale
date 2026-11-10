"""The ANKO Body Scale integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

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
    PERSON_DEVICE_PREFIX,
    SERVICE_ASSIGN,
    SERVICE_CAPTURE,
    SERVICE_REASSIGN,
    SERVICE_RESET_HISTORY,
    SERVICE_SET_NEXT_PERSON,
)
from .coordinator import AnkoScaleCoordinator
from .migration import async_adopt_legacy_scales
from .people import (
    HUB_KEY,
    PeopleHub,
    async_ensure_hub,
    async_release_hub,
    find_people_entry,
    is_people_entry,
)

_LOGGER = logging.getLogger(__name__)

SCALE_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]
PEOPLE_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

_CREATE_LOCK: HassKey[asyncio.Lock] = HassKey("anko_scale_create_people_lock")

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_DISCARD = "discard_measurement"
_ENTRY: dict[Any, Any] = {vol.Optional("config_entry_id"): cv.string}
ASSIGN_SCHEMA = vol.Schema(
    {**_ENTRY, vol.Required("pending_id"): cv.string, vol.Required("person_id"): str}
)
DISCARD_SCHEMA = vol.Schema({**_ENTRY, vol.Required("pending_id"): cv.string})
PERSON_SCHEMA = vol.Schema({vol.Required("person_id"): cv.string})
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
    """Return the scale coordinator a service call targets."""
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


def _hub_for(hass: HomeAssistant) -> PeopleHub:
    """Return the shared people hub."""
    hub = hass.data.get(HUB_KEY)
    if hub is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="people_unavailable"
        )
    return hub


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration services (once, independent of config entries)."""

    async def _assign(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_assign_pending(
            call.data["pending_id"], call.data["person_id"]
        )

    async def _discard(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_discard_pending(call.data["pending_id"])

    async def _reassign(call: ServiceCall) -> None:
        _hub_for(hass).reassign_last(call.data["person_id"])

    async def _set_next(call: ServiceCall) -> None:
        _coordinator_for(hass, call).async_set_next_person(call.data.get("person_id"))

    async def _reset(call: ServiceCall) -> None:
        _hub_for(hass).reset_history(call.data["person_id"])

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
    async_register_admin_service(
        hass, DOMAIN, SERVICE_DISCARD, _discard, DISCARD_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_REASSIGN, _reassign, PERSON_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_NEXT_PERSON, _set_next, NEXT_PERSON_SCHEMA
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_RESET_HISTORY, _reset, PERSON_SCHEMA
    )
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Bring older scale entries up to version 3.

    v1 held one profile in the options. v2 held a list of persons. v3 keeps
    people in the shared People entry; a v2 scale keeps its persons in the
    options until that entry adopts them (see migration.py).
    """
    if entry.version > 3:
        return False

    options = dict(entry.options)
    if entry.version == 1:
        person = {
            CONF_PROFILE_ID: "legacy",
            CONF_DISPLAY_NAME: "Person 1",
            CONF_HEIGHT_CM: options.get(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM),
            CONF_AGE: options.get(CONF_AGE, DEFAULT_AGE),
            CONF_SEX: options.get(CONF_SEX, DEFAULT_SEX),
        }
        options = {CONF_PERSONS: [person]}
    if entry.version < 3:
        hass.config_entries.async_update_entry(entry, options=options, version=3)
        _LOGGER.info("Migrated ANKO scale entry %s to version 3", entry.entry_id)
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
def _register_scale_device(
    hass: HomeAssistant, entry: ConfigEntry, address: str
) -> None:
    """Register the scale device, keeping the 1.x identifier and name."""
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name="ANKO Body Scale",
        manufacturer="ANKO",
        model="iF1012D",
    )


@callback
def _register_person_devices(
    hass: HomeAssistant, entry: ConfigEntry, hub: PeopleHub
) -> None:
    """Register one device per person; drop devices of deleted people."""
    registry = dr.async_get(hass)
    keep: set[str] = set()
    for person in hub.persons:
        identifier = f"{PERSON_DEVICE_PREFIX}{person.profile_id}"
        keep.add(identifier)
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, identifier)},
            name=person.display_name,
            manufacturer="ANKO",
            model="iF1012D person",
        )

    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN or not identifier.startswith(PERSON_DEVICE_PREFIX):
                continue
            if identifier not in keep:
                registry.async_update_device(
                    device.id, remove_config_entry_id=entry.entry_id
                )
            break


async def _async_create_people_entry(hass: HomeAssistant) -> None:
    """Create the People entry; it adopts the data of v2 scale entries."""
    lock = hass.data.setdefault(_CREATE_LOCK, asyncio.Lock())
    async with lock:
        if find_people_entry(hass) is None:
            await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data={}
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a scale entry or the People entry."""
    if is_people_entry(entry):
        return await _async_setup_people(hass, entry)
    return await _async_setup_scale(hass, entry)


async def _async_setup_people(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Adopt v2 scale data, start the shared hub and add person entities."""
    await async_adopt_legacy_scales(hass, entry)
    hub = await async_ensure_hub(hass, entry)
    _register_person_devices(hass, entry, hub)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PEOPLE_PLATFORMS)
    # Scales that started against an earlier hub must pick up this one.
    for scale in hass.config_entries.async_entries(DOMAIN):
        coordinator = hass.data.get(DOMAIN, {}).get(scale.entry_id)
        if coordinator is not None and coordinator.hub is not hub:
            hass.config_entries.async_schedule_reload(scale.entry_id)
    return True


async def _async_setup_scale(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one scale on top of the shared hub."""
    people = find_people_entry(hass)
    if people is None:
        if CONF_PERSONS not in entry.options:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="people_missing"
            )
        await _async_create_people_entry(hass)
        people = find_people_entry(hass)
        if people is None:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="people_missing"
            )
    if CONF_PERSONS in entry.options:
        # The People entry moves this scale's people over when it loads.
        if people.state is ConfigEntryState.LOADED:
            hass.config_entries.async_schedule_reload(people.entry_id)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="people_adopting"
        )

    hub = await async_ensure_hub(hass, people)
    coordinator = AnkoScaleCoordinator(hass, entry, hub)
    await coordinator.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    _register_scale_device(hass, entry, coordinator.address)
    _remove_scale_body_sensors(hass, entry, coordinator.address)
    coordinator.async_start()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(coordinator.async_stop)

    await hass.config_entries.async_forward_entry_setups(entry, SCALE_PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after an options change.

    Reloading the People entry reloads the scales that held its old hub.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a scale entry or the People entry."""
    if is_people_entry(entry):
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, PEOPLE_PLATFORMS
        )
        if unload_ok:
            await async_release_hub(hass)
        return unload_ok

    unload_ok = await hass.config_entries.async_unload_platforms(entry, SCALE_PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
