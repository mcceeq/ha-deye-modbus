"""Home Assistant integration for Deye Modbus."""

from __future__ import annotations

import logging
import datetime as dt
import time as _time
from pathlib import Path
from typing import Any

from homeassistant.util import dt as dt_util

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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

# Some registers use implicit scaling not captured in the definitions.
_SCALE_OVERRIDES: dict[str, float] = {
    # Register 0x00D4/0x00D5 report integer amps; exposed in HA should be *100
    "battery_bms_charge_current_limit": 100,
    "battery_bms_discharge_current_limit": 100,
}


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
        spans = _build_spans(def_items)

        last_ts: float = 0

        async def _async_update_definitions() -> dict[str, Any]:
            nonlocal last_ts
            prev = hass.data[DOMAIN][entry.entry_id]["definitions"]["coordinator"].data if "definitions" in hass.data[DOMAIN][entry.entry_id] else {}
            try:
                data: dict[str, Any] = {}
                read_ts = _time.monotonic()
                # Read in batches
                registers: dict[int, int] = {}
                successful_spans = 0
                for start, count in spans:
                    try:
                        rr = await client.async_read_holding_registers(start, count)
                        if rr.isError():
                            raise ConnectionError(rr)
                        vals = list(getattr(rr, "registers", []))
                        _LOGGER.debug(
                            "Definition read @%s (%s regs): %s",
                            start,
                            len(vals),
                            vals if len(vals) <= 12 else f"{vals[:12]}...",
                        )
                        for idx, reg_val in enumerate(rr.registers):
                            registers[start + idx] = reg_val
                        successful_spans += 1
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.warning("Definition batch read failed (%s, %s): %s", start, count, err)
                        continue

                if not registers:
                    msg = "No Modbus definition reads succeeded; keeping previous data"
                    if prev:
                        _LOGGER.error("%s (%s previous keys)", msg, len(prev))
                        return prev
                    raise UpdateFailed(msg)

                # Decode items using cached register values
                decoded = 0
                for item in def_items:
                    try:
                        regs = []
                        missing = False
                        for addr in item.registers:
                            if addr in registers:
                                regs.append(registers[addr])
                            else:
                                missing = True
                                break
                        if missing:
                            continue
                        val = _decode_item(item, regs)
                        if val is None:
                            continue
                        data[item.key] = val
                        decoded += 1
                        _LOGGER.debug(
                            "Decoded %s from registers %s: %s -> %s",
                            item.key,
                            item.registers,
                            regs,
                            val,
                        )
                    except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Definition decode failed for %s: %s", item.name, err)
                        continue

                if not data:
                    msg = "Definition decode produced no values; keeping previous data"
                    if prev:
                        _LOGGER.error("%s (%s previous keys)", msg, len(prev))
                        return prev
                    raise UpdateFailed(msg)

                _LOGGER.debug(
                    "Definition update decoded %s items; spans ok=%s/%s",
                    decoded,
                    successful_spans,
                    len(spans),
                )
                if read_ts <= last_ts:
                    existing = hass.data[DOMAIN][entry.entry_id].get("definitions", {}).get("coordinator")
                    return existing.data if existing else {}
                last_ts = read_ts
                # Merge with previous to avoid dropping to unknowns when a read fails
                merged = dict(prev)
                merged.update(data)
                if merged == prev:
                    return prev
                return merged
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Definition update failed; keeping previous data: %s", err)
                return prev

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


def _build_spans(items) -> list[tuple[int, int]]:
    """Build batched read spans from definition items."""
    spans: list[tuple[int, int]] = []
    ranges: list[tuple[int, int]] = []
    for item in items:
        start = min(item.registers)
        end = max(item.registers) + 1
        ranges.append((start, end))
    ranges.sort(key=lambda r: r[0])
    if not ranges:
        return spans
    cur_start, cur_end = ranges[0]
    for start, end in ranges[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            spans.append((cur_start, cur_end - cur_start))
            cur_start, cur_end = start, end
    spans.append((cur_start, cur_end - cur_start))
    return spans


def _decode_item(item, regs: list[int]) -> Any:
    """Decode registers using a simplified subset of Solarman rules."""
    if not regs:
        return None

    val: Any = None
    rule = item.rule

    def _bcd_byte_to_int(raw: int) -> int | None:
        """Convert a single BCD-encoded byte (0x00-0x99) to int."""
        tens = (raw >> 4) & 0x0F
        ones = raw & 0x0F
        if tens >= 10 or ones >= 10:
            return None
        return tens * 10 + ones

    def _decode_year(raw: int) -> int | None:
        """Return a plausible four-digit year from raw or BCD encoded data."""
        def _try_year(val: int) -> int | None:
            if 1970 <= val <= 2100:
                return val
            if 0 <= val < 100:
                candidate = 2000 + val
                return candidate if candidate <= 2100 else None
            high = _bcd_byte_to_int((val >> 8) & 0xFF)
            low = _bcd_byte_to_int(val & 0xFF)
            if high is None or low is None:
                return None
            candidate = high * 100 + low
            return candidate if 1970 <= candidate <= 2100 else None

        # Try direct, then swapped-byte BCD
        direct = _try_year(raw)
        if direct is not None:
            return direct
        swapped = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
        return _try_year(swapped)

    def _decode_component(raw: int, upper: int, allow_zero: bool = False) -> int | None:
        """Decode a date/time component, handling both binary and BCD values."""
        if (allow_zero and 0 <= raw <= upper) or (not allow_zero and 1 <= raw <= upper):
            return raw
        decoded = _bcd_byte_to_int(raw)
        if decoded is None:
            return None
        if allow_zero:
            return decoded if 0 <= decoded <= upper else None
        return decoded if 1 <= decoded <= upper else None

    def _decode_month_day(raw: int) -> tuple[int | None, int | None]:
        """Try both byte orders for month/day."""
        candidates = [
            ((raw >> 8) & 0xFF, raw & 0xFF),
            (raw & 0xFF, (raw >> 8) & 0xFF),
        ]
        for month_raw, day_raw in candidates:
            month = _decode_component(month_raw, 12)
            day = _decode_component(day_raw, 31)
            if None not in (month, day):
                return month, day
        return None, None

    def _decode_hour_min(raw: int) -> tuple[int | None, int | None]:
        """Try both byte orders for hour/minute."""
        candidates = [
            ((raw >> 8) & 0xFF, raw & 0xFF),
            (raw & 0xFF, (raw >> 8) & 0xFF),
        ]
        for hour_raw, minute_raw in candidates:
            hour = _decode_component(hour_raw, 23, allow_zero=True)
            minute = _decode_component(minute_raw, 59, allow_zero=True)
            if None not in (hour, minute):
                return hour, minute
        return None, None

    def _decode_two_digit_year(raw: int) -> int | None:
        """Map a 0-99 byte to a sensible year."""
        if 0 <= raw <= 99:
            candidate = 2000 + raw
            if 1970 <= candidate <= 2100:
                return candidate
        return _decode_year(raw)

    def _decode_datetime_from_regs(regs_in: list[int]) -> dt.datetime | None:
        """Try multiple byte orders and register permutations for datetime."""
        if len(regs_in) < 3:
            return None

        # Common Solarman layout: reg0=YY/MM, reg1=DD/HH, reg2=MM/SS
        y_byte = (regs_in[0] >> 8) & 0xFF
        m_byte = regs_in[0] & 0xFF
        d_byte = (regs_in[1] >> 8) & 0xFF
        h_byte = regs_in[1] & 0xFF
        min_byte = (regs_in[2] >> 8) & 0xFF
        s_byte = regs_in[2] & 0xFF
        solarman_year = _decode_two_digit_year(y_byte)
        solarman_month = _decode_component(m_byte, 12)
        solarman_day = _decode_component(d_byte, 31)
        solarman_hour = _decode_component(h_byte, 23, allow_zero=True)
        solarman_minute = _decode_component(min_byte, 59, allow_zero=True)
        solarman_second = _decode_component(s_byte, 59, allow_zero=True)
        if None not in (
            solarman_year,
            solarman_month,
            solarman_day,
            solarman_hour,
            solarman_minute,
            solarman_second,
        ):
            try:
                return dt.datetime(
                    solarman_year,
                    solarman_month,
                    solarman_day,
                    solarman_hour or 0,
                    solarman_minute or 0,
                    solarman_second or 0,
                )
            except Exception:  # noqa: BLE001
                pass

        # Prefer definition order first, then permutations for resilience
        idx_orders = [(0, 1, 2), (1, 0, 2), (2, 0, 1), (0, 2, 1), (1, 2, 0), (2, 1, 0)]
        for y_idx, md_idx, hm_idx in idx_orders:
            year = _decode_year(regs_in[y_idx])
            month, day = _decode_month_day(regs_in[md_idx])
            hour, minute = _decode_hour_min(regs_in[hm_idx])
            if None in (year, month, day, hour, minute):
                continue
                try:
                    return dt.datetime(year, month, day, hour or 0, minute or 0)
                except Exception:  # noqa: BLE001
                    continue
        # Fallback: interpret successive bytes as YH,YL,M,D,H,M
        bytes_linear: list[int] = []
        for reg in regs_in:
            bytes_linear.append((reg >> 8) & 0xFF)
            bytes_linear.append(reg & 0xFF)
        if len(bytes_linear) >= 6:
            y_raw = (bytes_linear[0] << 8) | bytes_linear[1]
            year = _decode_year(y_raw)
            month = _decode_component(bytes_linear[2], 12)
            day = _decode_component(bytes_linear[3], 31)
            hour = _decode_component(bytes_linear[4], 23, allow_zero=True)
            minute = _decode_component(bytes_linear[5], 59, allow_zero=True)
            if None not in (year, month, day, hour, minute):
                try:
                    return dt.datetime(year, month, day, hour or 0, minute or 0)
                except Exception:  # noqa: BLE001
                    pass
        return None

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
                val = _decode_datetime_from_regs(regs[:3])
                if not val:
                    _LOGGER.debug(
                        "Datetime decode failed for %s with raw registers %s",
                        item.name,
                        regs[:3],
                    )
                    return None
            elif item.platform == "time" and len(regs) >= 1:
                hour = _decode_component((regs[0] >> 8) & 0xFF, 23, allow_zero=True)
                minute = _decode_component(regs[0] & 0xFF, 59, allow_zero=True)
                second = (
                    _decode_component(regs[1] & 0xFF, 59, allow_zero=True)
                    if len(regs) > 1
                    else 0
                )
                if None in (hour, minute):
                    # Some firmwares may invert hour/minute bytes
                    hour_swapped = _decode_component(regs[0] & 0xFF, 23, allow_zero=True)
                    minute_swapped = _decode_component((regs[0] >> 8) & 0xFF, 59, allow_zero=True)
                    if None not in (hour_swapped, minute_swapped):
                        hour, minute = hour_swapped, minute_swapped
                if None in (hour, minute, second):
                    _LOGGER.debug("Time decode failed for %s with raw registers %s", item.name, regs)
                    return None
                val = dt.time(hour, minute, second)
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
            val = dt.time(hour, minute, 0)
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
    scale = _SCALE_OVERRIDES.get(getattr(item, "key", None), item.scale)
    if scale:
        try:
            val = val * scale  # type: ignore[operator]
        except Exception:  # noqa: BLE001
            pass

    if item.lookup and isinstance(val, int):
        val = item.lookup.get(val, val)

    # Normalize datetime/time
    if isinstance(val, dt.datetime):
        if val.year < 1970 or val.year > 2100:
            return None
        if val.tzinfo is None:
            val = val.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    if isinstance(val, dt.time):
        # leave naive times as-is
        pass

    return val
