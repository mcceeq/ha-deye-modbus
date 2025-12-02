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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up definition-driven numbers if available."""
    sol = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not sol:
        return

    coordinator = sol["coordinator"]
    items: list[DefinitionItem] = sol["items"]

    base_device_info = {
        "identifiers": {(DOMAIN, f"{entry.entry_id}_new")},
        "manufacturer": "Deye",
        "name": _build_base_name(entry.data, suffix="(new)"),
        "configuration_url": _build_config_url(entry.data),
    }

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
                device_info=base_device_info,
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

    async def async_set_native_value(self, value):
        raise NotImplementedError("Write not implemented for numbers")


def _build_base_name(entry_data: dict, suffix: str = "") -> str:
    if host := entry_data.get(CONF_HOST):
        port = entry_data.get(CONF_PORT)
        base = f"Deye Inverter ({host}:{port})" if port else f"Deye Inverter ({host})"
    elif device := entry_data.get(CONF_DEVICE):
        base = f"Deye Inverter ({device})"
    else:
        base = "Deye Inverter"
    return base


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

    return NumberEntityDescription(
        key=item.key,
        name=item.name,
        native_unit_of_measurement=native_unit,
        native_min_value=item.range_min if hasattr(item, "range_min") else None,
        native_max_value=item.range_max if hasattr(item, "range_max") else None,
        native_step=1,
        icon=item.icon,
    )
