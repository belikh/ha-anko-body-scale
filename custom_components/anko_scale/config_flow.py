"""Config flow for the ANKO Body Scale integration."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .attribution import is_valid_profile_id
from .const import (
    CONF_ADDRESS,
    CONF_AGE,
    CONF_BIRTH_DATE,
    CONF_DISPLAY_NAME,
    CONF_ENTRY_TYPE,
    CONF_EXPECTED_WEIGHT,
    CONF_HEIGHT_CM,
    CONF_HISTORY_SIZE,
    CONF_MARGIN_KG,
    CONF_NOTIFY_SERVICE,
    CONF_PENDING_TIMEOUT,
    CONF_PEOPLE,
    CONF_PERSON_ENTITY,
    CONF_PERSONS,
    CONF_PROFILE_ID,
    CONF_SEX,
    CONF_TOLERANCE_KG,
    CONF_TOLERANCE_PCT,
    DEFAULT_HEIGHT_CM,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_MARGIN_KG,
    DEFAULT_PENDING_TIMEOUT_MIN,
    DEFAULT_PERSON_NAME,
    DEFAULT_SEX,
    DEFAULT_TOLERANCE_KG,
    DEFAULT_TOLERANCE_PCT,
    DOMAIN,
    ENTRY_TYPE_PEOPLE,
    PEOPLE_TITLE,
    PEOPLE_UNIQUE_ID,
    SEX_FEMALE,
    SEX_MALE,
)
from .parser import LOCAL_NAME
from .people import find_people_entry, is_people_entry

_OPTIONAL_PERSON_KEYS = (
    CONF_BIRTH_DATE,
    CONF_PERSON_ENTITY,
    CONF_EXPECTED_WEIGHT,
)


def _optional(key: str, current: dict[str, Any]) -> vol.Optional:
    """Return an Optional key that pre-fills from the stored value."""
    if current.get(key) not in (None, ""):
        return vol.Optional(key, description={"suggested_value": current[key]})
    return vol.Optional(key)


def _number(minimum: float, maximum: float, step: float = 1) -> Any:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def person_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Return the add/edit-person form schema."""
    current = current or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_DISPLAY_NAME, default=current.get(CONF_DISPLAY_NAME, "")
            ): selector.TextSelector(),
            vol.Required(
                CONF_HEIGHT_CM, default=current.get(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM)
            ): _number(100, 250),
            vol.Required(
                CONF_SEX, default=current.get(CONF_SEX, DEFAULT_SEX)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[SEX_MALE, SEX_FEMALE],
                    translation_key="sex",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            _optional(CONF_BIRTH_DATE, current): selector.TextSelector(),
            _optional(CONF_AGE, current): _number(5, 120),
            _optional(CONF_PERSON_ENTITY, current): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="person")
            ),
            _optional(CONF_EXPECTED_WEIGHT, current): _number(10, 300, 0.1),
        }
    )


def clean_person(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise form input: ints for whole numbers, drop empty optionals."""
    person = dict(user_input)
    person[CONF_DISPLAY_NAME] = person[CONF_DISPLAY_NAME].strip()
    person[CONF_HEIGHT_CM] = int(person[CONF_HEIGHT_CM])
    if person.get(CONF_AGE) not in (None, ""):
        person[CONF_AGE] = int(person[CONF_AGE])
    else:
        person.pop(CONF_AGE, None)
    for key in _OPTIONAL_PERSON_KEYS:
        if person.get(key) in (None, ""):
            person.pop(key, None)
    return person


def validate_person(
    person: dict[str, Any], others: list[dict[str, Any]]
) -> dict[str, str]:
    """Return form errors for a person (empty when valid)."""
    errors: dict[str, str] = {}
    name = person[CONF_DISPLAY_NAME]
    if not name:
        errors[CONF_DISPLAY_NAME] = "name_required"
    elif name.casefold() in {o[CONF_DISPLAY_NAME].casefold() for o in others}:
        errors[CONF_DISPLAY_NAME] = "name_exists"
    raw_birth = person.get(CONF_BIRTH_DATE)
    if not raw_birth and CONF_AGE not in person:
        errors[CONF_BIRTH_DATE] = "birth_date_or_age"
    if raw_birth:
        try:
            parsed = date.fromisoformat(str(raw_birth).strip())
        except ValueError:
            errors[CONF_BIRTH_DATE] = "invalid_birth_date"
        else:
            if parsed >= date.today():
                errors[CONF_BIRTH_DATE] = "invalid_birth_date"
            else:
                person[CONF_BIRTH_DATE] = parsed.isoformat()
    return errors


def new_profile_id(name: str, existing: list[dict[str, Any]]) -> str:
    """Return a unique lowercase slug for a new person."""
    base = slugify(name) or "person"
    taken = {p[CONF_PROFILE_ID] for p in existing}
    candidate, n = base, 2
    while candidate in taken or not is_valid_profile_id(candidate):
        candidate = f"{base}_{n}"
        n += 1
    return candidate


def default_settings() -> dict[str, Any]:
    """Return the default attribution settings."""
    return {
        CONF_TOLERANCE_KG: DEFAULT_TOLERANCE_KG,
        CONF_TOLERANCE_PCT: DEFAULT_TOLERANCE_PCT,
        CONF_MARGIN_KG: DEFAULT_MARGIN_KG,
        CONF_HISTORY_SIZE: DEFAULT_HISTORY_SIZE,
        CONF_PENDING_TIMEOUT: DEFAULT_PENDING_TIMEOUT_MIN,
    }


def people_options(entry: ConfigEntry | None) -> list[dict[str, Any]]:
    """Return the people stored in the People entry."""
    if entry is None:
        return []
    return [dict(p) for p in entry.options.get(CONF_PERSONS, [])]


class AnkoScaleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the ANKO Body Scale."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._address: str | None = None
        self._title: str = "ANKO Body Scale"

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Create the People entry (used by the first-scale flow and upgrades)."""
        await self.async_set_unique_id(PEOPLE_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=PEOPLE_TITLE,
            data={CONF_ENTRY_TYPE: ENTRY_TYPE_PEOPLE},
            options=import_data,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a scale discovered by the Bluetooth integration."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._title = discovery_info.name or self._title
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask before adding a discovered scale (it may be a neighbour's)."""
        if user_input is not None:
            return await self._async_after_scale_chosen()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._title},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup by picking a previously seen scale."""
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(self._address)
            self._abort_if_unique_id_configured()
            return await self._async_after_scale_chosen()

        current_addresses = self._async_current_ids()
        discovered = {
            info.address: info.name or info.address
            for info in async_discovered_service_info(self.hass)
            if info.name == LOCAL_NAME and info.address not in current_addresses
        }
        if not discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(discovered)}),
        )

    async def _async_after_scale_chosen(self) -> ConfigFlowResult:
        """Ask for the first person, or who uses this scale if people exist."""
        persons = people_options(find_people_entry(self.hass))
        if not persons:
            return await self.async_step_profile()
        if len(persons) > 1:
            return await self.async_step_people()
        return self._create_scale_entry(None)

    def _create_scale_entry(self, allowed: list[str] | None) -> ConfigFlowResult:
        options = {} if allowed is None else {CONF_PEOPLE: allowed}
        return self.async_create_entry(
            title=self._title, data={CONF_ADDRESS: self._address}, options=options
        )

    async def async_step_people(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which people use this scale (everyone by default)."""
        persons = people_options(find_people_entry(self.hass))
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = list(user_input[CONF_PEOPLE])
            all_ids = [p[CONF_PROFILE_ID] for p in persons]
            if not chosen:
                errors[CONF_PEOPLE] = "people_required"
            else:
                return self._create_scale_entry(
                    None if set(chosen) == set(all_ids) else chosen
                )
        return self.async_show_form(
            step_id="people",
            data_schema=people_schema(persons, None),
            errors=errors,
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the first person. More can be added later in Configure."""
        errors: dict[str, str] = {}
        if user_input is not None:
            person = clean_person(user_input)
            errors = validate_person(person, [])
            if not errors:
                person[CONF_PROFILE_ID] = new_profile_id(person[CONF_DISPLAY_NAME], [])
                await self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={CONF_PERSONS: [person], **default_settings()},
                )
                return self._create_scale_entry(None)

        return self.async_show_form(
            step_id="profile",
            data_schema=person_schema(
                user_input or {CONF_DISPLAY_NAME: DEFAULT_PERSON_NAME}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AnkoPeopleOptionsFlow | AnkoScaleOptionsFlow:
        """Return the People options flow or the per-scale one."""
        if is_people_entry(config_entry):
            return AnkoPeopleOptionsFlow()
        return AnkoScaleOptionsFlow()


def people_schema(
    persons: list[dict[str, Any]], selected: list[str] | None
) -> vol.Schema:
    """Return the form that picks which people use a scale."""
    options = [
        selector.SelectOptionDict(value=p[CONF_PROFILE_ID], label=p[CONF_DISPLAY_NAME])
        for p in persons
    ]
    default = (
        [p[CONF_PROFILE_ID] for p in persons] if selected is None else list(selected)
    )
    return vol.Schema(
        {
            vol.Required(CONF_PEOPLE, default=default): selector.SelectSelector(
                selector.SelectSelectorConfig(options=options, multiple=True)
            )
        }
    )


class AnkoScaleOptionsFlow(OptionsFlow):
    """Choose which people use this scale."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the only step (options flows must begin at init)."""
        return await self.async_step_scale_people()

    async def async_step_scale_people(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the people; selecting everyone stores no list."""
        persons = people_options(find_people_entry(self.hass))
        all_ids = [p[CONF_PROFILE_ID] for p in persons]
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = [pid for pid in user_input[CONF_PEOPLE] if pid in all_ids]
            if not chosen:
                errors[CONF_PEOPLE] = "people_required"
            else:
                options = {
                    k: v
                    for k, v in self.config_entry.options.items()
                    if k != CONF_PEOPLE
                }
                if set(chosen) != set(all_ids):
                    options[CONF_PEOPLE] = chosen
                return self.async_create_entry(data=options)
        current = self.config_entry.options.get(CONF_PEOPLE)
        return self.async_show_form(
            step_id="scale_people",
            data_schema=people_schema(persons, current),
            errors=errors,
        )


class AnkoPeopleOptionsFlow(OptionsFlow):
    """Add, edit and delete people; tune attribution."""

    def __init__(self) -> None:
        """Initialise the options flow."""
        self._edit_id: str | None = None
        self._prefill: dict[str, Any] = {}

    @property
    def _persons(self) -> list[dict[str, Any]]:
        return [dict(p) for p in self.config_entry.options.get(CONF_PERSONS, [])]

    def _save(self, persons: list[dict[str, Any]]) -> ConfigFlowResult:
        options = {**self.config_entry.options, CONF_PERSONS: persons}
        return self.async_create_entry(data=options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options menu."""
        menu = ["add_person", "add_from_person", "edit_person"]
        if len(self._persons) > 1:
            menu.append("delete_person")
        menu.append("settings")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add_person(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a person."""
        persons = self._persons
        errors: dict[str, str] = {}
        if user_input is not None:
            person = clean_person(user_input)
            errors = validate_person(person, persons)
            if not errors:
                person[CONF_PROFILE_ID] = new_profile_id(
                    person[CONF_DISPLAY_NAME], persons
                )
                return self._save([*persons, person])
        return self.async_show_form(
            step_id="add_person",
            data_schema=person_schema(user_input or self._prefill or None),
            errors=errors,
        )

    async def async_step_add_from_person(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start a new profile from a Home Assistant person."""
        if user_input is not None:
            entity_id = user_input[CONF_PERSON_ENTITY]
            state = self.hass.states.get(entity_id)
            name = (state.name if state else "") or entity_id.split(".", 1)[-1]
            self._prefill = {CONF_DISPLAY_NAME: name, CONF_PERSON_ENTITY: entity_id}
            return await self.async_step_add_person()
        return self.async_show_form(
            step_id="add_from_person",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person")
                    )
                }
            ),
        )

    async def async_step_edit_person(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the person to edit."""
        persons = self._persons
        if user_input is not None:
            self._edit_id = user_input[CONF_PROFILE_ID]
            return await self.async_step_edit_person_form()
        choices = {p[CONF_PROFILE_ID]: p[CONF_DISPLAY_NAME] for p in persons}
        return self.async_show_form(
            step_id="edit_person",
            data_schema=vol.Schema({vol.Required(CONF_PROFILE_ID): vol.In(choices)}),
        )

    async def async_step_edit_person_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the chosen person. profile_id never changes."""
        persons = self._persons
        current = next(p for p in persons if p[CONF_PROFILE_ID] == self._edit_id)
        errors: dict[str, str] = {}
        if user_input is not None:
            person = clean_person(user_input)
            others = [p for p in persons if p[CONF_PROFILE_ID] != self._edit_id]
            errors = validate_person(person, others)
            if not errors:
                person[CONF_PROFILE_ID] = self._edit_id
                return self._save(
                    [person if p is current else p for p in persons],
                )
        return self.async_show_form(
            step_id="edit_person_form",
            data_schema=person_schema(user_input or current),
            errors=errors,
        )

    async def async_step_delete_person(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Delete a person. At least one person must remain."""
        persons = self._persons
        if user_input is not None:
            remaining = [
                p for p in persons if p[CONF_PROFILE_ID] != user_input[CONF_PROFILE_ID]
            ]
            if remaining:
                self._drop_from_scales(user_input[CONF_PROFILE_ID])
                return self._save(remaining)
        choices = {p[CONF_PROFILE_ID]: p[CONF_DISPLAY_NAME] for p in persons}
        return self.async_show_form(
            step_id="delete_person",
            data_schema=vol.Schema({vol.Required(CONF_PROFILE_ID): vol.In(choices)}),
        )

    def _drop_from_scales(self, profile_id: str) -> None:
        """Remove a deleted person from every scale's explicit people list."""
        for scale in self.hass.config_entries.async_entries(DOMAIN):
            allowed = scale.options.get(CONF_PEOPLE)
            if is_people_entry(scale) or allowed is None or profile_id not in allowed:
                continue
            # An empty list stays empty: readings wait as pending until
            # someone is chosen, instead of going to everyone.
            self.hass.config_entries.async_update_entry(
                scale,
                options={
                    **scale.options,
                    CONF_PEOPLE: [pid for pid in allowed if pid != profile_id],
                },
            )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit attribution and notification settings."""
        options = self.config_entry.options
        if user_input is not None:
            data = {**options, **user_input}
            for key in (CONF_HISTORY_SIZE, CONF_PENDING_TIMEOUT):
                data[key] = int(data[key])
            if not data.get(CONF_NOTIFY_SERVICE):
                data.pop(CONF_NOTIFY_SERVICE, None)
            return self.async_create_entry(data=data)

        def current(key: str, default: Any) -> Any:
            return options.get(key, default)

        notify = (
            {"suggested_value": options[CONF_NOTIFY_SERVICE]}
            if options.get(CONF_NOTIFY_SERVICE)
            else None
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TOLERANCE_KG,
                    default=current(CONF_TOLERANCE_KG, DEFAULT_TOLERANCE_KG),
                ): _number(1, 50, 0.5),
                vol.Required(
                    CONF_TOLERANCE_PCT,
                    default=current(CONF_TOLERANCE_PCT, DEFAULT_TOLERANCE_PCT),
                ): _number(1, 50, 0.5),
                vol.Required(
                    CONF_MARGIN_KG,
                    default=current(CONF_MARGIN_KG, DEFAULT_MARGIN_KG),
                ): _number(0, 20, 0.5),
                vol.Required(
                    CONF_HISTORY_SIZE,
                    default=current(CONF_HISTORY_SIZE, DEFAULT_HISTORY_SIZE),
                ): _number(5, 200),
                vol.Required(
                    CONF_PENDING_TIMEOUT,
                    default=current(CONF_PENDING_TIMEOUT, DEFAULT_PENDING_TIMEOUT_MIN),
                ): _number(1, 1440),
                vol.Optional(CONF_NOTIFY_SERVICE, description=notify): str,
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)
