"""Shared base entity."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HiveTRVCoordinator


class HiveTRVEntity(CoordinatorEntity[HiveTRVCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveTRVCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.ieee_address)},
            name=coordinator.friendly_name,
            manufacturer="Hive",
            model="UK7004240",
            sw_version=coordinator.device_info.get("software_build_id"),
        )
