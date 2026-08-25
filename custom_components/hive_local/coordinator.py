"""Coordinator for Hive Local — ZBMINIR2 boiler switch control."""

from __future__ import annotations

import json
from asyncio import sleep
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate.const import HVACAction, HVACMode, PRESET_BOOST, PRESET_NONE
from homeassistant.components.mqtt import client as mqtt_client
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .const import (
    DEFAULT_FROST_TEMPERATURE,
    DEFAULT_HEATING_BOOST_MINUTES,
    DEFAULT_HEATING_BOOST_TEMPERATURE,
    DOMAIN,
    HIVE_BOOST,
    LOGGER,
)

PRESET_MAP = {
    PRESET_NONE: "",
    PRESET_BOOST: HIVE_BOOST,
}

BOOST_ERROR = 65000
WATCHDOG_INTERVAL = 20   # seconds
STARTUP_SETTLE   = 30    # seconds


class HiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages a single Hive TRV (UK7004240) via MQTT.

    The SLR receiver has been replaced by a Sonoff ZBMINIR2 relay.
    This coordinator:
    - Tracks TRV state (temp, target, mode, boost, running_state)
    - Reports heat demand (heat_required / pi_heating_demand / running_state)
    - The boiler switch (ZBMINIR2) is driven by a separate BoilerSwitchCoordinator
    """

    # TRV state
    current_temperature: float | None = None
    target_temperature:  float | None = None
    preset_mode:         str | None   = None
    hvac_mode:           HVACMode | None = None
    running_state_heat:  str = ""

    heat_boost:                  bool          = False
    heat_boost_started:          datetime | None = None
    heat_boost_started_duration: int           = 0
    heat_boost_remaining:        int           = 0

    pre_boost_hvac_mode:                         HVACMode | None = None
    pre_boost_occupied_heating_setpoint_heat:    float | None    = None

    # Number entity values
    heating_boost_duration:     float = DEFAULT_HEATING_BOOST_MINUTES
    heating_boost_temperature:  float = DEFAULT_HEATING_BOOST_TEMPERATURE
    heating_frost_prevention:   float = DEFAULT_FROST_TEMPERATURE

    # Diagnostics
    last_mqtt_payload: dict[str, Any] | None = None

    # Heat demand — used by BoilerSwitchCoordinator
    heat_required:     bool | None = None
    pi_heating_demand: int | None  = None
    # Callback fired after every MQTT update
    on_demand_change:  Any | None  = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        model: str,
        topic: str,
        show_heat_schedule_mode: bool,
    ) -> None:
        """Initialise the TRV coordinator."""
        super().__init__(hass, LOGGER, name=f"{DOMAIN}_{entry_id}")
        self.entry_id                 = entry_id
        self.model                    = model
        self.topic                    = topic
        self.show_heating_schedule_mode = show_heat_schedule_mode
        self.data: dict[str, Any]     = {}

    @property
    def topic_get(self) -> str:
        return self.topic + "/get"

    @property
    def topic_set(self) -> str:
        return self.topic + "/set"

    @property
    def boost_remaining_heat(self) -> int:
        return self.heat_boost_remaining

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.running_state_heat == "preheating":
            return HVACAction.PREHEATING
        if self.running_state_heat == "heat":
            return HVACAction.HEATING
        if self.running_state_heat == "idle":
            return HVACAction.IDLE
        if self.running_state_heat == "off":
            return HVACAction.OFF
        return None

    @property
    def local_temperature_heat(self) -> float | None:
        return self.current_temperature

    def climate_preset(self, mode: str) -> str:
        return next((k for k, v in PRESET_MAP.items() if v == mode), PRESET_MAP[PRESET_NONE])

    @callback
    def handle_mqtt_message(self, message: ReceiveMessage) -> None:
        """Parse incoming TRV MQTT payload."""
        topic   = message.topic
        payload = message.payload
        LOGGER.debug("Received from %s payload: %s", topic, payload)

        if not payload:
            LOGGER.error("Empty payload on topic %s", topic)
            return

        self.current_temperature = None
        self.target_temperature  = None
        self.preset_mode         = None
        self.hvac_mode           = None
        self.heat_boost          = False

        try:
            parsed_data: dict[str, Any] = json.loads(payload)
            self.last_mqtt_payload       = parsed_data

            # Heat demand signals
            self.heat_required     = parsed_data.get("heat_required")
            self.pi_heating_demand = parsed_data.get("pi_heating_demand")

            reported_boost_remaining = (
                int(parsed_data["temperature_setpoint_hold_duration"])
                if parsed_data.get("system_mode") == "emergency_heating"
                else 0
            )
            reported_boost_temperature = parsed_data.get("occupied_heating_setpoint", 0)

            self.running_state_heat = (
                parsed_data.get("running_state") or "preheating"
            )
            self.current_temperature = parsed_data.get("local_temperature")

            setpoint = parsed_data.get("occupied_heating_setpoint", 1)
            self.target_temperature = (
                self.heating_frost_prevention if setpoint == 1 else setpoint
            )
            self.preset_mode = self.climate_preset(parsed_data.get("system_mode", ""))

            sys_mode = parsed_data.get("system_mode", "")
            if sys_mode == "heat":
                hold = parsed_data.get("temperature_setpoint_hold", True)
                self.hvac_mode = (
                    HVACMode.AUTO if hold is False and self.show_heating_schedule_mode
                    else HVACMode.HEAT
                )
            elif sys_mode == "emergency_heating":
                self.hvac_mode = HVACMode.HEAT
                self.heat_boost = True
            elif sys_mode == "off":
                self.hvac_mode = HVACMode.OFF

            if sys_mode != "emergency_heating":
                self.pre_boost_occupied_heating_setpoint_heat = self.target_temperature
                self.pre_boost_hvac_mode = self.hvac_mode

            if self.correct_heat_boost(reported_boost_remaining, reported_boost_temperature):
                return
            self.record_heat_boost_state()
            self.async_set_updated_data(parsed_data)

            # Notify boiler coordinator of demand change
            if self.on_demand_change is not None:
                self.hass.async_create_task(
                    self.on_demand_change(),
                    name="hive_boiler_demand",
                )

        except (json.JSONDecodeError, KeyError) as err:
            LOGGER.error("Error parsing TRV payload: %s", err)

    def correct_heat_boost(self, reported_boost_remaining: int, reported_boost_temperature: float) -> bool:
        if reported_boost_remaining > BOOST_ERROR:
            if self.heat_boost_started and self.heat_boost_started_duration > 0:
                elapsed = (utcnow() - self.heat_boost_started).total_seconds() / 60
                self.heat_boost_remaining = int(self.heat_boost_started_duration - elapsed)
            else:
                self.heat_boost_remaining = 0
            LOGGER.warning("Correcting boost remaining from %d to %d", reported_boost_remaining, self.heat_boost_remaining)
            if self.config_entry is not None:
                self.config_entry.async_create_task(
                    self.hass,
                    self.async_heating_boost(self.heat_boost_remaining, reported_boost_temperature),
                )
            return True
        self.heat_boost_remaining = reported_boost_remaining
        return False

    def record_heat_boost_state(self) -> None:
        if self.heat_boost and self.heat_boost_remaining > 0:
            if not self.heat_boost_started:
                self.heat_boost_started = utcnow()
                self.heat_boost_started_duration = self.heat_boost_remaining
        elif not self.heat_boost:
            self.heat_boost_started = None
            self.heat_boost_started_duration = 0

    async def _async_publish_set(self, payload: str) -> None:
        LOGGER.debug("Sending to %s: %s", self.topic_set, payload)
        await mqtt_client.async_publish(self.hass, self.topic_set, payload)

    async def async_heating_boost(self, boost_duration_minutes: int | None = None, boost_temperature: float | None = None) -> None:
        self.pre_boost_occupied_heating_setpoint_heat = self.target_temperature
        self.pre_boost_hvac_mode = self.hvac_mode
        duration    = str(int(boost_duration_minutes or self.heating_boost_duration))
        temperature = str(boost_temperature or self.heating_boost_temperature)
        payload = (
            r'{"system_mode":"emergency_heating","temperature_setpoint_hold_duration":' + duration
            + r',"temperature_setpoint_hold":1,"occupied_heating_setpoint":' + temperature + r'}'
        )
        self.heat_boost = True
        self.heat_boost_started = utcnow()
        self.heat_boost_started_duration = int(duration)
        await self._async_publish_set(payload)

    async def async_heating_boost_cancel(self) -> None:
        if self.pre_boost_hvac_mode == HVACMode.AUTO:
            await self.async_set_hvac_mode_auto()
        elif self.pre_boost_hvac_mode == HVACMode.HEAT:
            temp = self.pre_boost_occupied_heating_setpoint_heat or self.heating_frost_prevention
            await self.async_set_hvac_mode_heat(temp)
        else:
            await self.async_set_hvac_mode_off()

    async def async_set_temperature(self, temperature: float) -> None:
        payload = r'{"occupied_heating_setpoint":' + str(temperature) + r'}'
        await self._async_publish_set(payload)

    async def async_set_hvac_mode_off(self) -> None:
        payload = r'{"system_mode":"off","temperature_setpoint_hold":"0"}'
        self.hvac_mode = HVACMode.OFF
        await self._async_publish_set(payload)
        await sleep(0.5)
        payload = (
            r'{"occupied_heating_setpoint":' + str(self.heating_frost_prevention)
            + r',"temperature_setpoint_hold":"1","temperature_setpoint_hold_duration":"65535"}'
        )
        await self._async_publish_set(payload)

    async def async_set_hvac_mode_auto(self) -> None:
        payload = r'{"system_mode":"heat","temperature_setpoint_hold":"0","temperature_setpoint_hold_duration":"0"}'
        self.hvac_mode = HVACMode.AUTO
        await self._async_publish_set(payload)

    async def async_set_hvac_mode_heat(self, temperature: float, set_from_temperature: bool = False) -> None:
        payload = (
            r'{"system_mode":"heat","occupied_heating_setpoint":' + str(temperature)
            + r',"temperature_setpoint_hold":"1","temperature_setpoint_hold_duration":"0"}'
        )
        self.hvac_mode = HVACMode.HEAT
        await self._async_publish_set(payload)
        if not set_from_temperature:
            await sleep(0.5)
            payload2 = r'{"system_mode":"heat","occupied_heating_setpoint":' + str(temperature) + r'}'
            await self._async_publish_set(payload2)


class BoilerSwitchCoordinator:
    """Controls the Sonoff ZBMINIR2 relay based on demand from all TRV coordinators.

    Replaces the SLR1/SLR2 receiver. Monitors all registered TRV coordinators
    and turns the HA switch entity on/off based on heat demand.

    Safety features:
    - 30s startup settling before acting — Z2M retained messages land first
    - 5-minute hold-off before turning OFF — prevents boiler short-cycling
    - 20s watchdog — self-heals any state mismatch in both directions
    - power_on_behavior set to 'off' on the ZBMINIR2 via MQTT
    """

    def __init__(self, hass: HomeAssistant, switch_entity_id: str, z2m_topic: str) -> None:
        self.hass              = hass
        self.switch_entity_id  = switch_entity_id
        self.z2m_topic         = z2m_topic          # e.g. zigbee2mqtt/ZBMINIR2
        self._trv_coordinators: list[HiveCoordinator] = []
        self._demand:           bool | None = None   # None = unknown
        self._off_timer                     = None
        self._startup_timer                 = None
        self._watchdog_unsub                = None
        self._ready                         = False

    def register_trv(self, coordinator: HiveCoordinator) -> None:
        """Register a TRV coordinator to monitor for heat demand."""
        if coordinator not in self._trv_coordinators:
            self._trv_coordinators.append(coordinator)
            coordinator.on_demand_change = self.notify_demand_change

    async def async_setup(self) -> None:
        """Start settling timer and set power_on_behavior to off."""
        # Ensure ZBMINIR2 starts safe after any power cycle
        await self._set_power_on_behavior_off()

        async def _mark_ready(_now=None) -> None:
            self._startup_timer = None
            self._ready = True
            LOGGER.info("Hive Local: boiler switch settling complete — evaluating demand")
            await self._watchdog_check()
            self._watchdog_unsub = async_track_time_interval(
                self.hass, self._watchdog, timedelta(seconds=WATCHDOG_INTERVAL)
            )

        self._startup_timer = async_call_later(self.hass, STARTUP_SETTLE, _mark_ready)

    async def async_unload(self) -> None:
        if self._startup_timer:
            self._startup_timer()
            self._startup_timer = None
        if self._off_timer:
            self._off_timer()
            self._off_timer = None
        if self._watchdog_unsub:
            self._watchdog_unsub()
            self._watchdog_unsub = None

    @callback
    def _watchdog(self, _now=None) -> None:
        self.hass.async_create_task(self._watchdog_check(), name="hive_boiler_watchdog")

    async def _watchdog_check(self) -> None:
        """Compare actual switch state to required demand — correct if mismatched."""
        if not self.switch_entity_id:
            return
        state = self.hass.states.get(self.switch_entity_id)
        if state is None:
            return
        switch_on = state.state in ("on", "ON")
        demand, callers = self._evaluate_demand()

        if switch_on and not demand:
            LOGGER.warning(
                "Boiler watchdog: switch ON but no demand — forcing OFF (%s). "
                "TRVs calling: none",
                self.switch_entity_id,
            )
            self._demand = True
            await self._set_switch(False)

        elif not switch_on and demand:
            LOGGER.warning(
                "Boiler watchdog: switch OFF but demand exists — forcing ON (%s). "
                "Demand from: %s",
                self.switch_entity_id,
                ", ".join(callers),
            )
            self._demand = False
            await self._set_switch(True)

        elif switch_on and demand:
            LOGGER.debug(
                "Boiler watchdog: switch ON — valid demand from %s",
                ", ".join(callers),
            )

    def _evaluate_demand(self) -> tuple[bool, list[str]]:
        """Check all TRVs for heat demand. Returns (demand, list_of_caller_names)."""
        callers: list[str] = []
        for coord in self._trv_coordinators:
            calling = (
                coord.running_state_heat == "heat"
                or coord.heat_required is True
                or (coord.pi_heating_demand is not None and coord.pi_heating_demand > 0)
            )
            if calling:
                callers.append(coord.topic.split("/")[-1])
        return bool(callers), callers

    async def notify_demand_change(self) -> None:
        """Called by TRV coordinators when their state changes."""
        if not self._ready:
            return
        demand, callers = self._evaluate_demand()
        if demand:
            if self._off_timer:
                self._off_timer()
                self._off_timer = None
            if callers:
                LOGGER.debug("Heat demand from: %s", ", ".join(callers))
            await self._set_switch(True)
        else:
            if self._off_timer:
                return  # Already waiting to turn off
            async def _do_off(_now=None) -> None:
                self._off_timer = None
                d, _ = self._evaluate_demand()
                if not d:
                    await self._set_switch(False)
            self._off_timer = async_call_later(self.hass, 300, _do_off)

    async def _set_switch(self, on: bool) -> None:
        if not self.switch_entity_id:
            return
        if self._demand is not None and on == self._demand:
            return
        self._demand = on
        domain  = self.switch_entity_id.split(".")[0]
        service = "turn_on" if on else "turn_off"
        try:
            await self.hass.services.async_call(
                domain, service,
                {"entity_id": self.switch_entity_id},
                blocking=False,
            )
            LOGGER.info(
                "Boiler switch → %s (%s)",
                "ON — firing boiler" if on else "OFF — boiler demand cleared",
                self.switch_entity_id,
            )
        except Exception as exc:
            LOGGER.warning("Boiler switch call failed: %s", exc)

    async def _set_power_on_behavior_off(self) -> None:
        """Set ZBMINIR2 power_on_behavior to off via MQTT."""
        if not self.z2m_topic:
            return
        topic   = self.z2m_topic + "/set"
        payload = '{"power_on_behavior":"off"}'
        try:
            await mqtt_client.async_publish(self.hass, topic, payload)
            LOGGER.info("ZBMINIR2: power_on_behavior set to off (%s)", topic)
        except Exception as exc:
            LOGGER.debug("Could not set power_on_behavior: %s", exc)
