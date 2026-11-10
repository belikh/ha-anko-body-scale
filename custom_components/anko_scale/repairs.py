"""Repair flow: turn an unknown weight into a new person."""

from __future__ import annotations

import contextlib
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ServiceValidationError

from .config_flow import clean_person, new_profile_id, person_schema, validate_person
from .const import (
    CONF_DISPLAY_NAME,
    CONF_EXPECTED_WEIGHT,
    CONF_PEOPLE,
    CONF_PERSONS,
    CONF_PROFILE_ID,
    DOMAIN,
)
from .people import find_people_entry


class AddPersonRepairFlow(RepairsFlow):
    """Add a person, seeded with the weight that matched nobody."""

    def __init__(self, entry_id: str, pending_id: str, weight_kg: float) -> None:
        """Remember which weigh-in raised the repair."""
        self._entry_id = entry_id
        self._pending_id = pending_id
        self._weight_kg = weight_kg

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Start the flow."""
        return await self.async_step_person()

    async def async_step_person(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect the new person's details."""
        scale = self.hass.config_entries.async_get_entry(self._entry_id)
        entry = find_people_entry(self.hass)
        if scale is None or entry is None:
            return self.async_abort(reason="entry_gone")
        persons = [dict(p) for p in entry.options.get(CONF_PERSONS, [])]

        errors: dict[str, str] = {}
        if user_input is not None:
            person = clean_person(user_input)
            errors = validate_person(person, persons)
            if not errors:
                person[CONF_PROFILE_ID] = new_profile_id(
                    person[CONF_DISPLAY_NAME], persons
                )
                coordinator = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
                if coordinator is not None:
                    # The pending weigh-in may already be resolved or expired.
                    with contextlib.suppress(ServiceValidationError):
                        coordinator.async_discard_pending(self._pending_id)
                allowed = scale.options.get(CONF_PEOPLE)
                if allowed is not None:
                    # Let the new person use the scale that heard them.
                    self.hass.config_entries.async_update_entry(
                        scale,
                        options={
                            **scale.options,
                            CONF_PEOPLE: [*allowed, person[CONF_PROFILE_ID]],
                        },
                    )
                self.hass.config_entries.async_update_entry(
                    entry, options={**entry.options, CONF_PERSONS: [*persons, person]}
                )
                return self.async_create_entry(data={})

        defaults = user_input or {CONF_EXPECTED_WEIGHT: round(self._weight_kg, 1)}
        return self.async_show_form(
            step_id="person",
            data_schema=person_schema(defaults),
            errors=errors,
            description_placeholders={"weight": f"{self._weight_kg:.1f}"},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Create the fix flow for an unknown-weight repair."""
    assert data is not None
    return AddPersonRepairFlow(
        str(data["entry_id"]), str(data["pending_id"]), float(data["weight_kg"] or 0)
    )
