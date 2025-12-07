"""Number entities driven by definitions (writes allowed for a limited set)."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE
from .definition_loader import DefinitionItem

_LOGGER = logging.getLogger(__name__)

# Keys allowed to perform writes (ToU program controls)
_WRITABLE_NUMBER_KEYS = {
    # Program power
    "program_1_power",
    "program_2_power",
    "program_3_power",
    "program_4_power",
    "program_5_power",
    "program_6_power",
    # Program voltages
    "program_1_voltage",
    "program_2_voltage",
    "program_3_voltage",
    "program_4_voltage",
    "program_5_voltage",
    "program_6_voltage",
    # Program SOCs
    "program_1_soc",
    "program_2_soc",
    "program_3_soc",
    "program_4_soc",
    "program_5_soc",
    "program_6_soc",
    # Battery current limits
    "battery_max_charging_current",
    "battery_max_discharging_current",
    "battery_generator_charging_current",
    "battery_grid_charging_current",
    # SOC thresholds
    "battery_shutdown_soc",
    "battery_restart_soc",
    "battery_low_soc",
    "battery_grid_charging_start",
    "battery_generator_charging_start",
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up definition-driven numbers if available."""
    sol = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not sol:
        return

    coordinator = sol["coordinator"]
    items: list[DefinitionItem] = sol["items"]

    base_device_info = _base_device(entry.entry_id, entry.data)
    entities: list[DeyeDefinitionNumber] = []

    for item in items:
        if item.platform != "number":
            continue

        desc = _description_for(item)
        if not desc:
            continue

        entities.append(
            DeyeDefinitionNumber(
                coordinator=coordinator,
                description=desc,
                entry_id=entry.entry_id,
                definition=item,
                device_info=_device_for_group(item, entry.entry_id, base_device_info),
            )
        )

    if entities:
        async_add_entities(entities)


class DeyeDefinitionNumber(CoordinatorEntity, NumberEntity):
    """Number entity driven by external definition (read-only)."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator,
        description: NumberEntityDescription,
        entry_id: str,
        definition: DefinitionItem,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_def_{description.key}"
        self._attr_device_info = device_info
        self._entry_id = entry_id
        self._definition = definition

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value):
        if self.entity_description.key not in _WRITABLE_NUMBER_KEYS:
            raise HomeAssistantError("Writes not implemented for this entity")

        raw = self._to_raw(value)
        registers = self._definition.registers
        if not registers:
            raise HomeAssistantError("No register defined for this number")
        address = registers[0]

        client = self.coordinator.hass.data[DOMAIN][self._entry_id]["client"]
        try:
            await client.async_write_register(address, raw)
            _LOGGER.info(
                "Wrote number %s (value=%s -> raw=%s) to register %s",
                self.entity_description.key,
                value,
                raw,
                address,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to write number %s (value=%s -> raw=%s) to register %s: %s",
                self.entity_description.key,
                value,
                raw,
                address,
                err,
            )
            raise HomeAssistantError(f"Failed to write: {err}") from err

        # Read-after-write verification
        try:
            read_result = await client.async_read_holding_registers(address, 1)
            if read_result.isError():
                _LOGGER.warning(
                    "Failed to verify write for %s at register %s: %s",
                    self.entity_description.key,
                    address,
                    read_result,
                )
            else:
                read_value = read_result.registers[0]
                if read_value != raw:
                    _LOGGER.error(
                        "Write verification FAILED for %s: wrote %s but read back %s (register %s)",
                        self.entity_description.key,
                        raw,
                        read_value,
                        address,
                    )
                    raise HomeAssistantError(
                        f"Write verification failed: wrote {raw} but read back {read_value}"
                    )
                else:
                    _LOGGER.debug(
                        "Write verification OK for %s: value %s confirmed at register %s",
                        self.entity_description.key,
                        raw,
                        address,
                    )
        except HomeAssistantError:
            # Re-raise verification failures
            raise
        except Exception as err:  # noqa: BLE001
            # Log verification errors but don't fail the write
            _LOGGER.warning(
                "Exception during write verification for %s: %s",
                self.entity_description.key,
                err,
            )

        await self.coordinator.async_request_refresh()

    def _to_raw(self, value: Any) -> int:
        """Convert native value to raw register value applying inverse scale."""
        try:
            val = float(value)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Invalid number value: {value}") from err

        # Validate bounds before scaling
        range_min = getattr(self._definition, "range_min", None)
        range_max = getattr(self._definition, "range_max", None)

        if range_min is not None and val < range_min:
            raise HomeAssistantError(
                f"Value {val} is below minimum allowed value {range_min}"
            )
        if range_max is not None and val > range_max:
            raise HomeAssistantError(
                f"Value {val} is above maximum allowed value {range_max}"
            )

        scale = self._definition.scale
        if isinstance(scale, (int, float)) and scale:
            val = val / scale
        # For list scales (e.g., [1,10]) we only used first element on decode; invert similarly
        elif isinstance(scale, list) and scale:
            factor = scale[0]
            if len(scale) >= 2 and scale[1]:
                factor = factor / scale[1]
            val = val / factor

        raw_value = int(round(val))

        # Additional safety check: ensure raw value fits in 16-bit register
        if raw_value < 0 or raw_value > 65535:
            raise HomeAssistantError(
                f"Converted value {raw_value} is out of valid register range (0-65535)"
            )

        return raw_value


def _build_base_name(entry_data: dict) -> str:
    if host := entry_data.get(CONF_HOST):
        port = entry_data.get(CONF_PORT)
        base = f"Deye Inverter ({host}:{port})" if port else f"Deye Inverter ({host})"
    elif device := entry_data.get(CONF_DEVICE):
        base = f"Deye Inverter ({device})"
    else:
        base = "Deye Inverter"
    return base


def _base_device(entry_id: str, entry_data: dict) -> dict:
    return {
        "identifiers": {(DOMAIN, entry_id)},
        "manufacturer": "Deye",
        "name": _build_base_name(entry_data),
        "configuration_url": _build_config_url(entry_data),
    }


def _device_for_group(item: DefinitionItem, entry_id: str, base: dict) -> dict:
    group = (item.group_name or "").strip()
    if not group:
        return base
    return {
        "identifiers": {(DOMAIN, f"{entry_id}_{group}")},
        "manufacturer": base.get("manufacturer"),
        "name": f"{base.get('name')} - {group}",
        "via_device": (DOMAIN, entry_id),
        "configuration_url": base.get("configuration_url"),
    }


def _build_config_url(entry_data: dict) -> str | None:
    if host := entry_data.get(CONF_HOST):
        return f"http://{host}"
    return None


def _description_for(item: DefinitionItem) -> NumberEntityDescription | None:
    """Map definition item to a number description (read-only)."""
    native_unit = None
    if item.unit in ("A", "a"):
        native_unit = UnitOfElectricCurrent.AMPERE
    elif item.unit in ("W", "w"):
        native_unit = UnitOfPower.WATT
    elif item.unit in ("kWh", "kwh"):
        native_unit = UnitOfEnergy.KILO_WATT_HOUR

    fallback_unit = native_unit or item.unit

    return NumberEntityDescription(
        key=item.key,
        name=item.name,
        native_unit_of_measurement=fallback_unit,
        native_min_value=item.range_min if hasattr(item, "range_min") else None,
        native_max_value=item.range_max if hasattr(item, "range_max") else None,
        native_step=1,
        icon=item.icon,
    )
