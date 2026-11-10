"""Move the people of v2 scale entries into the shared People entry.

A v2 scale entry holds its people in its options, and its person entities and
devices carry the scale address in their unique ids. The People entry takes
over: it merges the people, moves the registry rows (same entity ids, same
device ids), copies weight history and gives each scale an allowlist of its
former people. The steps are repeatable, so an interrupted run finishes on
the next start.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .config_flow import new_profile_id
from .const import (
    CONF_ADDRESS,
    CONF_DISPLAY_NAME,
    CONF_HISTORY_SIZE,
    CONF_MARGIN_KG,
    CONF_NOTIFY_SERVICE,
    CONF_PENDING_TIMEOUT,
    CONF_PEOPLE,
    CONF_PERSONS,
    CONF_PROFILE_ID,
    CONF_TOLERANCE_KG,
    CONF_TOLERANCE_PCT,
    DOMAIN,
    PERSON_DEVICE_PREFIX,
    PERSON_UNIQUE_PREFIX,
)
from .people import is_people_entry
from .store import AnkoScaleStore

_LOGGER = logging.getLogger(__name__)

SETTING_KEYS = (
    CONF_TOLERANCE_KG,
    CONF_TOLERANCE_PCT,
    CONF_MARGIN_KG,
    CONF_HISTORY_SIZE,
    CONF_PENDING_TIMEOUT,
    CONF_NOTIFY_SERVICE,
)

# Unique-id suffixes that belong to the scale itself, not to a person.
SCALE_UNIQUE_KEYS = frozenset(
    {
        "weight",
        "impedance",
        "last_person",
        "pending_count",
        "reading_stable",
        "next_person",
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
    }
)


def _match_person(
    legacy: dict[str, Any], people: list[dict[str, Any]]
) -> tuple[str, bool]:
    """Return the People id for a legacy person and whether it is new.

    A person with the same name (case-insensitive) is the same person. A new
    person keeps its id unless another person already uses it.
    """
    name = str(legacy[CONF_DISPLAY_NAME]).casefold()
    for person in people:
        if str(person[CONF_DISPLAY_NAME]).casefold() == name:
            return person[CONF_PROFILE_ID], False
    person = dict(legacy)
    taken = {p[CONF_PROFILE_ID] for p in people}
    if person[CONF_PROFILE_ID] in taken:
        person[CONF_PROFILE_ID] = new_profile_id(person[CONF_DISPLAY_NAME], people)
    people.append(person)
    return person[CONF_PROFILE_ID], True


def _legacy_scales(hass: HomeAssistant) -> list[ConfigEntry]:
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if not is_people_entry(entry) and CONF_PERSONS in entry.options
    ]


def _person_key(rest: str, id_map: dict[str, str]) -> tuple[str, str] | None:
    """Split '<legacy id>_<key>' into (new person id, key)."""
    if rest in SCALE_UNIQUE_KEYS:
        return None
    for legacy_id in sorted(id_map, key=len, reverse=True):
        if rest.startswith(f"{legacy_id}_"):
            return id_map[legacy_id], rest[len(legacy_id) + 1 :]
    return None


def _move_registry(
    hass: HomeAssistant,
    people: ConfigEntry,
    scale: ConfigEntry,
    address: str,
    id_map: dict[str, str],
) -> None:
    """Re-home one scale's person devices and entities onto the People entry."""
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    # Devices: keep the row, add the People entry, rename the identifier.
    moved: list[tuple[str, bool]] = []
    for device in dr.async_entries_for_config_entry(devices, scale.entry_id):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN or not identifier.startswith(f"{address}:"):
                continue
            legacy_id = identifier[len(address) + 1 :]
            if legacy_id not in id_map:
                break
            target = (DOMAIN, f"{PERSON_DEVICE_PREFIX}{id_map[legacy_id]}")
            existing = devices.async_get_device_by_identifier(target, people.entry_id)
            if existing is not None and existing.id != device.id:
                moved.append((device.id, True))
            else:
                devices.async_update_device(
                    device.id,
                    add_config_entry_id=people.entry_id,
                    new_identifiers={target},
                    via_device_id=None,
                )
                moved.append((device.id, False))
            break

    # Entities: new unique id and owner, same registry row and entity id.
    prefix = f"{address}_"
    for entity in er.async_entries_for_config_entry(entities, scale.entry_id):
        if entity.platform != DOMAIN or not entity.unique_id.startswith(prefix):
            continue
        parsed = _person_key(entity.unique_id[len(prefix) :], id_map)
        if parsed is None:
            continue
        person_id, key = parsed
        new_unique_id = f"{PERSON_UNIQUE_PREFIX}{person_id}_{key}"
        existing_id = entities.async_get_entity_id(entity.domain, DOMAIN, new_unique_id)
        if existing_id is not None and existing_id != entity.entity_id:
            entities.async_remove(entity.entity_id)
            continue
        entities.async_update_entity(
            entity.entity_id,
            config_entry_id=people.entry_id,
            new_unique_id=new_unique_id,
        )

    for device_id, duplicate in moved:
        if duplicate:
            devices.async_remove_device(device_id)
        else:
            devices.async_update_device(
                device_id, remove_config_entry_id=scale.entry_id
            )


async def async_adopt_legacy_scales(hass: HomeAssistant, people: ConfigEntry) -> None:
    """Adopt every v2 scale entry into the People entry (no-op when none).

    Order: merge people and history first, then move registry rows, then clear
    each scale's old options. A scale keeps its old options until its rows are
    moved, so an interrupted run repeats the unfinished scale only.
    """
    legacy = _legacy_scales(hass)
    if not legacy:
        return

    persons = [dict(p) for p in people.options.get(CONF_PERSONS, [])]
    options = dict(people.options)
    hub_store = AnkoScaleStore(hass, people.entry_id)
    hub_data = await hub_store.async_load()
    hub_history: dict[str, Any] = hub_data.setdefault("persons", {})

    id_maps: dict[str, dict[str, str]] = {}
    for scale in legacy:
        stored = (await AnkoScaleStore(hass, scale.entry_id).async_load()).get(
            "persons", {}
        )
        id_map = id_maps[scale.entry_id] = {}
        for legacy_person in scale.options[CONF_PERSONS]:
            person_id, _ = _match_person(legacy_person, persons)
            id_map[legacy_person[CONF_PROFILE_ID]] = person_id
            saved = stored.get(legacy_person[CONF_PROFILE_ID])
            if not saved:
                continue
            if person_id not in hub_history:
                hub_history[person_id] = saved
            elif hub_history[person_id] != saved:
                _LOGGER.warning(
                    "%s is on more than one scale; keeping the weight history "
                    "from the first scale and dropping the one from %s",
                    legacy_person[CONF_DISPLAY_NAME],
                    scale.title,
                )
        for key in SETTING_KEYS:
            if key in scale.options and key not in options:
                options[key] = scale.options[key]

    await hub_store.async_save(hub_data)
    hass.config_entries.async_update_entry(
        people, options={**options, CONF_PERSONS: persons}
    )

    everyone = {p[CONF_PROFILE_ID] for p in persons}
    for scale in legacy:
        id_map = id_maps[scale.entry_id]
        _move_registry(hass, people, scale, scale.data[CONF_ADDRESS], id_map)
        allowed = list(dict.fromkeys(id_map.values()))
        # A scale that had every person keeps following the full list, so
        # people added later can use it.
        scale_options = {} if set(allowed) == everyone else {CONF_PEOPLE: allowed}
        hass.config_entries.async_update_entry(scale, options=scale_options)
        _LOGGER.info("Moved the people of scale %s to the People entry", scale.entry_id)
