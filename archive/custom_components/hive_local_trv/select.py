"""Select platform — keypad lock and mounting orientation."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_HUB, DOMAIN
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from .entity import HiveTRVEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: HiveTRVHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    _e: dict[str, list] = {}

    def _add(coord: HiveTRVCoordinator) -> None:
        if coord.friendly_name not in _e:
            es = [
                HiveKeypadSelect(coord),
                HiveMountingOrientationSelect(coord),
            ]
            _e[coord.friendly_name] = es
            async_add_entities(es)

    def _remove(name: str) -> None:
        for e in _e.pop(name, []):
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("select", _add, _remove)


class HiveKeypadSelect(HiveTRVEntity, SelectEntity):
    """Select keypad lock mode."""

    _attr_name    = "Keypad Lock"
    _attr_icon    = "mdi:lock"
    _attr_options = ["unlock", "lock1", "lock2"]

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "keypad_lockout")

    @property
    def current_option(self) -> str:
        return self.coordinator.data.get("keypad_lockout", "unlock")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_keypad_lockout(option)


class HiveMountingOrientationSelect(HiveTRVEntity, SelectEntity):
    """Select TRV mounting orientation — horizontal or vertical pipe.

    Setting the correct orientation improves the valve's flow control accuracy.
    Sent to Z2M as mounting_mode_control.

    Options:
      auto       — TRV detects orientation automatically (default)
      horizontal — force horizontal (standard radiator pipe)
      vertical   — force vertical (underfloor / vertical riser)
    """

    _attr_name    = "Mounting Orientation"
    _attr_icon    = "mdi:pipe"
    _attr_options = ["auto", "horizontal", "vertical"]

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "mounting_orientation")

    @property
    def current_option(self) -> str:
        return self.coordinator.data.get("mounting_mode_control", "auto")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mounting_orientation(option)
