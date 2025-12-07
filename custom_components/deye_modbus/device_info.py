"""Shared device info utilities for entity platforms."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE
from .definition_loader import DefinitionItem


def build_base_name(entry_data: dict) -> str:
    """Build a human-readable name for the base device."""
    if host := entry_data.get(CONF_HOST):
        port = entry_data.get(CONF_PORT)
        base = f"Deye Inverter ({host}:{port})" if port else f"Deye Inverter ({host})"
    elif device := entry_data.get(CONF_DEVICE):
        base = f"Deye Inverter ({device})"
    else:
        base = "Deye Inverter"
    return base


def build_config_url(entry_data: dict) -> str | None:
    """Build configuration URL for TCP connections."""
    if host := entry_data.get(CONF_HOST):
        return f"http://{host}"
    return None


def build_base_device(entry_id: str, entry_data: dict) -> dict[str, Any]:
    """Build device info dict for the base inverter device."""
    return {
        "identifiers": {(DOMAIN, entry_id)},
        "manufacturer": "Deye",
        "name": build_base_name(entry_data),
        "configuration_url": build_config_url(entry_data),
    }


def build_device_for_group(
    item: DefinitionItem, entry_id: str, base: dict[str, Any]
) -> dict[str, Any]:
    """Build device info for a grouped sub-device (e.g., Battery, Grid, etc.)."""
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
