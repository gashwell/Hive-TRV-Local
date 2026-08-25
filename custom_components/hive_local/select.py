"""Select platform for Hive Local — heating mode only.

Hot water (SLR2) mode selection removed — not applicable for ZBMINIR2 solution.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import HiveConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HiveConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities — none for heating-only configuration."""
