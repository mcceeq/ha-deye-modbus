"""Number entities driven by definitions (read-only)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE
from .definition_loader import DefinitionItem

# Keys whose availability depends on battery control mode
_LITHIUM_HIDE_KEYS = {
    # Voltage-tuned lead-acid settings that should not apply to lithium
    "battery_equalization",
    "battery_absorption",
    "battery_float",
    "battery_empty",
    "battery_shutdown_voltage",
    "battery_restart_voltage",
    "battery_low_voltage",
    "battery_generator_charging_start_voltage",
    "battery_grid_charging_start_voltage",
}

_SOC_HIDE_KEYS = {
    # SOC thresholds not relevant for lead-acid control
    "battery_shutdown_soc",
    "battery_restart_soc",
    "battery_low_soc",
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
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_def_{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Hide voltage controls when mode is lithium; hide SOC controls when not."""
        if not super().available:
            return False
        data = self.coordinator.data
        mode = data.get("battery_control_mode")
        key = self.entity_description.key
        if mode == "Lithium" and key in _LITHIUM_HIDE_KEYS:
            return False
        if mode and mode != "Lithium" and key in _SOC_HIDE_KEYS:
            return False
        return True

    async def async_set_native_value(self, value):
        raise NotImplementedError("Write not implemented for numbers")


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
