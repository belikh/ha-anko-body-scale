"""Config flow for the ANKO Body Scale integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_AGE,
    CONF_HEIGHT_CM,
    CONF_SEX,
    DEFAULT_AGE,
    DEFAULT_HEIGHT_CM,
    DEFAULT_SEX,
    DOMAIN,
    SEX_FEMALE,
    SEX_MALE,
)
from .parser import LOCAL_NAME

PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HEIGHT_CM, default=DEFAULT_HEIGHT_CM): vol.Coerce(int),
        vol.Required(CONF_AGE, default=DEFAULT_AGE): vol.Coerce(int),
        vol.Required(CONF_SEX, default=DEFAULT_SEX): vol.In([SEX_MALE, SEX_FEMALE]),
    }
)


class AnkoScaleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the ANKO Body Scale."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._address: str | None = None
        self._title: str = "ANKO Body Scale"

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a scale discovered by the Bluetooth integration."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._title = discovery_info.name or self._title
        return await self.async_step_profile()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup by picking a previously seen scale."""
        if user_input is not None:
            self._address = user_input["address"]
            await self.async_set_unique_id(self._address)
            self._abort_if_unique_id_configured()
            return await self.async_step_profile()

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
            data_schema=vol.Schema({vol.Required("address"): vol.In(discovered)}),
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the body-composition profile for the person using this scale."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data={"address": self._address},
                options=user_input,
            )

        return self.async_show_form(step_id="profile", data_schema=PROFILE_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AnkoScaleOptionsFlow:
        """Return the options flow for this integration."""
        return AnkoScaleOptionsFlow()


class AnkoScaleOptionsFlow(OptionsFlow):
    """Handle updates to the body-composition profile."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show or submit the body-profile options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HEIGHT_CM,
                    default=options.get(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM),
                ): vol.Coerce(int),
                vol.Required(
                    CONF_AGE, default=options.get(CONF_AGE, DEFAULT_AGE)
                ): vol.Coerce(int),
                vol.Required(
                    CONF_SEX, default=options.get(CONF_SEX, DEFAULT_SEX)
                ): vol.In([SEX_MALE, SEX_FEMALE]),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
