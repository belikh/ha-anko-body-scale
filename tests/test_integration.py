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

from custom_components.anko_scale.const import DOMAIN, EVENT_PENDING, EVENT_WEIGH_IN
from custom_components.anko_scale.coordinator import AnkoScaleCoordinator
from custom_components.anko_scale.parser import ScaleReading

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


def _entry(version: int, options: dict) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=version,
        unique_id=ADDRESS,
        data={"address": ADDRESS},
        options=options,
        title="IF_B7",
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> AnkoScaleCoordinator:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


def _weigh(coordinator: AnkoScaleCoordinator, weight: float, t0: float = 100.0) -> None:
    """Feed three stable adverts one second apart."""
    for i in range(3):
        coordinator.async_handle_reading(ScaleReading(weight, 195, True), t0 + i)


async def test_migration_v1_to_v2_keeps_entities(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(1, {"height_cm": 175, "age": 41, "sex": "male"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{ADDRESS}_weight",
        config_entry=entry,
        suggested_object_id="anko_body_scale_weight",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data == {"address": ADDRESS}
    assert entry.unique_id == ADDRESS
    persons = entry.options["persons"]
    assert persons == [
        {
            "profile_id": "legacy",
            "display_name": "Person 1",
            "height_cm": 175,
            "age": 41,
            "sex": "male",
        }
    ]
    assert registry.async_get("sensor.anko_body_scale_weight") is not None
    assert registry.async_get("sensor.anko_body_scale_weight").id == old.id
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_weight")


async def test_two_persons_create_devices_and_entities(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
    await _setup(hass, entry)

    devices = dr.async_get(hass)
    scale = devices.async_get_device_by_identifier((DOMAIN, ADDRESS), entry.entry_id)
    alice = devices.async_get_device_by_identifier(
        (DOMAIN, f"{ADDRESS}:alice"), entry.entry_id
    )
    bob = devices.async_get_device_by_identifier(
        (DOMAIN, f"{ADDRESS}:bob"), entry.entry_id
    )
    assert scale and alice and bob
    assert alice.via_device_id == scale.id
    assert bob.via_device_id == scale.id

    registry = er.async_get(hass)
    unique_ids = [
        e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    ]
    assert len(unique_ids) == len(set(unique_ids))
    assert f"{ADDRESS}_weight" in unique_ids
    assert f"{ADDRESS}_alice_weight" in unique_ids
    assert f"{ADDRESS}_bob_weight" in unique_ids
    assert hass.states.get("sensor.alice_weight") is not None
    assert hass.states.get("sensor.anko_body_scale_weight") is not None


async def test_weigh_in_single_event_and_person_sensors(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    entry = _entry(2, {"persons": [ALICE, close]})
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
    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    entry = _entry(2, {"persons": [alice, BOB]})
    coordinator = await _setup(hass, entry)
    hass.states.async_set("person.alice", "not_home")

    _weigh(coordinator, 60.0)
    assert len(coordinator.pending) == 1
    assert hass.states.get("sensor.alice_weight").state == "unavailable"


async def test_reassign_restores_previous_owner(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 60.0)
    _weigh(coordinator, 85.0, t0=200.0)
    await hass.services.async_call(
        DOMAIN, "reassign_measurement", {"person_id": "alice"}, blocking=True
    )
    assert coordinator.person_states["alice"].weight_kg == 85.0
    assert coordinator.person_states["bob"].weight_kg is None


async def test_unknown_person_raises(hass: HomeAssistant, mock_bluetooth: None) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
    await _setup(hass, entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_next_person", {"person_id": "ghost"}, blocking=True
        )


async def test_state_survives_reload(hass: HomeAssistant, mock_bluetooth: None) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 62.0)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    reloaded = hass.data[DOMAIN][entry.entry_id]
    assert reloaded is not coordinator
    assert len(reloaded.history["alice"]) == 2  # seed + the weigh-in
    assert reloaded.last_measured["alice"] is not None


async def test_deleted_person_device_removed(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
    await _setup(hass, entry)
    hass.config_entries.async_update_entry(entry, options={"persons": [ALICE]})
    await hass.async_block_till_done()
    devices = dr.async_get(hass)
    assert (
        devices.async_get_device_by_identifier(
            (DOMAIN, f"{ADDRESS}:bob"), entry.entry_id
        )
        is None
    )
    assert (
        devices.async_get_device_by_identifier(
            (DOMAIN, f"{ADDRESS}:alice"), entry.entry_id
        )
        is not None
    )
    assert hass.states.get("sensor.bob_weight") is None


async def test_diagnostics_redacts(hass: HomeAssistant, mock_bluetooth: None) -> None:
    from custom_components.anko_scale.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _entry(2, {"persons": [ALICE, BOB]})
    coordinator = await _setup(hass, entry)
    coordinator.last_raw_hex = f"0000:{ADDRESS.replace(':', '').lower()}0102"
    _weigh(coordinator, 61.0)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert ADDRESS not in text
    assert "Alice" not in text
    assert "history" not in text.replace("history_length", "")
    assert diag["counts"]["weigh_ins"] == 1


async def test_fake_advert_stream_yields_one_weigh_in(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
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

    entry = _entry(2, {"persons": [ALICE, BOB]})
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

    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    assert [p["profile_id"] for p in entry.options["persons"]] == [
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
    entry = _entry(2, {"persons": [ALICE, close]})
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 60.5)
    assert coordinator.pending[0].reason == "ambiguous"
    assert not ir.async_get(hass).issues


async def test_single_person_bypass_raises_no_repair(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    from homeassistant.helpers import issue_registry as ir

    entry = _entry(2, {"persons": [ALICE]})
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 120.0)
    assert coordinator.pending == []
    assert not ir.async_get(hass).issues


async def test_capture_returns_weight_without_assigning(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
    coordinator = await _setup(hass, entry)
    events = []
    hass.bus.async_listen(EVENT_WEIGH_IN, events.append)
    history_before = list(coordinator.history["alice"])

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
    assert coordinator.history["alice"] == history_before
    assert coordinator.pending == []

    _weigh(coordinator, 61.0, t0=200.0)  # capture is one-shot
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_capture_times_out_cleanly(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
    coordinator = await _setup(hass, entry)
    with pytest.raises(ServiceValidationError):
        await coordinator.async_capture_measurement(0)
    # A later capture is not blocked by the failed one.
    assert coordinator._capture is None


async def test_no_foot_contact_weigh_in_uses_bmi_route(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    entry = _entry(2, {"persons": [ALICE, BOB]})
    coordinator = await _setup(hass, entry)
    _weigh(coordinator, 61.0)  # raw code 195 -> assumed 499 ohm
    await hass.async_block_till_done()
    state = hass.states.get("sensor.alice_body_fat")
    assert state.attributes["method"] == "bia_assumed"


async def test_scale_body_sensors_are_removed(
    hass: HomeAssistant, mock_bluetooth: None
) -> None:
    entry = _entry(2, {"persons": [ALICE, BOB]})
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
    # Person sensors are untouched.
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_alice_bmi")
