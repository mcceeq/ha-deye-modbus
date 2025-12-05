"""Loader for external YAML definitions (read-only subset)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Local overrides for definition quirks without touching the YAML file
_ITEM_OVERRIDES: dict[str, dict[str, Any]] = {
    # Solarman exposes Meter (0x0146) as a select with three modes
    "meter": {
        "platform": "select",
        "lookup": [
            {"key": 0x0000, "value": "Disabled"},
            {"key": 0x0001, "value": "Enabled"},
            {"key": 0x0002, "value": "Generator"},
        ],
    },
}


@dataclass
class DefinitionItem:
    """Flattened item from the definition."""

    key: str
    name: str
    platform: str
    registers: list[int]
    scale: float | None
    lookup: dict[int, Any] | None
    group: str
    icon: str | None
    unit: str | None
    rule: int | None
    range_min: float | None = None
    range_max: float | None = None
    mask: int | None = None
    divide: float | None = None
    group_name: str | None = None
    offset: float | None = None


def load_definition(def_path: Path) -> list[DefinitionItem]:
    """Load a definition file and return supported items."""
    data = yaml.safe_load(def_path.read_text())
    items: list[DefinitionItem] = []

    params = data.get("parameters", [])
    for group_entry in params:
        group_name = group_entry.get("group", "Unknown")
        for item in group_entry.get("items", []):
            # Skip attribute-only entries to avoid cluttering entities
            if item.get("attribute") is not None:
                continue
            platform = item.get("platform", "sensor")
            rule = item.get("rule")

            # Only support simple sensors/numbers/switch/select/datetime/time at a subset of rules for now
            if rule not in (None, 1, 2, 8, 9):
                continue
            if platform not in ("sensor", "number", "switch", "select", "binary_sensor", "datetime", "time"):
                continue

            registers = item.get("registers") or []
            if not registers:
                continue

            # Normalize register addresses to int
            regs_int = []
            for reg in registers:
                if isinstance(reg, str):
                    regs_int.append(int(reg, 0))
                else:
                    regs_int.append(int(reg))

            name = (item.get("name") or item.get("id") or "").strip()
            if not name:
                continue
            key = _slug(name)

            # Apply any hardcoded overrides (platform/lookup/etc.)
            if key in _ITEM_OVERRIDES:
                override = _ITEM_OVERRIDES[key]
                if "platform" in override:
                    platform = override["platform"]
                if "lookup" in override:
                    item["lookup"] = override["lookup"]

            scale = item.get("scale")
            lookup = _parse_lookup(item.get("lookup"))
            range_min = None
            range_max = None
            if item.get("range"):
                range_min = item["range"].get("min")
                range_max = item["range"].get("max")
            mask = item.get("mask")
            if not mask and item.get("display", {}).get("mask") is not None:
                mask = item["display"]["mask"]
            divide = item.get("divide")
            offset = item.get("offset")
            items.append(
                DefinitionItem(
                    key=key,
                    name=name,
                    platform=platform,
                    registers=regs_int,
                    scale=scale,
                    lookup=lookup,
                    group=group_name,
                    icon=item.get("icon"),
                    unit=item.get("uom"),
                    rule=rule,
                    range_min=range_min,
                    range_max=range_max,
                    mask=int(mask, 0) if isinstance(mask, str) else mask,
                    divide=divide,
                    group_name=group_name,
                    offset=offset,
                )
            )

    return items


def _slug(name: str) -> str:
    """Create a simple slug key."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("&", "and")
    )


def _parse_lookup(lookup_list: Any) -> dict[int, Any] | None:
    """Convert lookup list to dict."""
    if not lookup_list:
        return None
    mapping: dict[int, Any] = {}
    for entry in lookup_list:
        key = entry.get("key")
        val = entry.get("value")
        if key is None:
            continue
        if isinstance(key, list):
            for k in key:
                if k is None:
                    continue
                mapping[int(k)] = val
        else:
            mapping[int(key)] = val
    return mapping
