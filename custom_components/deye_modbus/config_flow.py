from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEVICE,
    DEFAULT_HOST,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOPBITS,
    DOMAIN,
)


class DeyeModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Deye Modbus."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """First step: pick connection type."""
        if user_input is not None:
            connection_type = user_input[CONF_CONNECTION_TYPE]
            if connection_type == CONNECTION_TYPE_RTU:
                return await self.async_step_rtu()
            return await self.async_step_tcp()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONNECTION_TYPE, default=DEFAULT_CONNECTION_TYPE
                    ): vol.In([CONNECTION_TYPE_RTU, CONNECTION_TYPE_TCP]),
                }
            ),
        )

    async def async_step_rtu(self, user_input: dict | None = None) -> FlowResult:
        """Collect RTU/serial connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_DEVICE],
                data={
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                    CONF_DEVICE: user_input[CONF_DEVICE],
                    CONF_BAUDRATE: user_input[CONF_BAUDRATE],
                    CONF_PARITY: user_input[CONF_PARITY],
                    CONF_STOPBITS: user_input[CONF_STOPBITS],
                    CONF_SLAVE_ID: user_input[CONF_SLAVE_ID],
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=DEFAULT_DEVICE): str,
                vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): int,
                vol.Required(CONF_PARITY, default=DEFAULT_PARITY): vol.In(["N", "E", "O"]),
                vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In([1, 2]),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
            }
        )

        return self.async_show_form(
            step_id="rtu",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_tcp(self, user_input: dict | None = None) -> FlowResult:
        """Collect TCP connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                data={
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SLAVE_ID: user_input[CONF_SLAVE_ID],
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
            }
        )

        return self.async_show_form(
            step_id="tcp",
            data_schema=data_schema,
            errors=errors,
        )
