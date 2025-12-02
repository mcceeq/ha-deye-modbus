"""Select entities driven by external definitions (read-only)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE
from .definition_loader import DefinitionItem


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select entities from definitions."""
    defs = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not defs:
        return

    coordinator = defs["coordinator"]
    items: list[DefinitionItem] = defs["items"]

    base_device_info = {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "manufacturer": "Deye",
        "name": _build_base_name(entry.data),
        "configuration_url": _build_config_url(entry.data),
    }

    entities: list[DeyeDefinitionSelect] = []
    for item in items:
        if item.platform != "select":
            continue
        desc = _description_for(item)
        if not desc:
            continue
        entities.append(
            DeyeDefinitionSelect(
                coordinator=coordinator,
                description=desc,
                entry_id=entry.entry_id,
                device_info=base_device_info,
            )
        )

    if entities:
        async_add_entities(entities)


class DeyeDefinitionSelect(CoordinatorEntity, SelectEntity):
    """Select entity driven by external definition (read-only)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: SelectEntityDescription,
        entry_id: str,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_def_select_{description.key}"
        self._attr_device_info = device_info

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.get(self.entity_description.key)

    async def async_select_option(self, option: str) -> None:
        raise NotImplementedError("Writes not implemented for select entities")


def _description_for(item: DefinitionItem) -> SelectEntityDescription | None:
    """Map definition item to a select description."""
    if not item.lookup:
        return None
    options = list(dict.fromkeys(item.lookup.values()))
    return SelectEntityDescription(
        key=item.key,
        name=item.name,
        icon=item.icon,
        options=options,
    )


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
