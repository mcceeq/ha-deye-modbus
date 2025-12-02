"""Number entities for configurable limits (read-only placeholder)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfElectricCurrent

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE

_LOGGER = logging.getLogger(__name__)


NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="battery_max_charge_current_set",
        name="Battery Max Charge Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-dc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=240,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="battery_max_discharge_current_set",
        name="Battery Max Discharge Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-dc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=240,
        native_step=1,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities (read-only placeholders)."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    base_name = _build_base_name(entry.data)
    base_device_info = {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "manufacturer": "Deye",
        "name": base_name,
        "configuration_url": _build_config_url(entry.data),
    }

    entities: list[DeyeNumber] = [
        DeyeNumber(
            coordinator=coordinator,
            description=description,
            entry_id=entry.entry_id,
            base_device_info=base_device_info,
        )
        for description in NUMBER_DESCRIPTIONS
    ]

    async_add_entities(entities)


class DeyeNumber(CoordinatorEntity, NumberEntity):
    """Number entity for inverter limits (no writes yet)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: NumberEntityDescription,
        entry_id: str,
        base_device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = _device_info_for(description.key, entry_id, base_device_info)
        self._attr_mode = description.mode or NumberMode.BOX

    @property
    def native_value(self) -> float | None:
        """Return current value from coordinator."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Reject writes until implemented."""
        _LOGGER.warning("Write not implemented for %s", self.entity_id)
        raise NotImplementedError("Writes not yet implemented")


def _build_base_name(entry_data: dict) -> str:
    """Build a base device name from connection details."""
    if host := entry_data.get(CONF_HOST):
        port = entry_data.get(CONF_PORT)
        return f"Deye Inverter ({host}:{port})" if port else f"Deye Inverter ({host})"
    if device := entry_data.get(CONF_DEVICE):
        return f"Deye Inverter ({device})"
    return "Deye Inverter"


def _build_config_url(entry_data: dict) -> str | None:
    """If a host is provided, offer an http config URL (best effort)."""
    if host := entry_data.get(CONF_HOST):
        return f"http://{host}"
    return None


def _device_info_for(key: str, entry_id: str, base: dict) -> dict:
    """Put numbers under the inverter device."""
    return base
