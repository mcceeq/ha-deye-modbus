"""Time entities driven by external definitions (writes allowed for ToU program times)."""

from __future__ import annotations

import datetime
from typing import Any
import logging

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE
from .definition_loader import DefinitionItem

_LOGGER = logging.getLogger(__name__)

# Keys allowed to perform writes (ToU program times)
_WRITABLE_TIME_KEYS = {
    "program_1_time",
    "program_2_time",
    "program_3_time",
    "program_4_time",
    "program_5_time",
    "program_6_time",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up time entities from definitions."""
    defs = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not defs:
        return

    coordinator = defs["coordinator"]
    items: list[DefinitionItem] = defs["items"]

    base_device_info = _base_device(entry.entry_id, entry.data)

    entities: list[DeyeDefinitionTime] = []
    for item in items:
        if item.platform != "time":
            continue
        desc = TimeEntityDescription(
            key=item.key,
            name=item.name,
            icon=item.icon,
            entity_category=EntityCategory.CONFIG,
        )
        entities.append(
            DeyeDefinitionTime(
                coordinator=coordinator,
                description=desc,
                entry_id=entry.entry_id,
                definition=item,
                device_info=_device_for_group(item, entry.entry_id, base_device_info),
            )
        )

    if entities:
        async_add_entities(entities)


class DeyeDefinitionTime(CoordinatorEntity, TimeEntity):
    """Time entity driven by external definition (read-only)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator,
        description: TimeEntityDescription,
        entry_id: str,
        definition: DefinitionItem,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_def_time_{description.key}"
        self._attr_device_info = device_info
        self._entry_id = entry_id
        self._definition = definition

    @property
    def native_value(self) -> datetime.time | None:
        val = self.coordinator.data.get(self.entity_description.key)
        if isinstance(val, datetime.time):
            return val
        return None

    async def async_set_value(self, value: datetime.time) -> None:
        if self.entity_description.key not in _WRITABLE_TIME_KEYS:
            raise HomeAssistantError("Writes not implemented for this entity")

        registers = self._definition.registers
        if not registers:
            raise HomeAssistantError("No register defined for this time")
        address = registers[0]

        try:
            raw = value.hour * 100 + value.minute
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Invalid time value: {value}") from err

        client = self.coordinator.hass.data[DOMAIN][self._entry_id]["client"]
        try:
            await client.async_write_register(address, raw)
            _LOGGER.info(
                "Wrote time %s (value=%s -> raw=%s) to register %s",
                self.entity_description.key,
                value,
                raw,
                address,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to write time %s (value=%s -> raw=%s) to register %s: %s",
                self.entity_description.key,
                value,
                raw,
                address,
                err,
            )
            raise HomeAssistantError(f"Failed to write: {err}") from err

        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {
            "value": self.native_value,
            "device_class": "time",
        }


def _build_base_name(entry_data: dict) -> str:
    if host := entry_data.get(CONF_HOST):
        port = entry_data.get(CONF_PORT)
        return f"Deye Inverter ({host}:{port})" if port else f"Deye Inverter ({host})"
    if device := entry_data.get(CONF_DEVICE):
        return f"Deye Inverter ({device})"
    return "Deye Inverter"


def _build_config_url(entry_data: dict) -> str | None:
    if host := entry_data.get(CONF_HOST):
        return f"http://{host}"
    return None


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
