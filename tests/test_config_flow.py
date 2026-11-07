"""Tests for the config and options flows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.anko_scale.const import DOMAIN

from .conftest import ADDRESS

PERSON_INPUT = {
    "display_name": "Jupiter",
    "height_cm": 180,
    "sex": "male",
    "age": 38,
}


async def test_user_flow_creates_v2_entry(hass: HomeAssistant) -> None:
    info = SimpleNamespace(address=ADDRESS, name="IF_B7")
    with patch(
        "custom_components.anko_scale.config_flow.async_discovered_service_info",
        return_value=[info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"address": ADDRESS}
        )
    assert result["step_id"] == "profile"
    with patch("custom_components.anko_scale.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PERSON_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"address": ADDRESS}
    person = result["options"]["persons"][0]
    assert person["profile_id"] == "jupiter"
    assert person["height_cm"] == 180
    assert result["options"]["margin_kg"] == 2.0
    assert result["version"] == 2


async def test_user_flow_aborts_without_devices(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.anko_scale.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=ADDRESS,
        data={"address": ADDRESS},
        options={
            "persons": [
                {
                    "profile_id": "jupiter",
                    "display_name": "Jupiter",
                    "height_cm": 180,
                    "age": 38,
                    "sex": "male",
                }
            ]
        },
    )
    entry.add_to_hass(hass)
    return entry


async def _menu(hass: HomeAssistant, entry: MockConfigEntry, choice: str) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": choice}
    )


async def test_options_add_person(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    result = await _menu(hass, entry, "add_person")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**PERSON_INPUT, "display_name": "Sarah", "sex": "female", "age": 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    ids = [p["profile_id"] for p in result["data"]["persons"]]
    assert ids == ["jupiter", "sarah"]


async def test_options_duplicate_name_rejected(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    result = await _menu(hass, entry, "add_person")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], PERSON_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"display_name": "name_exists"}


async def test_options_edit_keeps_profile_id(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    result = await _menu(hass, entry, "edit_person")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"profile_id": "jupiter"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**PERSON_INPUT, "display_name": "Jupe", "height_cm": 181}
    )
    person = result["data"]["persons"][0]
    assert person["profile_id"] == "jupiter"
    assert person["display_name"] == "Jupe"
    assert person["height_cm"] == 181


async def test_options_cannot_delete_last_person(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "delete_person" not in result["menu_options"]


async def test_options_delete_person(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    entry_options = {
        "persons": [
            *entry.options["persons"],
            {
                "profile_id": "sarah",
                "display_name": "Sarah",
                "height_cm": 165,
                "age": 35,
                "sex": "female",
            },
        ]
    }
    hass.config_entries.async_update_entry(entry, options=entry_options)
    result = await _menu(hass, entry, "delete_person")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"profile_id": "sarah"}
    )
    assert [p["profile_id"] for p in result["data"]["persons"]] == ["jupiter"]


async def test_options_settings(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    result = await _menu(hass, entry, "settings")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "tolerance_kg": 4,
            "tolerance_pct": 6,
            "margin_kg": 3,
            "history_size": 20,
            "pending_timeout_min": 30,
            "notify_service": "notify.mobile_app_phone",
        },
    )
    assert result["data"]["history_size"] == 20
    assert result["data"]["notify_service"] == "notify.mobile_app_phone"
    assert len(result["data"]["persons"]) == 1


async def test_birth_date_typed_and_validated(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    result = await _menu(hass, entry, "add_person")
    bad = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**PERSON_INPUT, "display_name": "Sarah", "birth_date": "27/03/1985"},
    )
    assert bad["errors"] == {"birth_date": "invalid_birth_date"}
    good = await hass.config_entries.options.async_configure(
        bad["flow_id"],
        {**PERSON_INPUT, "display_name": "Sarah", "birth_date": "1985-03-27"},
    )
    assert good["data"]["persons"][1]["birth_date"] == "1985-03-27"
