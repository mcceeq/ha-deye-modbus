"""Datetime entities driven by external definitions (read-only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.datetime import DateTimeEntity, DateTimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .definition_loader import DefinitionItem
from .device_info import build_base_device, build_device_for_group


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up datetime entities from definitions."""
    defs = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not defs:
        return

    coordinator = defs["coordinator"]
    items: list[DefinitionItem] = defs["items"]

    base_device_info = build_base_device(entry.entry_id, entry.data)

    entities: list[DeyeDefinitionDateTime] = []
    for item in items:
        if item.platform != "datetime":
            continue
        desc = DateTimeEntityDescription(
            key=item.key,
            name=item.name,
            icon=item.icon,
            entity_category=EntityCategory.CONFIG,
        )
        entities.append(
            DeyeDefinitionDateTime(
                coordinator=coordinator,
                description=desc,
                entry_id=entry.entry_id,
                device_info=build_device_for_group(item, entry.entry_id, base_device_info),
            )
        )

    if entities:
        async_add_entities(entities)


class DeyeDefinitionDateTime(CoordinatorEntity, DateTimeEntity):
    """Datetime entity driven by external definition (read-only)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator,
        description: DateTimeEntityDescription,
        entry_id: str,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_def_datetime_{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> datetime | None:
        val = self.coordinator.data.get(self.entity_description.key)
        if isinstance(val, datetime):
            if val.tzinfo is None:
                # attach default HA timezone if missing
                from homeassistant.util import dt as dt_util
                return val.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return val
        return None

    async def async_set_value(self, value: datetime) -> None:
        raise NotImplementedError("Writes not implemented for datetime entities")
