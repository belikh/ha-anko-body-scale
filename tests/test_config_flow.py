"""Tests for the config and options flows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.anko_scale.const import DOMAIN, PEOPLE_UNIQUE_ID
from custom_components.anko_scale.people import find_people_entry

from .conftest import ADDRESS

PERSON_INPUT = {
    "display_name": "Jupiter",
    "height_cm": 180,
    "sex": "male",
    "age": 38,
}


async def test_first_scale_creates_people_entry_and_scale(
    hass: HomeAssistant,
) -> None:
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
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"address": ADDRESS}
    assert result["options"] == {}
    assert result["version"] == 3

    people = find_people_entry(hass)
    assert people is not None
    assert people.data == {"entry_type": "people"}
    person = people.options["persons"][0]
    assert person["profile_id"] == "jupiter"
    assert person["height_cm"] == 180
    assert people.options["margin_kg"] == 2.0


async def test_second_scale_asks_who_uses_it(hass: HomeAssistant) -> None:
    _people(hass, [JUPITER, SARAH])
    second = "11:22:33:44:55:66"
    info = SimpleNamespace(address=second, name="IF_B7")
    with patch(
        "custom_components.anko_scale.config_flow.async_discovered_service_info",
        return_value=[info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"address": second}
        )
    assert result["step_id"] == "people"
    with patch("custom_components.anko_scale.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"people": ["sarah"]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {"people": ["sarah"]}


async def test_second_scale_with_everyone_stores_no_list(
    hass: HomeAssistant,
) -> None:
    _people(hass, [JUPITER, SARAH])
    second = "11:22:33:44:55:66"
    info = SimpleNamespace(address=second, name="IF_B7")
    with patch(
        "custom_components.anko_scale.config_flow.async_discovered_service_info",
        return_value=[info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"address": second}
        )
    with patch("custom_components.anko_scale.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"people": ["jupiter", "sarah"]}
        )
    assert result["options"] == {}


async def test_second_scale_with_one_person_skips_the_question(
    hass: HomeAssistant,
) -> None:
    _people(hass, [JUPITER])
    second = "11:22:33:44:55:66"
    info = SimpleNamespace(address=second, name="IF_B7")
    with (
        patch(
            "custom_components.anko_scale.config_flow.async_discovered_service_info",
            return_value=[info],
        ),
        patch("custom_components.anko_scale.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"address": second}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {}


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


JUPITER = {
    "profile_id": "jupiter",
    "display_name": "Jupiter",
    "height_cm": 180,
    "age": 38,
    "sex": "male",
}
SARAH = {
    "profile_id": "sarah",
    "display_name": "Sarah",
    "height_cm": 165,
    "age": 35,
    "sex": "female",
}


def _people(hass: HomeAssistant, persons: list[dict]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=PEOPLE_UNIQUE_ID,
        data={"entry_type": "people"},
        options={"persons": persons},
        title="People",
    )
    entry.add_to_hass(hass)
    return entry


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    return _people(hass, [JUPITER])


def _scale(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=ADDRESS,
        data={"address": ADDRESS},
        options=options or {},
        title="IF_B7",
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


async def test_birth_date_or_age_required(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    result = await _menu(hass, entry, "add_person")
    no_age = {k: v for k, v in PERSON_INPUT.items() if k != "age"}
    bad = await hass.config_entries.options.async_configure(
        result["flow_id"], {**no_age, "display_name": "Sarah"}
    )
    assert bad["errors"] == {"birth_date": "birth_date_or_age"}
    good = await hass.config_entries.options.async_configure(
        bad["flow_id"],
        {**no_age, "display_name": "Sarah", "birth_date": "1985-03-27"},
    )
    person = good["data"]["persons"][1]
    assert "age" not in person
    assert person["birth_date"] == "1985-03-27"


async def test_bluetooth_discovery_asks_for_confirmation(hass: HomeAssistant) -> None:
    from custom_components.anko_scale.config_flow import AnkoScaleConfigFlow

    flow = AnkoScaleConfigFlow()
    flow.hass = hass
    flow.context = {"source": "bluetooth"}
    result = await flow.async_step_bluetooth(
        SimpleNamespace(address=ADDRESS, name="IF_B7")
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    result = await flow.async_step_bluetooth_confirm({})
    assert result["step_id"] == "profile"


async def test_options_add_from_home_assistant_person(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    hass.states.async_set("person.sarah", "home", {"friendly_name": "Sarah"})
    result = await _menu(hass, entry, "add_from_person")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"person_entity": "person.sarah"}
    )
    assert result["step_id"] == "add_person"
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["display_name"].default() == "Sarah"
    assert schema["person_entity"].description["suggested_value"] == "person.sarah"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "display_name": "Sarah",
            "height_cm": 165,
            "sex": "female",
            "age": 35,
            "person_entity": "person.sarah",
        },
    )
    added = result["data"]["persons"][1]
    assert added["profile_id"] == "sarah"
    assert added["person_entity"] == "person.sarah"


async def test_scale_options_pick_people(hass: HomeAssistant) -> None:
    _people(hass, [JUPITER, SARAH])
    scale = _scale(hass)
    result = await hass.config_entries.options.async_init(scale.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scale_people"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"people": ["sarah"]}
    )
    assert result["data"] == {"people": ["sarah"]}

    # Selecting everyone clears the list, so later additions are included.
    hass.config_entries.async_update_entry(scale, options={"people": ["sarah"]})
    result = await hass.config_entries.options.async_init(scale.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"people": ["jupiter", "sarah"]}
    )
    assert result["data"] == {}


async def test_scale_options_require_a_person(hass: HomeAssistant) -> None:
    _people(hass, [JUPITER, SARAH])
    scale = _scale(hass)
    result = await hass.config_entries.options.async_init(scale.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"people": []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"people": "people_required"}


async def test_deleting_a_person_clears_scale_allowlists(
    hass: HomeAssistant,
) -> None:
    people = _people(hass, [JUPITER, SARAH])
    both = _scale(hass, {"people": ["jupiter", "sarah"]})
    only_sarah = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="11:22:33:44:55:66",
        data={"address": "11:22:33:44:55:66"},
        options={"people": ["sarah"]},
    )
    only_sarah.add_to_hass(hass)
    result = await _menu(hass, people, "delete_person")
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"profile_id": "sarah"}
    )
    assert both.options == {"people": ["jupiter"]}
    assert only_sarah.options == {"people": []}


async def test_second_scale_requires_a_person(hass: HomeAssistant) -> None:
    _people(hass, [JUPITER, SARAH])
    second = "11:22:33:44:55:66"
    info = SimpleNamespace(address=second, name="IF_B7")
    with patch(
        "custom_components.anko_scale.config_flow.async_discovered_service_info",
        return_value=[info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"address": second}
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"people": []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"people": "people_required"}
