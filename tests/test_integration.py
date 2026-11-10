"""Integration-level tests: migration, settling, attribution, services."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.anko_scale.const import (
    DOMAIN,
    EVENT_PENDING,
    EVENT_WEIGH_IN,
    PEOPLE_UNIQUE_ID,
)
from custom_components.anko_scale.coordinator import AnkoScaleCoordinator
from custom_components.anko_scale.parser import ScaleReading
from custom_components.anko_scale.people import HUB_KEY, find_people_entry

from .conftest import ADDRESS

ALICE = {
    "profile_id": "alice",
    "display_name": "Alice",
    "height_cm": 165,
    "age": 34,
    "sex": "female",
    "expected_weight_kg": 60.0,
}
BOB = {
    "profile_id": "bob",
    "display_name": "Bob",
    "height_cm": 180,
    "age": 40,
    "sex": "male",
    "expected_weight_kg": 85.0,
}


_PEOPLE_FOR: dict[str, MockConfigEntry] = {}


def _people_entry(persons: list[dict], **extra) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=PEOPLE_UNIQUE_ID,
        data={"entry_type": "people"},
        options={"persons": persons, **extra},
        title="People",
    )


def _entry(
    persons: list[dict],
    scale_options: dict | None = None,
    address: str = ADDRESS,
    **people_extra,
) -> MockConfigEntry:
    """Return a scale entry; _setup adds the matching People entry first."""
    scale = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=address,
        data={"address": address},
        options=scale_options or {},
        title="IF_B7",
    )
    _PEOPLE_FOR[scale.entry_id] = _people_entry(persons, **people_extra)
    return scale


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> AnkoScaleCoordinator:
    people = _PEOPLE_FOR.pop(entry.entry_id, None)
    if people is not None:
        people.add_to_hass(hass)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


def _weigh(coordinator: AnkoScaleCoordinator, weight: float, t0: float = 100.0) -> None:
    """Feed three stable adverts one second apart."""
    for i in range(3):
        coordinator.async_handle_reading(ScaleReading(weight, 195, True), t0 + i)


async def test_two_persons_create_devices_and_entities(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    await _setup(hass, entry)
    people = find_people_entry(hass)

    devices = dr.async_get(hass)
    scale = devices.async_get_device_by_identifier((DOMAIN, ADDRESS), entry.entry_id)
    alice = devices.async_get_device_by_identifier(
        (DOMAIN, "person:alice"), people.entry_id
    )
    bob = devices.async_get_device_by_identifier(
        (DOMAIN, "person:bob"), people.entry_id
    )
    assert scale and alice and bob

    registry = er.async_get(hass)
    scale_ids = {
        e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    people_ids = {
        e.unique_id
        for e in er.async_entries_for_config_entry(registry, people.entry_id)
    }
    assert f"{ADDRESS}_weight" in scale_ids
    assert "person_alice_weight" in people_ids
    assert "person_bob_weight" in people_ids
    assert not any("alice" in uid for uid in scale_ids)
    assert hass.states.get("sensor.alice_weight") is not None
    assert hass.states.get("sensor.anko_body_scale_weight") is not None


async def test_weigh_in_single_event_and_person_sensors(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)

    _weigh(coordinator, 61.0)
    # Further stable adverts of the same weigh-in do not publish again.
    coordinator.async_handle_reading(ScaleReading(61.1, 195, True), 104.0)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["person_id"] == "alice"
    assert hass.states.get("sensor.alice_weight").state == "61.0"
    assert hass.states.get("sensor.bob_weight").state == "unavailable"
    assert hass.states.get("sensor.alice_body_fat").state not in (
        "unknown",
        "unavailable",
    )
    assert hass.states.get("sensor.anko_body_scale_last_person").state == "Alice"


async def test_unstable_frames_never_publish(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)

    for i, weight in enumerate((55.0, 58.0, 60.5)):
        coordinator.async_handle_reading(ScaleReading(weight, None, False), 100.0 + i)
    await hass.async_block_till_done()
    assert events == []
    assert hass.states.get("sensor.alice_weight").state == "unavailable"


async def test_single_final_frame_published_after_timeout(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)

    coordinator.async_handle_reading(ScaleReading(84.5, 190, True), 100.0)
    await hass.async_block_till_done()
    assert events == []

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["person_id"] == "bob"


async def test_ambiguous_creates_pending_then_assign(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    close = {**BOB, "expected_weight_kg": 61.0}
    entry = _entry([ALICE, close])
    coordinator = await _setup(hass, entry)
    weigh_ins, pendings = [], []
    hass.bus.async_listen(EVENT_WEIGH_IN, weigh_ins.append)
    hass.bus.async_listen(EVENT_PENDING, pendings.append)

    _weigh(coordinator, 60.5)
    await hass.async_block_till_done()

    assert weigh_ins == []
    assert len(pendings) == 1
    assert hass.states.get("sensor.alice_weight").state == "unavailable"
    assert hass.states.get("sensor.anko_body_scale_pending_measurements").state == "1"

    pending_id = pendings[0].data["pending_id"]
    await hass.services.async_call(
        DOMAIN,
        "assign_measurement",
        {"pending_id": pending_id, "person_id": "bob"},
        blocking=True,
    )
    assert len(weigh_ins) == 1
    assert weigh_ins[0].data["person_id"] == "bob"
    assert hass.states.get("sensor.bob_weight").state == "60.5"
    assert hass.states.get("sensor.anko_body_scale_pending_measurements").state == "0"


async def test_discard_creates_no_profile(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 120.0)
    assert len(coordinator.pending) == 1
    await hass.services.async_call(
        DOMAIN,
        "discard_measurement",
        {"pending_id": coordinator.pending[0].pending_id},
        blocking=True,
    )
    assert coordinator.pending == []
    assert [p.profile_id for p in coordinator.persons] == ["alice", "bob"]


async def test_set_next_person_is_one_shot(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)

    await hass.services.async_call(
        DOMAIN, "set_next_person", {"person_id": "bob"}, blocking=True
    )
    _weigh(coordinator, 61.0)  # Alice's weight, forced to Bob
    await hass.async_block_till_done()
    assert events[-1].data["person_id"] == "bob"

    _weigh(coordinator, 61.0, t0=200.0)  # override consumed
    await hass.async_block_till_done()
    assert events[-1].data["person_id"] == "alice"


async def test_not_home_person_not_auto_assigned(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    alice = {**ALICE, "person_entity": "person.alice"}
    entry = _entry([alice, BOB])
    coordinator = await _setup(hass, entry)
    hass.states.async_set("person.alice", "not_home")

    _weigh(coordinator, 60.0)
    assert len(coordinator.pending) == 1
    assert hass.states.get("sensor.alice_weight").state == "unavailable"


async def test_reassign_restores_previous_owner(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 60.0)
    _weigh(coordinator, 85.0, t0=200.0)
    await hass.services.async_call(
        DOMAIN, "reassign_measurement", {"person_id": "alice"}, blocking=True
    )
    hub = hass.data[HUB_KEY]
    assert hub.person_states["alice"].weight_kg == 85.0
    assert hub.person_states["bob"].weight_kg is None


async def test_unknown_person_raises(hass: HomeAssistant, mock_bluetooth: None) -> None:
    entry = _entry([ALICE, BOB])
    await _setup(hass, entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_next_person", {"person_id": "ghost"}, blocking=True
        )


async def test_state_survives_reload(hass: HomeAssistant, mock_bluetooth: None) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 62.0)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is not coordinator
    hub = hass.data[HUB_KEY]
    assert len(hub.history["alice"]) == 2  # seed + the weigh-in
    assert hub.last_measured["alice"] is not None


async def test_deleted_person_device_removed(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    await _setup(hass, entry)
    people = find_people_entry(hass)
    hass.config_entries.async_update_entry(people, options={"persons": [ALICE]})
    await hass.async_block_till_done()
    devices = dr.async_get(hass)
    assert (
        devices.async_get_device_by_identifier((DOMAIN, "person:bob"), people.entry_id)
        is None
    )
    assert (
        devices.async_get_device_by_identifier(
            (DOMAIN, "person:alice"), people.entry_id
        )
        is not None
    )
    assert hass.states.get("sensor.bob_weight") is None
    # The scale reloaded against the new hub and still works.
    assert hass.data[DOMAIN][entry.entry_id].hub is hass.data[HUB_KEY]


async def test_diagnostics_redacts(hass: HomeAssistant, mock_bluetooth: None) -> None:
    from custom_components.anko_scale.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _entry([ALICE, BOB], notify_service="notify.mobile_app_alices_phone")
    coordinator = await _setup(hass, entry)
    coordinator.last_raw_hex = f"0000:{ADDRESS.replace(':', '').lower()}0102"
    _weigh(coordinator, 61.0)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert ADDRESS not in text
    assert "Alice" not in text
    assert "alice" not in text.lower()
    assert "bob" not in text.lower()
    assert "alices_phone" not in text
    assert diag["counts"]["weigh_ins"] == 1
    assert diag["people_on_scale"] == "all"

    people_diag = await async_get_config_entry_diagnostics(
        hass, find_people_entry(hass)
    )
    people_text = str(people_diag)
    assert "alice" not in people_text.lower()
    assert "bob" not in people_text.lower()
    assert "alices_phone" not in people_text
    assert [p["index"] for p in people_diag["persons"]] == [0, 1]
    assert "history" not in people_text.replace("history_length", "")


async def test_fake_advert_stream_yields_one_weigh_in(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)

    stream = [
        (50.0, None, False),
        (58.0, None, False),
        (60.8, None, False),
        (60.9, 200, True),
        (61.3, 200, True),  # jitter inside the 0.5 kg spread
        (61.1, 199, True),
        (61.1, 199, True),
        (61.2, 199, True),
    ]
    for i, (weight, impedance, stable) in enumerate(stream):
        coordinator.async_handle_reading(
            ScaleReading(weight, impedance, stable), 300.0 + i * 0.5
        )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["person_id"] == "alice"
    assert 60.8 <= events[0].data["weight_kg"] <= 61.3


async def test_diagnostics_lists_recent_frames_redacted(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from types import SimpleNamespace

    from custom_components.anko_scale.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    addr = bytes.fromhex(ADDRESS.replace(":", ""))
    payload = (
        bytes([2, 3, 17]) + addr + bytes([2, 0x18, 0x0B, 0, 0x78, 0xA1, 0x9E, 0xDC])
    )
    info = SimpleNamespace(manufacturer_data={0x0100: payload}, rssi=-80)
    coordinator._async_handle_advertisement(info, None)
    coordinator._async_handle_advertisement(info, None)  # duplicate is skipped

    diag = await async_get_config_entry_diagnostics(hass, entry)
    frames = diag["recent_frames"]
    assert len(frames) == 1
    assert frames[0]["weight_kg"] == 61.55
    assert ADDRESS.replace(":", "").lower() not in frames[0]["hex"]
    assert "78a19edc" in frames[0]["hex"]


async def test_unknown_weight_raises_repair_and_flow_adds_person(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from homeassistant.helpers import issue_registry as ir

    from custom_components.anko_scale.repairs import async_create_fix_flow

    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 120.0)

    pending = coordinator.pending[0]
    assert pending.reason == "no_match"
    issue_id = f"unknown_weight_{pending.pending_id}"
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(DOMAIN, issue_id)
    assert issue is not None and issue.is_fixable
    assert coordinator.unknown_weight_count == 1

    flow = await async_create_fix_flow(hass, issue_id, issue.data)
    flow.hass = hass
    form = await flow.async_step_init()
    assert form["step_id"] == "person"
    assert form["description_placeholders"] == {"weight": "120.0"}
    suggested = {
        str(k): k.description["suggested_value"]
        for k in form["data_schema"].schema
        if k.description
    }
    assert suggested["expected_weight_kg"] == 120.0

    done = await flow.async_step_person(
        {"display_name": "Guest Two", "height_cm": 175, "sex": "male", "age": 40}
    )
    assert done["type"] == "create_entry"
    await hass.async_block_till_done()
    assert [p["profile_id"] for p in find_people_entry(hass).options["persons"]] == [
        "alice",
        "bob",
        "guest_two",
    ]
    assert issues.async_get_issue(DOMAIN, issue_id) is None


async def test_ambiguous_reading_raises_no_repair(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from homeassistant.helpers import issue_registry as ir

    close = {**BOB, "expected_weight_kg": 61.0}
    entry = _entry([ALICE, close])
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 60.5)
    assert coordinator.pending[0].reason == "ambiguous"
    assert not ir.async_get(hass).issues


async def test_single_person_bypass_raises_no_repair(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from homeassistant.helpers import issue_registry as ir

    entry = _entry([ALICE])
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 120.0)
    assert coordinator.pending == []
    assert not ir.async_get(hass).issues


async def test_capture_returns_weight_without_assigning(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)
    history_before = list(hass.data[HUB_KEY].history["alice"])

    task = hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            "capture_measurement",
            {"timeout": 30},
            blocking=True,
            return_response=True,
        )
    )
    for _ in range(100):
        if coordinator._capture is not None:
            break
        await asyncio.sleep(0)
    assert coordinator._capture is not None
    _weigh(coordinator, 61.0)  # would normally be Alice
    result = await task

    assert result["weight_kg"] == 61.0
    assert events == []
    assert hass.data[HUB_KEY].history["alice"] == history_before
    assert coordinator.pending == []

    _weigh(coordinator, 61.0, t0=200.0)  # capture is one-shot
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_capture_times_out_cleanly(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    with pytest.raises(ServiceValidationError):
        await coordinator.async_capture_measurement(0)
    # A later capture is not blocked by the failed one.
    assert coordinator._capture is None


async def test_no_foot_contact_weigh_in_uses_bmi_route(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)

    for i in range(3):
        coordinator.async_handle_reading(ScaleReading(61.0, None, True), 100.0 + i)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["impedance_raw"] is None
    state = hass.states.get("sensor.alice_body_fat")
    assert state.attributes["method"] == "bmi"


async def test_contact_weigh_in_uses_assumed_bia_route(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 61.0)  # raw code 195 -> assumed 499 ohm
    await hass.async_block_till_done()
    state = hass.states.get("sensor.alice_body_fat")
    assert state.attributes["method"] == "bia_assumed"


async def test_scale_body_sensors_are_removed(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB])
    _PEOPLE_FOR.pop(entry.entry_id).add_to_hass(hass)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for key in ("bmi", "body_fat_percent", "bmr"):
        registry.async_get_or_create(
            "sensor", DOMAIN, f"{ADDRESS}_{key}", config_entry=entry
        )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for key in ("bmi", "body_fat_percent", "bmr"):
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_{key}") is None
        )
    # The scale keeps weight, raw impedance, last person and pending count.
    for key in ("weight", "impedance", "last_person", "pending_count"):
        assert registry.async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_{key}")
    # Person sensors belong to the People entry.
    assert registry.async_get_entity_id("sensor", DOMAIN, "person_alice_bmi")


async def test_destructive_services_require_admin(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from homeassistant.core import Context
    from homeassistant.exceptions import Unauthorized

    from custom_components.anko_scale import SERVICE_DISCARD, SERVICE_RESET_HISTORY

    entry = _entry([ALICE, BOB])
    await _setup(hass, entry)
    await hass.auth.async_create_user("owner", group_ids=["system-admin"])
    user = await hass.auth.async_create_user("viewer", group_ids=["system-users"])
    assert not user.is_admin
    for service, data in (
        (SERVICE_DISCARD, {"pending_id": "x"}),
        (SERVICE_RESET_HISTORY, {"person_id": "alice"}),
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN, service, data, blocking=True, context=Context(user_id=user.id)
            )


SECOND = "11:22:33:44:55:66"


async def _add_scale(
    hass: HomeAssistant, address: str = SECOND, options: dict | None = None
) -> AnkoScaleCoordinator:
    scale = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=address,
        data={"address": address},
        options=options or {},
        title="IF_B7",
    )
    scale.add_to_hass(hass)
    assert await hass.config_entries.async_setup(scale.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][scale.entry_id]


async def test_two_scales_update_the_same_person(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    first = await _setup(hass, _entry([ALICE, BOB]))
    second = await _add_scale(hass)
    hub = hass.data[HUB_KEY]
    assert first.hub is hub and second.hub is hub

    _weigh(first, 61.0)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.alice_weight").state == "61.0"

    # The same person on the other scale updates the same sensor and history.
    _weigh(second, 62.0, t0=200.0)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.alice_weight").state == "62.0"
    assert len(hub.history["alice"]) == 3  # seed + one reading per scale

    _weigh(second, 85.0, t0=300.0)
    await hass.async_block_till_done()
    assert first.last_person == "Alice"
    assert second.last_person == "Bob"
    assert hass.states.get("sensor.alice_weight").state == "62.0"
    assert hass.states.get("sensor.bob_weight").state == "85.0"


async def test_scale_allowlist_limits_attribution(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    await _setup(hass, _entry([ALICE, BOB]))
    bob_only = await _add_scale(hass, options={"people": ["bob"]})
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)

    assert [p.profile_id for p in bob_only.persons] == ["bob"]
    # 61 kg is Alice's weight, but Alice is not allowed on this scale.
    _weigh(bob_only, 61.0)
    await hass.async_block_till_done()
    assert events[-1].data["person_id"] == "bob"
    assert events[-1].data["source"] == "single_person"
    assert bob_only.pending == []


async def test_new_person_joins_scales_without_a_list(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    all_scale = await _setup(hass, _entry([ALICE]))
    listed = await _add_scale(hass, options={"people": ["alice"]})
    people = find_people_entry(hass)
    hass.config_entries.async_update_entry(people, options={"persons": [ALICE, BOB]})
    await hass.async_block_till_done()

    scales = hass.data[DOMAIN]
    assert [p.profile_id for p in scales[all_scale.entry.entry_id].persons] == [
        "alice",
        "bob",
    ]
    assert [p.profile_id for p in scales[listed.entry.entry_id].persons] == ["alice"]


async def test_weighing_in_button_arms_scales_that_allow_the_person(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    everyone = await _setup(hass, _entry([ALICE, BOB]))
    bob_only = await _add_scale(hass, options={"people": ["bob"]})

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.alice_weighing_in"}, blocking=True
    )
    assert everyone.next_person == "alice"
    assert bob_only.next_person is None

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.bob_weighing_in"}, blocking=True
    )
    assert everyone.next_person == "bob"
    assert bob_only.next_person == "bob"


async def test_button_fails_when_no_scale_allows_the_person(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry([ALICE, BOB], {"people": ["bob"]})
    await _setup(hass, entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.alice_weighing_in"}, blocking=True
        )


async def test_people_services_need_no_entry_id_with_two_scales(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    first = await _setup(hass, _entry([ALICE, BOB]))
    await _add_scale(hass)
    hub = hass.data[HUB_KEY]
    _weigh(first, 61.0)
    _weigh(first, 85.0, t0=200.0)

    await hass.services.async_call(
        DOMAIN, "reassign_measurement", {"person_id": "alice"}, blocking=True
    )
    assert hub.person_states["alice"].weight_kg == 85.0
    await hass.services.async_call(
        DOMAIN, "reset_person_history", {"person_id": "alice"}, blocking=True
    )
    assert hub.history["alice"] == [60.0]

    # Scale actions still need to know which scale.
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_next_person", {"person_id": "bob"}, blocking=True
        )
    await hass.services.async_call(
        DOMAIN,
        "set_next_person",
        {"person_id": "bob", "config_entry_id": first.entry.entry_id},
        blocking=True,
    )
    assert first.next_person == "bob"


async def test_scale_without_people_entry_waits(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    scale = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=ADDRESS,
        data={"address": ADDRESS},
        options={},
    )
    scale.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(scale.entry_id)
    assert scale.state.value == "setup_retry"


async def test_people_reload_rebinds_scales(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    coordinator = await _setup(hass, _entry([ALICE, BOB]))
    people = find_people_entry(hass)
    old_hub = hass.data[HUB_KEY]

    assert await hass.config_entries.async_reload(people.entry_id)
    await hass.async_block_till_done()

    new_hub = hass.data[HUB_KEY]
    assert new_hub is not old_hub
    scale = hass.data[DOMAIN][coordinator.entry.entry_id]
    assert scale.hub is new_hub
    _weigh(scale, 61.0)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.alice_weight").state == "61.0"


async def test_new_person_after_migration_style_scale_is_matched(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    """A scale with no list picks up people added later."""
    coordinator = await _setup(hass, _entry([ALICE]))
    people = find_people_entry(hass)
    hass.config_entries.async_update_entry(people, options={"persons": [ALICE, BOB]})
    await hass.async_block_till_done()
    scale = hass.data[DOMAIN][coordinator.entry.entry_id]
    _weigh(scale, 85.0)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.bob_weight").state == "85.0"


async def test_repair_adds_person_to_an_explicit_scale_list(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from homeassistant.helpers import issue_registry as ir

    from custom_components.anko_scale.repairs import async_create_fix_flow

    entry = _entry([ALICE, BOB], {"people": ["alice", "bob"]})
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 120.0)
    pending = coordinator.pending[0]
    issue_id = f"unknown_weight_{pending.pending_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)

    flow = await async_create_fix_flow(hass, issue_id, issue.data)
    flow.hass = hass
    done = await flow.async_step_person(
        {"display_name": "Guest Two", "height_cm": 175, "sex": "male", "age": 40}
    )
    assert done["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.options == {"people": ["alice", "bob", "guest_two"]}
    scale = hass.data[DOMAIN][entry.entry_id]
    assert [p.profile_id for p in scale.persons] == ["alice", "bob", "guest_two"]
