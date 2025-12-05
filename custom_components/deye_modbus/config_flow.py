from __future__ import annotations

import voluptuous as vol
from pathlib import Path
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BAUDRATE,
    CONF_BATTERY_CONTROL_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_INVERTER_DEFINITION,
    CONF_PARITY,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEVICE,
    DEFAULT_HOST,
    DEFAULT_INVERTER_DEFINITION,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOPBITS,
    DOMAIN,
)
from .definition_loader import load_definition


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
        battery_mode_opts = _battery_mode_options()
        battery_mode_labels = list(battery_mode_opts.keys()) if battery_mode_opts else None

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
                    CONF_INVERTER_DEFINITION: user_input[CONF_INVERTER_DEFINITION],
                    CONF_BATTERY_CONTROL_MODE: battery_mode_opts.get(user_input.get(CONF_BATTERY_CONTROL_MODE)) if battery_mode_opts else user_input.get(CONF_BATTERY_CONTROL_MODE),
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=DEFAULT_DEVICE): str,
                vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): int,
                vol.Required(CONF_PARITY, default=DEFAULT_PARITY): vol.In(["N", "E", "O"]),
                vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In([1, 2]),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
                vol.Required(CONF_INVERTER_DEFINITION, default=DEFAULT_INVERTER_DEFINITION): vol.In([DEFAULT_INVERTER_DEFINITION]),
                vol.Optional(CONF_BATTERY_CONTROL_MODE): vol.In(battery_mode_labels) if battery_mode_labels else int,
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
        battery_mode_opts = _battery_mode_options()
        battery_mode_labels = list(battery_mode_opts.keys()) if battery_mode_opts else None

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
                    CONF_INVERTER_DEFINITION: user_input[CONF_INVERTER_DEFINITION],
                    CONF_BATTERY_CONTROL_MODE: battery_mode_opts.get(user_input.get(CONF_BATTERY_CONTROL_MODE)) if battery_mode_opts else user_input.get(CONF_BATTERY_CONTROL_MODE),
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
                vol.Required(CONF_INVERTER_DEFINITION, default=DEFAULT_INVERTER_DEFINITION): vol.In([DEFAULT_INVERTER_DEFINITION]),
                vol.Optional(CONF_BATTERY_CONTROL_MODE): vol.In(battery_mode_labels) if battery_mode_labels else int,
            }
        )

        return self.async_show_form(
            step_id="tcp",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    def _current(entry):
        data = dict(entry.data)
        data.update(entry.options)
        return data

    @staticmethod
    async def async_get_options_flow(config_entry):
        return DeyeModbusOptionsFlow(config_entry)


class DeyeModbusOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Deye Modbus."""

    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        data = DeyeModbusConfigFlow._current(self.entry)
        connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        if user_input:
            connection_type = user_input[CONF_CONNECTION_TYPE]
            if connection_type == CONNECTION_TYPE_RTU:
                return await self.async_step_rtu()
            return await self.async_step_tcp()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONNECTION_TYPE, default=connection_type
                    ): vol.In([CONNECTION_TYPE_RTU, CONNECTION_TYPE_TCP]),
                }
            ),
        )

    async def async_step_rtu(self, user_input=None):
        data = DeyeModbusConfigFlow._current(self.entry)
        errors: dict[str, str] = {}
        battery_mode_opts = _battery_mode_options()
        battery_mode_labels = list(battery_mode_opts.keys()) if battery_mode_opts else None
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=data.get(CONF_DEVICE, DEFAULT_DEVICE)): str,
                vol.Required(CONF_BAUDRATE, default=data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)): int,
                vol.Required(CONF_PARITY, default=data.get(CONF_PARITY, DEFAULT_PARITY)): vol.In(["N", "E", "O"]),
                vol.Required(CONF_STOPBITS, default=data.get(CONF_STOPBITS, DEFAULT_STOPBITS)): vol.In([1, 2]),
                vol.Required(CONF_SLAVE_ID, default=data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)): int,
                vol.Required(CONF_SCAN_INTERVAL, default=int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds()))): int,
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_RTU): vol.In([CONNECTION_TYPE_RTU]),
                vol.Required(CONF_INVERTER_DEFINITION, default=data.get(CONF_INVERTER_DEFINITION, DEFAULT_INVERTER_DEFINITION)): vol.In([DEFAULT_INVERTER_DEFINITION]),
                vol.Optional(CONF_BATTERY_CONTROL_MODE, default=_display_label_for_mode(data.get(CONF_BATTERY_CONTROL_MODE), battery_mode_opts)): vol.In(battery_mode_labels) if battery_mode_labels else int,
            }
        )
        return self.async_show_form(step_id="rtu", data_schema=schema, errors=errors)

    async def async_step_tcp(self, user_input=None):
        data = DeyeModbusConfigFlow._current(self.entry)
        errors: dict[str, str] = {}
        battery_mode_opts = _battery_mode_options()
        battery_mode_labels = list(battery_mode_opts.keys()) if battery_mode_opts else None
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=data.get(CONF_HOST, DEFAULT_HOST)): str,
                vol.Required(CONF_PORT, default=data.get(CONF_PORT, DEFAULT_PORT)): int,
                vol.Required(CONF_SLAVE_ID, default=data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)): int,
                vol.Required(CONF_SCAN_INTERVAL, default=int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds()))): int,
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_TCP): vol.In([CONNECTION_TYPE_TCP]),
                vol.Required(CONF_INVERTER_DEFINITION, default=data.get(CONF_INVERTER_DEFINITION, DEFAULT_INVERTER_DEFINITION)): vol.In([DEFAULT_INVERTER_DEFINITION]),
                vol.Optional(CONF_BATTERY_CONTROL_MODE, default=_display_label_for_mode(data.get(CONF_BATTERY_CONTROL_MODE), battery_mode_opts)): vol.In(battery_mode_labels) if battery_mode_labels else int,
            }
        )
        return self.async_show_form(step_id="tcp", data_schema=schema, errors=errors)


def _battery_mode_options() -> dict[str, int] | None:
    """Return available battery control mode labels->keys from current definition."""
    try:
        def_path = Path(__file__).parent / "definitions" / f"{DEFAULT_INVERTER_DEFINITION}.yaml"
        items = load_definition(def_path)
        for item in items:
            if item.key == "battery_control_mode" and item.lookup:
                return {label: key for key, label in item.lookup.items()}
    except Exception:
        return None
    return None


def _display_label_for_mode(mode_value: int | None, options: dict[str, int] | None) -> str | int | None:
    """Return the label string for a stored mode value, for use as default in the form."""
    if mode_value is None or not options:
        return mode_value
    for label, val in options.items():
        if val == mode_value:
            return label
    return mode_value
