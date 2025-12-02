from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN


class DeyeModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Deye Modbus."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """First step – we don't ask anything yet."""
        if user_input is not None:
            return self.async_create_entry(
                title="Deye Modbus",
                data=user_input,
            )

        # Empty form, just a Submit button for now
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DeyeModbusOptionsFlow(config_entry)


class DeyeModbusOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Deye Modbus (placeholder)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # No options yet – just finish
        return self.async_create_entry(title="", data={})
