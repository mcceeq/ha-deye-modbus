"""Switch entities driven by external definitions (read-only)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .definition_loader import DefinitionItem
from .device_info import build_base_device, build_device_for_group


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch entities from definitions."""
    defs = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not defs:
        return

    coordinator = defs["coordinator"]
    items: list[DefinitionItem] = defs["items"]

    base_device_info = build_base_device(entry.entry_id, entry.data)

    entities: list[DeyeDefinitionSwitch] = []
    for item in items:
        if item.platform != "switch":
            continue
        desc = SwitchEntityDescription(
            key=item.key,
            name=item.name,
            icon=item.icon,
            entity_category=EntityCategory.CONFIG,
        )
        entities.append(
            DeyeDefinitionSwitch(
                coordinator=coordinator,
                description=desc,
                entry_id=entry.entry_id,
                device_info=build_device_for_group(item, entry.entry_id, base_device_info),
            )
        )

    if entities:
        async_add_entities(entities)


class DeyeDefinitionSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity driven by external definition (read-only)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        description: SwitchEntityDescription,
        entry_id: str,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_def_switch_{description.key}"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        val = self.coordinator.data.get(self.entity_description.key)
        if val is None:
            return None
        if isinstance(val, str):
            return val.lower() in ("on", "true", "1")
        try:
            return bool(int(val))
        except Exception:
            return bool(val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        raise NotImplementedError("Writes not implemented for switch entities")

    async def async_turn_off(self, **kwargs: Any) -> None:
        raise NotImplementedError("Writes not implemented for switch entities")
