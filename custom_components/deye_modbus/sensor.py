"""Dynamic sensors driven by definitions (read-only)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE
from .definition_loader import DefinitionItem


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up definition-driven sensors if available."""
    sol = hass.data[DOMAIN][entry.entry_id].get("definitions")
    if not sol:
        return

    coordinator = sol["coordinator"]
    items: list[DefinitionItem] = sol["items"]

    base_device_info = {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "manufacturer": "Deye",
        "name": _build_base_name(entry.data),
        "configuration_url": _build_config_url(entry.data),
    }

    entities: list[CoordinatorEntity] = []

    for item in items:
        if item.platform != "sensor":
            continue

        desc = _description_for(item)
        if not desc:
            continue

        entities.append(
            DeyeDefinitionSensor(
                coordinator=coordinator,
                description=desc,
                entry_id=entry.entry_id,
                device_info=base_device_info,
            )
        )

    if entities:
        async_add_entities(entities)


class DeyeDefinitionSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity driven by external definition."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: SensorEntityDescription,
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


def _build_base_name(entry_data: dict) -> str:
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


def _description_for(item: DefinitionItem) -> SensorEntityDescription | None:
    """Map definition item to a sensor description (read-only)."""
    unit = item.unit
    dev_class = None
    state_class = None
    native_unit = None

    if unit in ("W", "w"):
        native_unit = UnitOfPower.WATT
        dev_class = SensorDeviceClass.POWER
        state_class = SensorStateClass.MEASUREMENT
    elif unit in ("V", "v"):
        native_unit = UnitOfElectricPotential.VOLT
        dev_class = SensorDeviceClass.VOLTAGE
        state_class = SensorStateClass.MEASUREMENT
    elif unit in ("A", "a"):
        native_unit = UnitOfElectricCurrent.AMPERE
        dev_class = SensorDeviceClass.CURRENT
        state_class = SensorStateClass.MEASUREMENT
    elif unit in ("Hz", "hz"):
        native_unit = UnitOfFrequency.HERTZ
        dev_class = SensorDeviceClass.FREQUENCY
        state_class = SensorStateClass.MEASUREMENT
    elif unit in ("kWh", "kwh"):
        native_unit = UnitOfEnergy.KILO_WATT_HOUR
        dev_class = SensorDeviceClass.ENERGY
        state_class = SensorStateClass.TOTAL_INCREASING
    elif unit in ("C", "°C", "c"):
        native_unit = UnitOfTemperature.CELSIUS
        dev_class = SensorDeviceClass.TEMPERATURE
        state_class = SensorStateClass.MEASUREMENT

    return SensorEntityDescription(
        key=item.key,
        name=item.name,
        native_unit_of_measurement=native_unit,
        device_class=dev_class,
        state_class=state_class,
        icon=item.icon,
    )
