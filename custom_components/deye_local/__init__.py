"""Home Assistant integration for local Deye Modbus access."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .modbus_client import DeyeModbusClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Deye Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = DeyeModbusClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        slave_id=entry.data[CONF_SLAVE_ID],
    )

    try:
        await client.async_setup()
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to inverter: {err}") from err

    async def _async_update_data() -> dict[str, Any]:
        """Fetch data from the inverter."""
        try:
            return await client.async_read_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="deye_local",
        update_method=_async_update_data,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    stored = hass.data[DOMAIN].pop(entry.entry_id, {})
    client: DeyeModbusClient | None = stored.get("client")

    if client:
        await client.async_close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
