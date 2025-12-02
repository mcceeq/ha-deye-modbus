"""Thin wrapper around the Modbus client used by the integration."""

from __future__ import annotations

from typing import Any


class DeyeModbusClient:
    """Handle Modbus communication with a Deye inverter.

    This is intentionally minimal scaffolding that can be expanded to perform
    the actual register reads required for the integration.
    """

    def __init__(self, host: str, port: int, slave_id: int) -> None:
        self._host = host
        self._port = port
        self._slave_id = slave_id

    async def async_setup(self) -> None:
        """Prepare the client connection.

        Replace this stub with real connection logic as needed.
        """

    async def async_close(self) -> None:
        """Close any open connections."""

    async def async_read_data(self) -> dict[str, Any]:
        """Read values from the inverter.

        The returned mapping is consumed by the DataUpdateCoordinator. Replace
        the placeholder values with real Modbus register reads.
        """
        return {
            "grid_power": None,
            "pv_power": None,
            "load_power": None,
        }
