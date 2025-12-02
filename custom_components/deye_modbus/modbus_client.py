"""Thin wrapper around the Modbus client used by the integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

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

        The mapping below is a minimal set based on known addresses. Adjust
        scaling/decoding as you refine the register map.
        """
        if not self._client:
            raise ConnectionError("Modbus client not initialized")

        async def _read_holding(address: int, count: int):
            """Read holding registers with broad compatibility across pymodbus versions."""
            try:
                return await self._client.read_holding_registers(address, count)
            except TypeError as err1:
                try:
                    return await self._client.read_holding_registers(address, count, unit=self._slave_id)
                except TypeError as err2:
                    try:
                        return await self._client.read_holding_registers(address, count, slave=self._slave_id)
                    except TypeError as err3:
                        raise err1 from err3

        def _signed_16(regs: list[int], idx: int, scale: float | None = None) -> float | int | None:
            if idx >= len(regs):
                return None
            val = regs[idx]
            val = val - 0x10000 if val & 0x8000 else val
            return val if scale is None else val * scale

        def _u16(regs: list[int], idx: int, scale: float | None = None) -> float | int | None:
            if idx >= len(regs):
                return None
            val = regs[idx]
            return val if scale is None else val * scale

        def _u32(regs: list[int], idx: int, scale: float | None = None) -> float | int | None:
            if idx + 1 >= len(regs):
                return None
            val = (regs[idx] << 16) | regs[idx + 1]
            return val if scale is None else val * scale

        data: dict[str, Any] = {}

        # Block 1: 70-86 (day totals, frequency, energy)
        rr = await _read_holding(70, 17)
        if not rr.isError():
            b1 = rr.registers
            data["day_charge"] = _u16(b1, 0)  # Addr 70
            data["day_discharge"] = _u16(b1, 1)  # Addr 71
            data["energy_bought_day"] = _u16(b1, 6)  # Addr 76
            data["frequency_grid"] = _u16(b1, 9)  # Addr 79
            data["frequency_grid_total"] = _u32(b1, 9)  # Addr 79-80 (L/H)
            data["energy_load_day"] = _u16(b1, 14)  # Addr 84
            data["energy_load_total"] = _u32(b1, 15)  # Addr 85-86
        else:
            raise ConnectionError(f"Modbus read failed (70-86): {rr}")

        # Block 1b: identity/status/temps/energy totals (59-96, 108, 109-112)
        rr = await _read_holding(59, 54)
        if not rr.isError():
            b1b = rr.registers
            data["inverter_status"] = _u16(b1b, 0)  # 59
            data["internal_temp_1"] = _signed_16(b1b, 31, 0.01)  # 90
            data["internal_temp_2"] = _signed_16(b1b, 32, 0.01)  # 91
            data["inverter_total_energy"] = _u16(b1b, 37, 0.1)  # 96
            # 108, 109-112
            data["inverter_day_energy"] = _u16(b1b, 49, 0.1)  # 108
            data["pv1_voltage"] = _u16(b1b, 50, 0.1)  # 109
            data["pv1_current"] = _u16(b1b, 51, 0.01)  # 110
            data["pv2_voltage"] = _u16(b1b, 52, 0.1)  # 111
            data["pv2_current"] = _u16(b1b, 53, 0.01)  # 112
            # serial number fragment (0x0003, offset -56): 3-? Not fetched here.
        else:
            raise ConnectionError(f"Modbus read failed (59-112): {rr}")

        # Block 2: 150-158 (voltages)
        rr = await _read_holding(150, 9)
        if not rr.isError():
            b2 = rr.registers
            data["grid_voltage_l1"] = _u16(b2, 0, 0.1)  # 150 L1-N
            data["grid_voltage_l2"] = _u16(b2, 1, 0.1)  # 151 L2-N
            data["grid_voltage_ll"] = _u16(b2, 3, 0.1)  # 153 L1-L2 (mid)
            data["output_voltage_l1"] = _u16(b2, 4, 0.1)  # 154
            data["output_voltage_l2"] = _u16(b2, 5, 0.1)  # 155
            data["output_voltage_ll"] = _u16(b2, 6, 0.1)  # 156
            data["load_voltage_l1"] = _u16(b2, 7, 0.1)  # 157
            data["load_voltage_l2"] = _u16(b2, 8, 0.1)  # 158
        else:
            raise ConnectionError(f"Modbus read failed (150-158): {rr}")

        # Block 3: 160-172 (currents + grid/external power)
        rr = await _read_holding(160, 13)
        if not rr.isError():
            b3 = rr.registers
            data["grid_current_l1"] = _signed_16(b3, 0, 0.01)  # 160
            data["grid_current_l2"] = _signed_16(b3, 1, 0.01)  # 161
            data["external_current_l1"] = _signed_16(b3, 2, 0.01)  # 162
            data["external_current_l2"] = _signed_16(b3, 3, 0.01)  # 163
            data["output_current_l1"] = _signed_16(b3, 4, 0.01)  # 164
            data["output_current_l2"] = _signed_16(b3, 5, 0.01)  # 165
            data["grid_power_l1"] = _signed_16(b3, 7, 1)  # 167
            data["grid_power_l2"] = _signed_16(b3, 8, 1)  # 168
            data["grid_import_export_power"] = _signed_16(b3, 10, 1)  # 170 total grid power (signed)
            data["external_power_l1"] = _signed_16(b3, 10, 1)  # 170
            data["external_power_l2"] = _signed_16(b3, 11, 1)  # 171
            data["external_power_total"] = _signed_16(b3, 12, 1)  # 172
        else:
            raise ConnectionError(f"Modbus read failed (160-172): {rr}")

        # Block 4: 173-180 (output + load power & current)
        rr = await _read_holding(173, 8)
        if not rr.isError():
            b4 = rr.registers
            data["output_power_l1"] = _signed_16(b4, 0, 1)  # 173
            data["output_power_l2"] = _signed_16(b4, 1, 1)  # 174
            data["load_power_l1"] = _signed_16(b4, 3, 1)  # 176
            data["load_power_l2"] = _signed_16(b4, 4, 1)  # 177
            data["load_power_total"] = _signed_16(b4, 5, 1)  # 178
            data["load_current_l1"] = _signed_16(b4, 6, 0.01)  # 179
            data["load_current_l2"] = _signed_16(b4, 7, 0.01)  # 180
        else:
            raise ConnectionError(f"Modbus read failed (173-180): {rr}")

        # Block 5: 182-189 (battery temp/voltage/SOC/status + pv power)
        rr = await _read_holding(182, 8)
        if not rr.isError():
            b5 = rr.registers
            data["battery_temp"] = _signed_16(b5, 0, 0.1)  # 182
            data["battery_voltage"] = _u16(b5, 1, 0.01)  # 183
            data["battery_soc"] = _u16(b5, 2, 1)  # 184
            data["battery_status"] = _u16(b5, 3, 1)  # 185
            data["pv1_power"] = _u16(b5, 4, 1)  # 186
            data["pv2_power"] = _u16(b5, 5, 1)  # 187
            data["battery_status_alt"] = _u16(b5, 6, 1)  # 188 (not in list but placeholder)
            data["battery_status_flag"] = _u16(b5, 7, 1)  # 189
        else:
            raise ConnectionError(f"Modbus read failed (182-185): {rr}")

        # Block 6: 190-194 (battery power/current, load/output freq, relay)
        rr = await _read_holding(190, 5)
        if not rr.isError():
            b6 = rr.registers
            data["battery_power"] = _signed_16(b6, 0, 1)  # 190
            data["battery_current"] = _signed_16(b6, 1, 0.01)  # 191
            data["frequency_load"] = _u16(b6, 2, 0.01)  # 192
            data["frequency_output"] = _u16(b6, 3, 0.01)  # 193
            data["relay_status"] = _u16(b6, 4, 1)  # 194
        else:
            raise ConnectionError(f"Modbus read failed (190-194): {rr}")

        # Block 7: BMS limits 212-219
        rr = await _read_holding(212, 8)
        if not rr.isError():
            b7 = rr.registers
            data["bms_max_charge_current"] = _u16(b7, 0, 1)  # 212
            data["bms_max_discharge_current"] = _u16(b7, 1, 1)  # 213
            data["bms_abs_max_charge_current"] = _u16(b7, 6, 1)  # 218
            data["bms_abs_max_discharge_current"] = _u16(b7, 7, 1)  # 219
        else:
            raise ConnectionError(f"Modbus read failed (212-219): {rr}")

        # Block 8: ToU enable and slot times 248-255
        rr = await _read_holding(248, 8)
        if not rr.isError():
            b8 = rr.registers
            data["tou_mode_enable"] = _u16(b8, 0)  # 248
            data["tou_slot1_minutes"] = _u16(b8, 2)  # 250
            data["tou_slot2_minutes"] = _u16(b8, 3)  # 251
            data["tou_slot3_minutes"] = _u16(b8, 4)  # 252
            data["tou_slot4_minutes"] = _u16(b8, 5)  # 253
            data["tou_slot5_minutes"] = _u16(b8, 6)  # 254
            data["tou_slot6_minutes"] = _u16(b8, 7)  # 255
        else:
            raise ConnectionError(f"Modbus read failed (248-255): {rr}")

        # Block 9: ToU power limits 256-261
        rr = await _read_holding(256, 6)
        if not rr.isError():
            b9 = rr.registers
            data["tou_slot1_power_limit"] = _u16(b9, 0, 1)  # 256
            data["tou_slot2_power_limit"] = _u16(b9, 1, 1)  # 257
            data["tou_slot3_power_limit"] = _u16(b9, 2, 1)  # 258
            data["tou_slot4_power_limit"] = _u16(b9, 3, 1)  # 259
            data["tou_slot5_power_limit"] = _u16(b9, 4, 1)  # 260
            data["tou_slot6_power_limit"] = _u16(b9, 5, 1)  # 261
        else:
            raise ConnectionError(f"Modbus read failed (256-261): {rr}")

        return data
