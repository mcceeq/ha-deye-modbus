"""Home Assistant integration for Deye Modbus."""

from __future__ import annotations

import logging
import datetime
import time as _time
from pathlib import Path
from typing import Any

from homeassistant.util import dt as dt_util

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_STOPBITS,
    CONF_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFINITION_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .modbus_client import DeyeModbusClient
from .definition_loader import load_definition

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Deye Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = DeyeModbusClient(
        connection_type=entry.data[CONF_CONNECTION_TYPE],
        device=entry.data.get(CONF_DEVICE),
        baudrate=entry.data.get(CONF_BAUDRATE),
        parity=entry.data.get(CONF_PARITY),
        stopbits=entry.data.get(CONF_STOPBITS),
        host=entry.data.get(CONF_HOST),
        port=entry.data.get(CONF_PORT),
        slave_id=entry.data[CONF_SLAVE_ID],
    )

    try:
        await client.async_setup()
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to inverter: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
    }

    # Definition-driven coordinator (read-only)
    definition_path = Path(__file__).parent / "definitions" / "deye_hybrid.yaml"
    if definition_path.exists():
        def_items = load_definition(definition_path)

        last_ts: float = 0

        async def _async_update_definitions() -> dict[str, Any]:
            nonlocal last_ts
            data: dict[str, Any] = {}
            read_ts = _time.monotonic()
            for item in def_items:
                try:
                    rr = await client.async_read_holding_registers(item.registers[0], len(item.registers))
                    if rr.isError():
                        raise ConnectionError(rr)
                    regs = rr.registers
                    val = _decode_item(item, regs)
                    if val is None:
                        continue
                    data[item.key] = val
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Definition read failed for %s: %s", item.name, err)
                    continue
            if read_ts <= last_ts:
                existing = hass.data[DOMAIN][entry.entry_id].get("definitions", {}).get("coordinator")
                return existing.data if existing else {}
            last_ts = read_ts
            return data

        def_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="deye_modbus_definition",
            update_method=_async_update_definitions,
            update_interval=DEFINITION_SCAN_INTERVAL,
        )
        await def_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id]["definitions"] = {
            "items": def_items,
            "coordinator": def_coordinator,
        }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    stored = hass.data[DOMAIN].pop(entry.entry_id, {})
    client: DeyeModbusClient | None = stored.get("client")

    if client:
        await client.async_close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _decode_item(item, regs: list[int]) -> Any:
    """Decode registers using a simplified subset of Solarman rules."""
    if not regs:
        return None

    val: Any = None
    rule = item.rule

    if rule in (None, 1):
        val = regs[0]
    elif rule == 4 and len(regs) >= 2:
        val = (regs[0] << 16) | regs[1]
    elif rule in (5, 7):
        # Basic string decoding: two ASCII bytes per register, high then low
        bytes_out = []
        for reg in regs:
            bytes_out.append((reg >> 8) & 0xFF)
            bytes_out.append(reg & 0xFF)
        val = bytes(byte for byte in bytes_out if byte != 0).decode(errors="ignore").strip()
    elif rule == 8:
        try:
            if item.platform == "datetime" and len(regs) >= 3:
                year = regs[0]
                month = (regs[1] >> 8) & 0xFF
                day = regs[1] & 0xFF
                hour = (regs[2] >> 8) & 0xFF
                minute = regs[2] & 0xFF
                # sanity check years
                if year < 1970 or year > 2100:
                    return None
                val = datetime.datetime(year, month, day, hour, minute, tzinfo=dt_util.DEFAULT_TIME_ZONE)
            elif item.platform == "time" and len(regs) >= 1:
                hour = (regs[0] >> 8) & 0xFF
                minute = regs[0] & 0xFF
                second = regs[1] & 0xFF if len(regs) > 1 else 0
                val = datetime.time(hour, minute, second)
            else:
                return None
        except Exception:  # noqa: BLE001
            return None
    elif rule == 9:
        # HHMM encoded in a single register
        try:
            hhmm = regs[0]
            hour = hhmm // 100
            minute = hhmm % 100
            val = datetime.time(hour, minute, 0)
        except Exception:  # noqa: BLE001
            return None
    else:
        # Unsupported rule – skip for now
        return None

    # Mask/divide/scale if present
    if hasattr(item, "mask") and item.mask is not None:
        try:
            val = val & item.mask  # type: ignore[operator]
        except Exception:  # noqa: BLE001
            pass
    if hasattr(item, "divide") and item.divide:
        try:
            val = val / item.divide  # type: ignore[operator]
        except Exception:  # noqa: BLE001
            pass
    if item.scale:
        try:
            val = val * item.scale  # type: ignore[operator]
        except Exception:  # noqa: BLE001
            pass

    if item.lookup and isinstance(val, int):
        val = item.lookup.get(val, val)

    return val
