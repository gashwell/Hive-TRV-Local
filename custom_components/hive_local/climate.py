"""Climate platform — individual TRV/receiver entities and room entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR, DEVICE_TYPE_RECEIVER, DEVICE_TYPE_TRV, DOMAIN,
    MAX_TEMP, MIN_TEMP, MODE_BOOST, MODE_MANUAL, MODE_OFF, MODE_SCHEDULE,
    TEMP_STEP, uid_device, uid_room,
)
from .coordinator import HiveLocalCoordinator
from .mqtt import HiveDeviceMqtt
from .room import HiveRoom

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HiveLocalCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[ClimateEntity] = []

    # Device entities (TRV and receiver)
    for device_id, device_data in coordinator.store.get_all_devices().items():
        dtype = device_data.get("type")
        if dtype in (DEVICE_TYPE_TRV, DEVICE_TYPE_RECEIVER):
            mqtt = coordinator.get_device_mqtt(device_id)
            if mqtt:
                entities.append(HiveDeviceClimate(coordinator, device_id, mqtt, device_data))

    # Room entities
    for room_id, room in coordinator.all_rooms().items():
        entities.append(HiveRoomClimate(coordinator, room_id, room))

    async_add_entities(entities)

    # Listen for runtime additions
    @callback
    def _on_device_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        device_id   = event.data.get("device_id")
        device_data = event.data.get("data", {})
        dtype = device_data.get("type")
        if dtype in (DEVICE_TYPE_TRV, DEVICE_TYPE_RECEIVER):
            mqtt = coordinator.get_device_mqtt(device_id)
            if mqtt:
                async_add_entities([HiveDeviceClimate(coordinator, device_id, mqtt, device_data)])

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id = event.data.get("room_id")
        room    = event.data.get("room")
        if room:
            async_add_entities([HiveRoomClimate(coordinator, room_id, room)])

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_device_added", _on_device_added))
    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_added",   _on_room_added))


# ── Device climate entity ──────────────────────────────────────────────────────

class HiveDeviceClimate(ClimateEntity):
    """Individual TRV or receiver climate entity."""

    _attr_temperature_unit        = UnitOfTemperature.CELSIUS
    _attr_min_temp                = MIN_TEMP
    _attr_max_temp                = MAX_TEMP
    _attr_target_temperature_step = TEMP_STEP
    _attr_has_entity_name         = True

    def __init__(
        self,
        coordinator: HiveLocalCoordinator,
        device_id: str,
        mqtt: HiveDeviceMqtt,
        device_data: dict,
    ) -> None:
        self._coordinator  = coordinator
        self._device_id    = device_id
        self._mqtt         = mqtt
        self._device_data  = device_data
        self._attr_unique_id = uid_device(device_id, "climate")
        self._attr_name      = device_data.get("name", device_id)

        dtype = device_data.get("type")
        if dtype == DEVICE_TYPE_TRV:
            self._attr_hvac_modes        = [HVACMode.HEAT, HVACMode.OFF]
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
            )
        else:
            # Receiver supports auto (schedule) mode
            self._attr_hvac_modes        = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF]
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
            )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_data.get("name", self._device_id),
            model=self._device_data.get("model", self._device_data.get("type", "TRV")),
            manufacturer="Hive",
        )

    async def async_added_to_hass(self) -> None:
        self._mqtt.add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._mqtt.available

    @property
    def current_temperature(self) -> float | None:
        return self._mqtt.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self._mqtt.target_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        return self._mqtt.hvac_mode

    @property
    def hvac_action(self) -> HVACAction | None:
        return self._mqtt.hvac_action

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        if self._mqtt.battery is not None:
            attrs["battery"] = self._mqtt.battery
        if self._mqtt.pi_heating_demand is not None:
            attrs["pi_heating_demand"] = self._mqtt.pi_heating_demand
        if self._mqtt.local_temp_calibration is not None:
            attrs["local_temperature_calibration"] = self._mqtt.local_temp_calibration
        if self._mqtt.heat_boost_active:
            attrs["boost_remaining_minutes"] = self._mqtt.heat_boost_remaining
        # Receiver link — used by panel card
        recv_id = self._coordinator.store.get_device_receiver(self._device_id)
        if recv_id:
            recv_data = self._coordinator.store.get_device(recv_id) or {}
            attrs["receiver_name"] = recv_data.get("name", recv_id)
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp:
            await self._mqtt.async_set_mode_heat(float(temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._mqtt.async_set_mode_off()
        elif hvac_mode == HVACMode.AUTO:
            await self._mqtt.async_set_mode_schedule()
        elif hvac_mode == HVACMode.HEAT:
            temp = self._mqtt.target_temperature or 20.0
            await self._mqtt.async_set_mode_heat(temp)

    async def async_turn_on(self)  -> None: await self.async_set_hvac_mode(HVACMode.HEAT)
    async def async_turn_off(self) -> None: await self.async_set_hvac_mode(HVACMode.OFF)


# ── Room climate entity ────────────────────────────────────────────────────────

_ROOM_PRESETS  = [MODE_SCHEDULE, MODE_MANUAL, MODE_BOOST]
_ROOM_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


class HiveRoomClimate(ClimateEntity):
    """Virtual climate entity for a heating room."""

    _attr_temperature_unit        = UnitOfTemperature.CELSIUS
    _attr_hvac_modes              = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp                = MIN_TEMP
    _attr_max_temp                = MAX_TEMP
    _attr_target_temperature_step = TEMP_STEP
    _attr_has_entity_name         = True
    _attr_supported_features      = _ROOM_FEATURES

    def __init__(
        self,
        coordinator: HiveLocalCoordinator,
        room_id: str,
        room: HiveRoom,
    ) -> None:
        self._coordinator  = coordinator
        self._room_id      = room_id
        self._room         = room
        self._attr_unique_id = uid_room(room_id, "climate")
        self._attr_name      = room.room_name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self._room_id}")},
            name=self._room.room_name,
            model="Heating Room",
            manufacturer="Hive Local",
        )

    async def async_added_to_hass(self) -> None:
        self._room.add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._room.available

    @property
    def current_temperature(self) -> float | None:
        return self._room.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self._room.setpoint

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self._room.mode == MODE_OFF else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        return self._room.hvac_action

    @property
    def preset_modes(self) -> list[str]:
        return _ROOM_PRESETS

    @property
    def preset_mode(self) -> str | None:
        m = self._room.mode
        return None if m == MODE_OFF else m

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "mode":           self._room.mode,
            "member_detail":  self._room.member_detail,
            "member_count":   len(self._room.device_ids),
            "heat_required":  self._room.heat_required,
            "schedule":       self._room.schedule,
        }
        slot = self._room.current_schedule_slot
        if slot:
            attrs["current_schedule_slot"] = slot
        if self._room.mode == MODE_BOOST:
            attrs["boost_remaining_minutes"] = self._room.boost_remaining_minutes
            attrs["boost_ends"]              = self._room.boost_end_iso
        if self._room.outdoor_temperature is not None:
            attrs["outdoor_temperature"]     = self._room.outdoor_temperature
        if self._room.frost_active:
            attrs["frost_protection_active"] = True
        # Receiver name — used by panel card
        if self._room.receiver_device_id:
            recv_data = self._coordinator.store.get_device(self._room.receiver_device_id) or {}
            attrs["receiver_name"] = recv_data.get("name", self._room.receiver_device_id)
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._room.async_set_temperature(float(temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._room.async_set_mode(
            MODE_OFF if hvac_mode == HVACMode.OFF else MODE_MANUAL
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._room.async_set_mode(preset_mode)

    async def async_turn_on(self)  -> None: await self._room.async_set_mode(MODE_MANUAL)
    async def async_turn_off(self) -> None: await self._room.async_set_mode(MODE_OFF)
