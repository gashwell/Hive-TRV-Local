"""Per-device MQTT coordinator for Hive TRVs and receivers.

Subscribes to a single Z2M MQTT topic and maintains device state.
Based on andrew-codechimp/HA-Hive-Local-Thermostat with adaptations.
"""
from __future__ import annotations

import json
import logging
from asyncio import sleep
from datetime import datetime
from typing import Any

from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.components.mqtt import client as mqtt_client
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .const import (
    DEFAULT_FROST_TEMP, DEFAULT_HEATING_BOOST_MINS, DEFAULT_HEATING_BOOST_TEMP,
    DEFAULT_WATER_BOOST_MINS, DOMAIN, ENTRY_TYPE_TRV, HIVE_BOOST,
    MAXIMUM_BOOST_MINUTES, MODEL_SLR2,
)

_LOGGER = logging.getLogger(__name__)

BOOST_ERROR = 65000


class HiveDeviceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """MQTT coordinator for a single Hive TRV or receiver device."""

    # ── State ──────────────────────────────────────────────────────────────────
    current_temperature:  float | None = None
    target_temperature:   float | None = None
    hvac_mode:            HVACMode | None = None
    hvac_action:          HVACAction | None = None
    water_mode:           str | None = None
    running_state_heat:   str = ""
    running_state_water:  str = ""
    heat_boost:           bool = False
    water_boost:          bool = False
    heat_boost_remaining: int = 0
    water_boost_remaining:int = 0
    heat_boost_started:   datetime | None = None
    water_boost_started:  datetime | None = None
    heat_boost_started_duration:  int = 0
    water_boost_started_duration: int = 0
    pre_boost_hvac_mode:  HVACMode | None = None
    pre_boost_target_temp:float | None = None
    pre_boost_water_mode: str | None = None

    # ── Number entity values (restored by RestoreNumber) ──────────────────────
    heating_boost_duration:    float = DEFAULT_HEATING_BOOST_MINS
    heating_boost_temperature: float = DEFAULT_HEATING_BOOST_TEMP
    heating_frost_prevention:  float = DEFAULT_FROST_TEMP
    water_boost_duration:      float = DEFAULT_WATER_BOOST_MINS

    # ── Battery / demand (TRV only) ───────────────────────────────────────────
    battery:          int | None = None
    pi_heating_demand:int | None = None

    # ── Diagnostics ───────────────────────────────────────────────────────────
    last_mqtt_payload: dict[str, Any] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        device_type: str,
        model: str,
        topic: str,
        device_name: str,
        show_heat_schedule: bool = True,
        show_water_schedule: bool = True,
    ) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry_id}")
        self.entry_id           = entry_id
        self.device_type        = device_type  # ENTRY_TYPE_TRV or ENTRY_TYPE_RECEIVER
        self.model              = model
        self.topic              = topic
        self.device_name        = device_name
        self.show_heat_schedule = show_heat_schedule
        self.show_water_schedule= show_water_schedule
        self.data: dict[str, Any] = {}

    @property
    def topic_get(self) -> str:
        return self.topic + "/get"

    @property
    def topic_set(self) -> str:
        return self.topic + "/set"

    @property
    def is_trv(self) -> bool:
        return self.device_type == ENTRY_TYPE_TRV

    # ── MQTT message handling ──────────────────────────────────────────────────

    @callback
    def handle_mqtt_message(self, message: ReceiveMessage) -> None:
        """Parse incoming Z2M payload and update state."""
        payload = message.payload
        if not payload:
            _LOGGER.error("Empty MQTT payload on %s", message.topic)
            return

        try:
            data: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError:
            _LOGGER.error("Bad JSON on %s: %s", message.topic, payload)
            return

        _LOGGER.debug("MQTT %s: %s", self.topic, data)
        self.last_mqtt_payload = data

        # Reset volatile state
        self.current_temperature  = None
        self.target_temperature   = None
        self.hvac_mode            = None
        self.heat_boost           = False
        self.water_boost          = False
        self.water_mode           = None

        try:
            if self.is_trv:
                self._parse_trv(data)
            elif self.model == MODEL_SLR2:
                self._parse_slr2(data)
            else:
                self._parse_slr1(data)
        except Exception as exc:
            _LOGGER.error("Error parsing MQTT payload for %s: %s", self.topic, exc)
            return

        self.async_set_updated_data(data)

    def _parse_trv(self, data: dict) -> None:
        """Parse TRV (UK7004240 etc) payload."""
        self.current_temperature = data.get("local_temperature") or data.get("current_heating_setpoint")
        self.target_temperature  = data.get("occupied_heating_setpoint") or data.get("current_heating_setpoint")
        self.battery             = data.get("battery")
        self.pi_heating_demand   = data.get("pi_heating_demand")

        rs = data.get("running_state", "")
        self.running_state_heat  = rs if rs else "idle"

        sm = data.get("system_mode", "heat")
        if sm == "off":
            self.hvac_mode   = HVACMode.OFF
            self.hvac_action = HVACAction.OFF
        else:
            self.hvac_mode   = HVACMode.HEAT
            self.hvac_action = HVACAction.HEATING if self.running_state_heat == "heat" else HVACAction.IDLE

    def _parse_slr1(self, data: dict) -> None:
        """Parse SLR1/OTR1 payload."""
        self.current_temperature = data.get("local_temperature")

        raw_sp = data.get("occupied_heating_setpoint")
        self.target_temperature  = self.heating_frost_prevention if raw_sp == 1 else raw_sp

        rs = data.get("running_state", "")
        self.running_state_heat  = rs if rs else "preheating"

        if self.running_state_heat == "heat":
            self.hvac_action = HVACAction.HEATING
        elif self.running_state_heat == "idle":
            self.hvac_action = HVACAction.IDLE
        else:
            self.hvac_action = HVACAction.PREHEATING

        sm = data.get("system_mode", "heat")
        hold = data.get("temperature_setpoint_hold", False)

        if sm == "off":
            self.hvac_mode = HVACMode.OFF
        elif sm == HIVE_BOOST:
            self.hvac_mode  = HVACMode.HEAT
            self.heat_boost = True
        elif sm == "heat":
            if not hold and self.show_heat_schedule:
                self.hvac_mode = HVACMode.AUTO
            else:
                self.hvac_mode = HVACMode.HEAT

        if sm != HIVE_BOOST:
            self.pre_boost_hvac_mode   = self.hvac_mode
            self.pre_boost_target_temp = self.target_temperature

        boost_remaining = data.get("temperature_setpoint_hold_duration", 0) if sm == HIVE_BOOST else 0
        if self._correct_heat_boost(boost_remaining, data.get("occupied_heating_setpoint", 0)):
            return
        self._record_heat_boost()

    def _parse_slr2(self, data: dict) -> None:
        """Parse SLR2 dual-channel payload."""
        self.current_temperature = data.get("local_temperature_heat")

        raw_sp = data.get("occupied_heating_setpoint_heat")
        self.target_temperature  = self.heating_frost_prevention if raw_sp == 1 else raw_sp

        rsh = data.get("running_state_heat", "")
        self.running_state_heat  = rsh if rsh else "preheating"
        rsw = data.get("running_state_water", "")
        self.running_state_water = rsw if rsw else "preheating"

        if self.running_state_heat == "heat":
            self.hvac_action = HVACAction.HEATING
        elif self.running_state_heat == "idle":
            self.hvac_action = HVACAction.IDLE
        else:
            self.hvac_action = HVACAction.PREHEATING

        smh = data.get("system_mode_heat", "heat")
        holdh = data.get("temperature_setpoint_hold_heat", False)

        if smh == "off":
            self.hvac_mode = HVACMode.OFF
        elif smh == HIVE_BOOST:
            self.hvac_mode  = HVACMode.HEAT
            self.heat_boost = True
        elif smh == "heat":
            if not holdh and self.show_heat_schedule:
                self.hvac_mode = HVACMode.AUTO
            else:
                self.hvac_mode = HVACMode.HEAT

        if smh != HIVE_BOOST:
            self.pre_boost_hvac_mode   = self.hvac_mode
            self.pre_boost_target_temp = self.target_temperature

        smw = data.get("system_mode_water", "off")
        holdw = data.get("temperature_setpoint_hold_water", False)
        if smw == "off":
            self.water_mode = "off"
        elif smw == HIVE_BOOST:
            self.water_mode  = "boost"
            self.water_boost = True
        elif smw == "heat":
            if not holdw and self.show_water_schedule:
                self.water_mode = "auto"
            else:
                self.water_mode = "heat"

        if smw != HIVE_BOOST:
            self.pre_boost_water_mode = self.water_mode

        boost_h = data.get("temperature_setpoint_hold_duration_heat", 0) if smh == HIVE_BOOST else 0
        boost_w = data.get("temperature_setpoint_hold_duration_water", 0) if smw == HIVE_BOOST else 0

        if self._correct_heat_boost(boost_h, data.get("occupied_heating_setpoint_heat", 0)):
            return
        self._record_heat_boost()
        if self._correct_water_boost(boost_w):
            return
        self._record_water_boost()

    # ── Boost correction ───────────────────────────────────────────────────────

    def _correct_heat_boost(self, reported: int, temp: float) -> bool:
        if reported > BOOST_ERROR:
            if self.heat_boost_started and self.heat_boost_started_duration > 0:
                elapsed = (utcnow() - self.heat_boost_started).total_seconds() / 60
                self.heat_boost_remaining = max(0, int(self.heat_boost_started_duration - elapsed))
            else:
                self.heat_boost_remaining = 0
            if self.config_entry:
                self.config_entry.async_create_task(
                    self.hass, self.async_heating_boost(self.heat_boost_remaining, temp)
                )
            return True
        self.heat_boost_remaining = reported
        return False

    def _correct_water_boost(self, reported: int) -> bool:
        if reported > BOOST_ERROR:
            if self.water_boost_started and self.water_boost_started_duration > 0:
                elapsed = (utcnow() - self.water_boost_started).total_seconds() / 60
                self.water_boost_remaining = max(0, int(self.water_boost_started_duration - elapsed))
            else:
                self.water_boost_remaining = 0
            if self.config_entry:
                self.config_entry.async_create_task(
                    self.hass, self.async_water_boost(self.water_boost_remaining)
                )
            return True
        self.water_boost_remaining = reported
        return False

    def _record_heat_boost(self) -> None:
        if self.heat_boost and self.heat_boost_remaining > 0:
            if not self.heat_boost_started:
                self.heat_boost_started = utcnow()
                self.heat_boost_started_duration = self.heat_boost_remaining
        else:
            self.heat_boost_started = None
            self.heat_boost_started_duration = 0

    def _record_water_boost(self) -> None:
        if self.water_boost and self.water_boost_remaining > 0:
            if not self.water_boost_started:
                self.water_boost_started = utcnow()
                self.water_boost_started_duration = self.water_boost_remaining
        else:
            self.water_boost_started = None
            self.water_boost_started_duration = 0

    # ── MQTT publish helpers ───────────────────────────────────────────────────

    async def _publish(self, payload: str) -> None:
        _LOGGER.debug("→ %s : %s", self.topic_set, payload)
        await mqtt_client.async_publish(self.hass, self.topic_set, payload)

    # ── Climate commands ───────────────────────────────────────────────────────

    async def async_set_temperature(self, temperature: float) -> None:
        if self.model == MODEL_SLR2:
            await self._publish(f'{{"occupied_heating_setpoint_heat":{temperature}}}')
        elif self.is_trv:
            await self._publish(f'{{"occupied_heating_setpoint":{temperature}}}')
        else:
            await self._publish(f'{{"occupied_heating_setpoint":{temperature}}}')

    async def async_set_hvac_mode_off(self) -> None:
        if self.model == MODEL_SLR2:
            await self._publish('{"system_mode_heat":"off","temperature_setpoint_hold_heat":"0"}')
            await sleep(0.5)
            await self._publish(
                f'{{"occupied_heating_setpoint_heat":{self.heating_frost_prevention},'
                f'"temperature_setpoint_hold_heat":"1","temperature_setpoint_hold_duration_heat":"65535"}}'
            )
        elif self.is_trv:
            await self._publish('{"system_mode":"off"}')
        else:
            await self._publish('{"system_mode":"off","temperature_setpoint_hold":"0"}')
            await sleep(0.5)
            await self._publish(
                f'{{"occupied_heating_setpoint":{self.heating_frost_prevention},'
                f'"temperature_setpoint_hold":"1","temperature_setpoint_hold_duration":"65535"}}'
            )

    async def async_set_hvac_mode_heat(self, temperature: float, from_temp: bool = False) -> None:
        if self.model == MODEL_SLR2:
            payload = (
                f'{{"system_mode_heat":"heat","occupied_heating_setpoint_heat":{temperature},'
                f'"temperature_setpoint_hold_heat":"1","temperature_setpoint_hold_duration_heat":"0"}}'
            )
            await self._publish(payload)
            if not from_temp:
                await sleep(0.5)
                await self._publish(f'{{"system_mode_heat":"heat","occupied_heating_setpoint_heat":{temperature}}}')
        elif self.is_trv:
            await self._publish(f'{{"system_mode":"heat","occupied_heating_setpoint":{temperature}}}')
        else:
            payload = (
                f'{{"system_mode":"heat","occupied_heating_setpoint":{temperature},'
                f'"temperature_setpoint_hold":"1","temperature_setpoint_hold_duration":"0"}}'
            )
            await self._publish(payload)
            if not from_temp:
                await sleep(0.5)
                await self._publish(f'{{"system_mode":"heat","occupied_heating_setpoint":{temperature}}}')

    async def async_set_hvac_mode_auto(self) -> None:
        if self.model == MODEL_SLR2:
            await self._publish(
                '{"system_mode_heat":"heat","temperature_setpoint_hold_heat":"0",'
                '"temperature_setpoint_hold_duration_heat":"0"}'
            )
        elif not self.is_trv:
            await self._publish(
                '{"system_mode":"heat","temperature_setpoint_hold":"0",'
                '"temperature_setpoint_hold_duration":"0"}'
            )

    async def async_heating_boost(
        self,
        duration: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self.pre_boost_hvac_mode   = self.hvac_mode
        self.pre_boost_target_temp = self.target_temperature
        dur  = int(duration or self.heating_boost_duration)
        temp = temperature or self.heating_boost_temperature

        if self.model == MODEL_SLR2:
            await self._publish(
                f'{{"system_mode_heat":"emergency_heating",'
                f'"temperature_setpoint_hold_duration_heat":{dur},'
                f'"temperature_setpoint_hold_heat":1,'
                f'"occupied_heating_setpoint_heat":{temp}}}'
            )
        elif self.is_trv:
            await self._publish(
                f'{{"system_mode":"emergency_heating","occupied_heating_setpoint":{temp}}}'
            )
        else:
            await self._publish(
                f'{{"system_mode":"emergency_heating",'
                f'"temperature_setpoint_hold_duration":{dur},'
                f'"temperature_setpoint_hold":1,'
                f'"occupied_heating_setpoint":{temp}}}'
            )

        self.heat_boost = True
        self.heat_boost_started = utcnow()
        self.heat_boost_started_duration = dur

    async def async_heating_boost_cancel(self) -> None:
        if self.pre_boost_hvac_mode == HVACMode.AUTO:
            await self.async_set_hvac_mode_auto()
        elif self.pre_boost_hvac_mode == HVACMode.HEAT and self.pre_boost_target_temp:
            await self.async_set_hvac_mode_heat(self.pre_boost_target_temp)
        else:
            await self.async_set_hvac_mode_off()

    async def async_water_boost(self, duration: int | None = None) -> None:
        self.pre_boost_water_mode = self.water_mode
        dur = int(duration or self.water_boost_duration)
        await self._publish(
            f'{{"system_mode_water":"emergency_heating",'
            f'"temperature_setpoint_hold_duration_water":{dur},'
            f'"temperature_setpoint_hold_water":1}}'
        )
        self.water_boost = True
        self.water_boost_started = utcnow()
        self.water_boost_started_duration = dur

    async def async_water_boost_cancel(self) -> None:
        if self.pre_boost_water_mode == "auto":
            await self.async_water_scheduled()
        elif self.pre_boost_water_mode == "heat":
            await self.async_water_always_on()
        else:
            await self.async_water_always_off()

    async def async_water_scheduled(self) -> None:
        await self._publish(
            '{"system_mode_water":"heat","temperature_setpoint_hold_water":"0",'
            '"temperature_setpoint_hold_duration_water":"0"}'
        )

    async def async_water_always_on(self) -> None:
        await self._publish('{"system_mode_water":"heat","temperature_setpoint_hold_water":1}')

    async def async_water_always_off(self) -> None:
        await self._publish('{"system_mode_water":"off","temperature_setpoint_hold_water":0}')
