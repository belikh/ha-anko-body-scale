"""Upgrade from v1/v2 scale entries to the shared People entry."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.anko_scale.const import DOMAIN
from custom_components.anko_scale.people import HUB_KEY, find_people_entry

from .conftest import ADDRESS

SECOND = "11:22:33:44:55:66"

LEGACY = {
    "profile_id": "legacy",
    "display_name": "Person 1",
    "height_cm": 183,
    "age": 30,
    "sex": "male",
}
SETTINGS = {"tolerance_kg": 4.0, "margin_kg": 3.0}
PERSON_KEYS = ("weight", "impedance", "body_fat_percent")


def _v2(address: str, persons: list[dict], **extra) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=address,
        data={"address": address},
        options={"persons": persons, **extra},
        title="IF_B7",
    )


def _seed_registry(
    hass: HomeAssistant, entry: MockConfigEntry, persons: list[dict]
) -> dict[str, er.RegistryEntry]:
    """Create the rows a 2.x install leaves behind."""
    address = entry.data["address"]
    devices = dr.async_get(hass)
    registry = er.async_get(hass)
    scale = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name="ANKO Body Scale",
    )
    rows: dict[str, er.RegistryEntry] = {
        "scale_weight": registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{address}_weight",
            config_entry=entry,
            device_id=scale.id,
            suggested_object_id=f"anko_body_scale_weight_{address[-2:].lower()}",
        )
    }
    for person in persons:
        pid = person["profile_id"]
        device = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{address}:{pid}")},
            name=person["display_name"],
            via_device_id=scale.id,
        )
        name = person["display_name"].lower().replace(" ", "_")
        for key in PERSON_KEYS:
            rows[f"{pid}_{key}"] = registry.async_get_or_create(
                "sensor",
                DOMAIN,
                f"{address}_{pid}_{key}",
                config_entry=entry,
                device_id=device.id,
                suggested_object_id=f"{name}_{key}_{address[-2:].lower()}",
            )
        rows[f"{pid}_button"] = registry.async_get_or_create(
            "button",
            DOMAIN,
            f"{address}_{pid}_weighing_in",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=f"{name}_weighing_in_{address[-2:].lower()}",
        )
    return rows


async def _seed_history(
    hass: HomeAssistant, entry: MockConfigEntry, history: dict[str, list[float]]
) -> None:
    store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save(
        {
            "persons": {
                pid: {"history": values, "last_measurement": None}
                for pid, values in history.items()
            },
            "pending": [],
        }
    )


async def _start(hass: HomeAssistant, *entries: MockConfigEntry) -> None:
    for entry in entries:
        entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()
    # A scale that waited for the People entry retries on its own timer.
    for entry in entries:
        if entry.state.value != "loaded":
            await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


async def test_live_shape_one_scale_keeps_entities(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    """One scale, profile 'legacy': same registry rows, entity ids and history."""
    entry = _v2(ADDRESS, [LEGACY], **SETTINGS)
    entry.add_to_hass(hass)
    rows = _seed_registry(hass, entry, [LEGACY])
    await _seed_history(hass, entry, {"legacy": [80.0, 81.0, 82.0]})
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    person_device_id = rows["legacy_weight"].device_id

    await _start(hass, entry)

    people = find_people_entry(hass)
    assert people is not None
    assert people.options["persons"] == [LEGACY]
    assert people.options["tolerance_kg"] == 4.0
    assert entry.version == 3
    assert entry.options == {}

    # The scale's own rows are untouched.
    scale_weight = registry.async_get(rows["scale_weight"].entity_id)
    assert scale_weight.id == rows["scale_weight"].id
    assert scale_weight.unique_id == f"{ADDRESS}_weight"
    assert scale_weight.config_entry_id == entry.entry_id

    # Person rows keep id and entity_id, with the new owner and unique id.
    for key in PERSON_KEYS:
        moved = registry.async_get(rows[f"legacy_{key}"].entity_id)
        assert moved.id == rows[f"legacy_{key}"].id
        assert moved.unique_id == f"person_legacy_{key}"
        assert moved.config_entry_id == people.entry_id
        assert moved.device_id == person_device_id
    button = registry.async_get(rows["legacy_button"].entity_id)
    assert button.unique_id == "person_legacy_weighing_in"

    # The person device survives with a new identifier and no scale link.
    device = devices.async_get(person_device_id)
    assert device is not None
    assert (DOMAIN, "person:legacy") in device.identifiers
    assert device.via_device_id is None
    assert people.entry_id in device.config_entries
    assert entry.entry_id not in device.config_entries

    # No duplicate entities were created next to the migrated ones.
    ids = [e.entity_id for e in registry.entities.values() if e.platform == DOMAIN]
    assert not any(entity_id.endswith("_2") for entity_id in ids)
    for key in PERSON_KEYS:
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"person_legacy_{key}")
            == rows[f"legacy_{key}"].entity_id
        )

    hub = hass.data[HUB_KEY]
    assert hub.history["legacy"] == [80.0, 81.0, 82.0]
    assert hass.data[DOMAIN][entry.entry_id].hub is hub


async def test_migration_is_repeatable(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    """A second pass over already-moved rows changes nothing."""
    from custom_components.anko_scale.migration import async_adopt_legacy_scales

    entry = _v2(ADDRESS, [LEGACY])
    entry.add_to_hass(hass)
    rows = _seed_registry(hass, entry, [LEGACY])
    await _start(hass, entry)
    people = find_people_entry(hass)
    registry = er.async_get(hass)
    before = {k: registry.async_get(v.entity_id).unique_id for k, v in rows.items()}

    # Simulate a crash after the rows moved but before the options were cleared.
    hass.config_entries.async_update_entry(entry, options={"persons": [LEGACY]})
    await async_adopt_legacy_scales(hass, people)

    after = {k: registry.async_get(v.entity_id).unique_id for k, v in rows.items()}
    assert after == before
    assert entry.options == {}
    assert people.options["persons"] == [LEGACY]


async def test_two_scales_share_one_person(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    """Same-named people merge; each scale keeps exactly its former people."""
    alice = {**LEGACY, "profile_id": "alice", "display_name": "Alice"}
    bob = {**LEGACY, "profile_id": "bob", "display_name": "Bob"}
    bob_b = {**bob, "profile_id": "bobby"}  # same person, different id
    carol = {**LEGACY, "profile_id": "carol", "display_name": "Carol"}
    first = _v2(ADDRESS, [alice, bob])
    second = _v2(SECOND, [bob_b, carol])
    first.add_to_hass(hass)
    second.add_to_hass(hass)
    first_rows = _seed_registry(hass, first, [alice, bob])
    second_rows = _seed_registry(hass, second, [bob_b, carol])
    await _seed_history(hass, first, {"bob": [90.0]})
    await _seed_history(hass, second, {"bobby": [70.0], "carol": [60.0]})

    await _start(hass, first, second)

    people = find_people_entry(hass)
    assert [p["profile_id"] for p in people.options["persons"]] == [
        "alice",
        "bob",
        "carol",
    ]
    assert first.options == {"people": ["alice", "bob"]}
    assert second.options == {"people": ["bob", "carol"]}

    registry = er.async_get(hass)
    # Bob's rows from the first scale moved; the second scale's copies are gone.
    assert registry.async_get(first_rows["bob_weight"].entity_id).unique_id == (
        "person_bob_weight"
    )
    assert registry.async_get(second_rows["bobby_weight"].entity_id) is None
    assert registry.async_get(second_rows["carol_weight"].entity_id).unique_id == (
        "person_carol_weight"
    )
    uids = [
        e.unique_id
        for e in registry.entities.values()
        if e.platform == DOMAIN and e.unique_id.startswith("person_")
    ]
    assert len(uids) == len(set(uids))

    devices = dr.async_get(hass)
    assert (
        devices.async_get_device_by_identifier((DOMAIN, "person:bob"), people.entry_id)
        is not None
    )
    assert not any(
        identifier == (DOMAIN, f"{SECOND}:bobby")
        for device in devices.devices
        for identifier in device.identifiers
    )

    hub = hass.data[HUB_KEY]
    assert hub.history["bob"] == [90.0]  # first scale wins, not merged
    assert hub.history["carol"] == [60.0]


async def test_v1_entry_upgrades_through_to_people(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=ADDRESS,
        data={"address": ADDRESS},
        options={"height_cm": 175, "age": 41, "sex": "male"},
        title="IF_B7",
    )
    entry.add_to_hass(hass)
    rows = _seed_registry(hass, entry, [{**LEGACY, "height_cm": 175}])

    await _start(hass, entry)

    people = find_people_entry(hass)
    assert people.options["persons"] == [
        {
            "profile_id": "legacy",
            "display_name": "Person 1",
            "height_cm": 175,
            "age": 41,
            "sex": "male",
        }
    ]
    assert entry.version == 3
    registry = er.async_get(hass)
    assert registry.async_get(rows["scale_weight"].entity_id).unique_id == (
        f"{ADDRESS}_weight"
    )
    assert registry.async_get(rows["legacy_weight"].entity_id).unique_id == (
        "person_legacy_weight"
    )


async def test_migrated_scale_includes_people_added_later(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from custom_components.anko_scale.parser import ScaleReading

    entry = _v2(ADDRESS, [LEGACY])
    entry.add_to_hass(hass)
    _seed_registry(hass, entry, [LEGACY])
    await _seed_history(hass, entry, {"legacy": [82.0]})
    await _start(hass, entry)

    people = find_people_entry(hass)
    bob = {
        **LEGACY,
        "profile_id": "bob",
        "display_name": "Bob",
        "expected_weight_kg": 60.0,
    }
    hass.config_entries.async_update_entry(
        people, options={**people.options, "persons": [LEGACY, bob]}
    )
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    for i in range(3):
        coordinator.async_handle_reading(ScaleReading(60.5, 195, True), 100.0 + i)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.bob_weight").state == "60.5"
    assert coordinator.pending == []
