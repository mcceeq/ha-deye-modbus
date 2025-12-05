"""Select entities driven by external definitions (read/write for limited keys)."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE
from .definition_loader import DefinitionItem

_LOGGER = logging.getLogger(__name__)

# Keys allowed to perform writes (single-register selects)
_WRITABLE_SELECT_KEYS = {
    "time_of_use",
    "program_1_charging",
    "program_2_charging",
    "program_3_charging",
    "program_4_charging",
    "program_5_charging",
    "program_6_charging",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select entities from definitions."""
    defs = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not defs:
        return

    coordinator = defs["coordinator"]
    items: list[DefinitionItem] = defs["items"]

    base_device_info = _base_device(entry.entry_id, entry.data)

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
                definition=item,
                device_info=_device_for_group(item, entry.entry_id, base_device_info),
            )
        )

    if entities:
        async_add_entities(entities)


class DeyeDefinitionSelect(CoordinatorEntity, SelectEntity):
    """Select entity driven by external definition (writes supported for whitelisted keys)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: SelectEntityDescription,
        entry_id: str,
        definition: DefinitionItem,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_def_select_{description.key}"
        self._attr_device_info = device_info
        self._entry_id = entry_id
        self._definition = definition

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {
            "value": self.current_option,
            "device_class": "enum",
        }

    async def async_select_option(self, option: str) -> None:
        # Only allow writes for a small set of single-register selects
        if self.entity_description.key not in _WRITABLE_SELECT_KEYS:
            raise HomeAssistantError("Writes not implemented for this entity")

        if not self._definition.lookup:
            raise HomeAssistantError("No lookup defined for this select")

        # Map option back to numeric key
        reverse = {v: k for k, v in self._definition.lookup.items()}
        if option not in reverse:
            raise HomeAssistantError(f"Invalid option: {option}")
        value = reverse[option]

        registers = self._definition.registers
        if not registers:
            raise HomeAssistantError("No register defined for this select")
        address = registers[0]

        client = self.coordinator.hass.data[DOMAIN][self._entry_id]["client"]
        try:
            await client.async_write_register(address, value)
            _LOGGER.info(
                "Wrote select %s (option=%s -> value=%s) to register %s",
                self.entity_description.key,
                option,
                value,
                address,
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to write select %s (option=%s -> value=%s) to register %s: %s",
                self.entity_description.key,
                option,
                value,
                address,
                err,
            )
            raise HomeAssistantError(f"Failed to write: {err}") from err

        await self.coordinator.async_request_refresh()


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
