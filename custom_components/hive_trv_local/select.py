"""Select platform — water mode for SLR2 receivers."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_RECEIVER, MODEL_SLR2,
)
from .coordinator import HiveDeviceCoordinator
from .entity import HiveDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if entry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_RECEIVER:
        return
    coordinator: HiveDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if coordinator.model != MODEL_SLR2:
        return

    show_sched = entry.data.get("show_water_schedule_mode", True)
    options    = ["auto", "heat", "off", "boost"] if show_sched else ["heat", "off", "boost"]
    async_add_entities([HiveWaterModeSelect(coordinator, options)])


class HiveWaterModeSelect(HiveDeviceEntity, SelectEntity, RestoreEntity):
    """Water mode select entity for SLR2 receivers."""

    def __init__(self, coordinator: HiveDeviceCoordinator, options: list[str]) -> None:
        super().__init__(coordinator)
        self._attr_unique_id     = f"{DOMAIN}_{coordinator.entry_id}_water_mode"
        self._attr_name          = f"{coordinator.device_name} Water Mode"
        self._attr_options       = options
        self._attr_current_option= None
        self._attr_icon          = "mdi:water-boiler"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if ls := await self.async_get_last_state():
            self._attr_current_option = ls.state

    def _handle_coordinator_update(self) -> None:
        mode = self.coordinator.water_mode
        if mode in self._attr_options:
            self._attr_current_option = mode
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        if option == "auto":
            await self.coordinator.async_water_scheduled()
        elif option == "heat":
            await self.coordinator.async_water_always_on()
        elif option == "boost":
            await self.coordinator.async_water_boost()
        elif option == "off":
            await self.coordinator.async_water_always_off()
        self.async_write_ha_state()
