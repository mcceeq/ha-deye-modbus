"""Thin wrapper around the Modbus client used by the integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from .const import CONNECTION_TYPE_RTU, CONNECTION_TYPE_TCP

_LOGGER = logging.getLogger(__name__)


class DeyeModbusClient:
    """Handle Modbus RTU (serial) communication with a Deye inverter.

    NOTE: Register addresses and decoding are placeholders; wire them to real
    Deye register maps to surface meaningful data.
    """

    def __init__(
        self,
        connection_type: str,
        slave_id: int,
        device: str | None = None,
        baudrate: int | None = None,
        parity: str | None = None,
        stopbits: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self._connection_type = connection_type
        self._device = device
        self._baudrate = baudrate
        self._parity = parity
        self._stopbits = stopbits
        self._host = host
        self._port = port
        self._slave_id = slave_id
        self._client: AsyncModbusSerialClient | AsyncModbusTcpClient | None = None

    async def async_setup(self) -> None:
        """Prepare the client connection."""
        if self._connection_type == CONNECTION_TYPE_RTU:
            if not self._device:
                raise ValueError("Serial device not provided for RTU mode")
            self._client = AsyncModbusSerialClient(
                method="rtu",
                port=self._device,
                baudrate=self._baudrate or 9600,
                parity=self._parity or "N",
                stopbits=self._stopbits or 1,
                bytesize=8,
                timeout=3,
            )
        elif self._connection_type == CONNECTION_TYPE_TCP:
            if not self._host or not self._port:
                raise ValueError("Host/port not provided for TCP mode")
            self._client = AsyncModbusTcpClient(
                host=self._host,
                port=self._port,
                timeout=3,
            )
        else:
            raise ValueError(f"Unknown connection type: {self._connection_type}")

        connected = await self._client.connect()
        if not connected:
            raise ConnectionError("Failed to open Modbus connection")

    async def async_close(self) -> None:
        """Close any open connections."""
        if self._client:
            await self._client.close()
            self._client = None

    async def async_read_data(self) -> dict[str, Any]:
        """Read values from the inverter.

        Replace the placeholder register reads with the actual Deye map.
        """
        if not self._client:
            raise ConnectionError("Modbus client not initialized")

        # Example placeholder: read two registers starting at address 0
        rr = await self._client.read_holding_registers(0, 2, slave=self._slave_id)
        if rr.isError():
            raise ConnectionError(f"Modbus read failed: {rr}")

        decoder = BinaryPayloadDecoder.fromRegisters(
            rr.registers,
            byteorder=Endian.Big,
            wordorder=Endian.Big,
        )

        sample_value = decoder.decode_16bit_int()

        return {
            "grid_power": sample_value,
            "pv_power": None,
            "load_power": None,
        }
