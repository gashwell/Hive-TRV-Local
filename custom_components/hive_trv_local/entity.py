"""Base entity class for Hive TRV Local device entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HiveDeviceCoordinator


class HiveDeviceEntity(CoordinatorEntity[HiveDeviceCoordinator]):
    """Base class for all per-device entities (TRV or receiver)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry_id)},
            name=coordinator.device_name,
            model=coordinator.model,
            manufacturer="Hive",
        )
