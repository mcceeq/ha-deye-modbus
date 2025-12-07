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

from .const import DOMAIN
from .definition_loader import DefinitionItem
from .device_info import build_base_device, build_device_for_group

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

    base_device_info = build_base_device(entry.entry_id, entry.data)

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
                device_info=build_device_for_group(item, entry.entry_id, base_device_info),
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
            # If a mask is defined, preserve other bits by reading current value first
            if self._definition.mask:
                rr = await client.async_read_holding_registers(address, 1)
                if rr.isError():
                    raise HomeAssistantError(f"Failed to read before write: {rr}")
                current = rr.registers[0]
                masked = (current & ~self._definition.mask) | (value & self._definition.mask)
                value_to_write = masked
            else:
                value_to_write = value

            await client.async_write_register(address, value_to_write)
            _LOGGER.info(
                "Wrote select %s (option=%s -> value=%s) to register %s (masked=%s)",
                self.entity_description.key,
                option,
                value_to_write,
                address,
                self._definition.mask,
            )

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
                    # For masked writes, verify the masked bits match
                    if self._definition.mask:
                        expected = value_to_write & self._definition.mask
                        actual = read_value & self._definition.mask
                        if actual != expected:
                            _LOGGER.error(
                                "Write verification FAILED for %s: wrote masked value %s but read back %s (register %s, mask %s)",
                                self.entity_description.key,
                                expected,
                                actual,
                                address,
                                self._definition.mask,
                            )
                            raise HomeAssistantError(
                                f"Write verification failed: wrote {expected} but read back {actual}"
                            )
                    else:
                        if read_value != value_to_write:
                            _LOGGER.error(
                                "Write verification FAILED for %s: wrote %s but read back %s (register %s)",
                                self.entity_description.key,
                                value_to_write,
                                read_value,
                                address,
                            )
                            raise HomeAssistantError(
                                f"Write verification failed: wrote {value_to_write} but read back {read_value}"
                            )
                    _LOGGER.debug(
                        "Write verification OK for %s: option '%s' confirmed at register %s",
                        self.entity_description.key,
                        option,
                        address,
                    )
            except HomeAssistantError:
                # Re-raise verification failures
                raise
            except Exception as verify_err:  # noqa: BLE001
                # Log verification errors but don't fail the write
                _LOGGER.warning(
                    "Exception during write verification for %s: %s",
                    self.entity_description.key,
                    verify_err,
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
