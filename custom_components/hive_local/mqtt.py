"""Z2M MQTT device coordinator for Hive Local v5.

One instance per physical device (TRV or receiver).
Subscribes to a single Z2M topic, parses payloads, and publishes commands.
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
from homeassistant.util.dt import utcnow

from .const import (
    DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP, DEFAULT_FROST_TEMP,
    DEVICE_TYPE_RECEIVER, DEVICE_TYPE_TRV,
    MODEL_SLR2, Z2M_BOOST_MODE,
)

_LOGGER = logging.getLogger(__name__)

# Z2M sometimes reports boost remaining as 65535 when it can't track time
_BOOST_OVERFLOW = 60000


class HiveDeviceMqtt:
    """MQTT handler and state container for one Hive device."""

    # ── Shared state ───────────────────────────────────────────────────────────
    available:              bool       = False
    current_temperature:    float | None = None
    target_temperature:     float | None = None
    hvac_mode:              HVACMode | None = None
    hvac_action:            HVACAction | None = None
    running_state:          str        = "idle"

    # Boiler switch specific (ZBMINIR2)
    switch_state:           str | None = None   # "ON" | "OFF"

    # TRV-specific
    battery:                int | None = None
    pi_heating_demand:      int | None = None
    local_temp_calibration: float | None = None

    # Orientation / display (TRV only, R/W)
    thermostat_orientation: str | None = None   # "vertical" | "horizontal"
    viewing_direction:      str | None = None   # "normal" | "upside-down"

    # Keypad / lockout (TRV only, R/W)
    keypad_lockout: str | None = None           # "unlock" | "lock"

    # Window detection (TRV only)
    window_open_feature:  bool | None = None    # R/W
    window_open_internal: str | None  = None    # R only (enum)
    window_open_external: bool | None = None    # R/W

    # Heat flags (TRV only)
    heat_available: bool | None = None          # R/W
    heat_required:  bool | None = None          # R only

    # Radiator / sensor mode (TRV only, R/W)
    radiator_covered: bool | None = None

    # Adaptation run (TRV only)
    adaptation_run_status:   str | None  = None  # R only (enum)
    adaptation_run_settings: bool | None = None  # R/W (auto night run)
    adaptation_run_control:  str | None  = None  # R/W (enum)

    # Programming (TRV only, R/W)
    programming_operation_mode: str | None = None

    # Setpoints / limits (TRV only)
    regulation_setpoint_offset:  float | None = None   # R/W -2.5 to 2.5°C
    max_heat_setpoint_limit:     float | None = None   # R/W 5–35°C
    abs_max_heat_setpoint_limit: float | None = None   # R only

    # Algorithm (TRV only)
    algorithm_scale_factor: int | None = None         # R/W 1–10

    # Mounted mode (TRV only)
    mounted_mode_active:  bool | None = None           # R only
    mounted_mode_control: bool | None = None           # R/W

    # Preheat (TRV only, R only)
    preheat_status: bool | None = None

    # System diagnostics
    system_status_code:     str | None = None          # R only
    setpoint_change_source: str | None = None          # R only

    # Boost state
    heat_boost_active:      bool       = False
    heat_boost_remaining:   int        = 0
    heat_boost_started:     datetime | None = None
    heat_boost_duration:    int        = 0
    pre_boost_mode:         HVACMode | None = None
    pre_boost_temp:         float | None = None

    # Configurable defaults (set by number entities via RestoreNumber)
    boost_temperature:  float = DEFAULT_BOOST_TEMP
    boost_duration:     int   = DEFAULT_BOOST_MINUTES
    frost_temperature:  float = DEFAULT_FROST_TEMP

    # Raw last payload for diagnostics
    last_payload: dict[str, Any] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        device_type: str,
        model: str,
        topic: str,
        name: str,
    ) -> None:
        self.hass        = hass
        self.device_id   = device_id
        self.device_type = device_type
        self.model       = model
        self.topic       = topic
        self.name        = name
        self._listeners: list = []
        self._unsub_mqtt = None

    @property
    def is_trv(self) -> bool:
        return self.device_type == DEVICE_TYPE_TRV

    @property
    def topic_set(self) -> str:
        return f"{self.topic}/set"

    @property
    def topic_get(self) -> str:
        return f"{self.topic}/get"

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Subscribe to Z2M MQTT topic."""
        self._unsub_mqtt = await mqtt_client.async_subscribe(
            self.hass, self.topic, self._on_message, 1
        )
        _LOGGER.info("Subscribed to %s (device=%s, model=%s)", self.topic, self.name, self.model)
        # Request current state from Z2M
        await sleep(1)
        await self._publish_get()

    async def async_unload(self) -> None:
        if self._unsub_mqtt:
            self._unsub_mqtt()
            self._unsub_mqtt = None

    def add_listener(self, listener) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            try:
                listener()
            except Exception as exc:
                _LOGGER.error("Listener error: %s", exc)

    # ── MQTT message handling ──────────────────────────────────────────────────

    @callback
    def _on_message(self, message: ReceiveMessage) -> None:
        """Parse incoming Z2M payload."""
        if not message.payload:
            return
        try:
            data: dict[str, Any] = json.loads(message.payload)
        except (json.JSONDecodeError, ValueError):
            _LOGGER.warning("Bad JSON from %s: %s", self.topic, message.payload[:100])
            return

        self.last_payload = data
        self.available    = True

        try:
            if self.is_trv:
                self._parse_trv(data)
            elif self.model == MODEL_SLR2:
                self._parse_slr2(data)
            else:
                self._parse_slr1(data)
        except Exception as exc:
            _LOGGER.error("Parse error for %s: %s", self.name, exc)
            return

        self._notify()

    def _parse_trv(self, d: dict) -> None:
        self.current_temperature    = d.get("local_temperature")
        self.target_temperature     = d.get("occupied_heating_setpoint") or d.get("current_heating_setpoint")
        self.battery                = d.get("battery")
        self.pi_heating_demand      = d.get("pi_heating_demand")
        self.local_temp_calibration = d.get("local_temperature_calibration")

        rs = d.get("running_state", "idle")
        self.running_state = rs if rs else "idle"

        sm = d.get("system_mode", "heat")
        if sm == "off":
            self.hvac_mode   = HVACMode.OFF
            self.hvac_action = HVACAction.OFF
        elif sm == Z2M_BOOST_MODE:
            self.hvac_mode          = HVACMode.HEAT
            self.hvac_action        = HVACAction.HEATING
            self.heat_boost_active  = True
        else:
            self.hvac_mode   = HVACMode.HEAT
            self.hvac_action = HVACAction.HEATING if self.running_state == "heat" else HVACAction.IDLE
            if self.heat_boost_active and sm != Z2M_BOOST_MODE:
                self.heat_boost_active = False

        # Extended attributes
        self.thermostat_orientation     = d.get("thermostat_orientation")
        self.viewing_direction          = d.get("viewing_direction")
        self.keypad_lockout             = d.get("keypad_lockout")
        self.window_open_feature        = d.get("window_open_feature")
        self.window_open_internal       = d.get("window_open_internal")
        self.window_open_external       = d.get("window_open_external")
        self.heat_available             = d.get("heat_available")
        self.heat_required              = d.get("heat_required")
        self.radiator_covered           = d.get("radiator_covered")
        self.adaptation_run_status      = d.get("adaptation_run_status")
        self.adaptation_run_settings    = d.get("adaptation_run_settings")
        self.adaptation_run_control     = d.get("adaptation_run_control")
        self.programming_operation_mode = d.get("programming_operation_mode")
        self.regulation_setpoint_offset = d.get("regulation_setpoint_offset")
        self.max_heat_setpoint_limit    = d.get("max_heat_setpoint_limit")
        self.abs_max_heat_setpoint_limit= d.get("abs_max_heat_setpoint_limit")
        self.algorithm_scale_factor     = d.get("algorithm_scale_factor")
        self.mounted_mode_active        = d.get("mounted_mode_active")
        self.mounted_mode_control       = d.get("mounted_mode_control")
        self.preheat_status             = d.get("preheat_status")
        self.system_status_code         = d.get("system_status_code")
        self.setpoint_change_source     = d.get("setpoint_change_source")

    def _parse_slr1(self, d: dict) -> None:
        self.current_temperature = d.get("local_temperature")
        sp = d.get("occupied_heating_setpoint")
        self.target_temperature  = self.frost_temperature if sp == 1 else sp

        rs = d.get("running_state", "idle")
        self.running_state = rs if rs else "idle"
        self.hvac_action   = HVACAction.HEATING if self.running_state == "heat" else HVACAction.IDLE

        sm    = d.get("system_mode", "heat")
        hold  = d.get("temperature_setpoint_hold", False)
        br    = d.get("temperature_setpoint_hold_duration", 0) if sm == Z2M_BOOST_MODE else 0

        if sm == "off":
            self.hvac_mode = HVACMode.OFF
        elif sm == Z2M_BOOST_MODE:
            self.hvac_mode         = HVACMode.HEAT
            self.heat_boost_active = True
            self._update_boost_remaining(br)
        elif sm == "heat" and not hold:
            self.hvac_mode = HVACMode.AUTO   # schedule mode
        else:
            self.hvac_mode = HVACMode.HEAT

        if sm != Z2M_BOOST_MODE:
            self.pre_boost_mode = self.hvac_mode
            self.pre_boost_temp = self.target_temperature
            if self.heat_boost_active:
                self.heat_boost_active = False

    def _parse_slr2(self, d: dict) -> None:
        """Parse SLR2 — uses _heat suffixed keys for heating channel."""
        self.current_temperature = d.get("local_temperature_heat")
        sp = d.get("occupied_heating_setpoint_heat")
        self.target_temperature  = self.frost_temperature if sp == 1 else sp

        rs = d.get("running_state_heat", "idle")
        self.running_state = rs if rs else "idle"
        self.hvac_action   = HVACAction.HEATING if self.running_state == "heat" else HVACAction.IDLE

        sm    = d.get("system_mode_heat", "heat")
        hold  = d.get("temperature_setpoint_hold_heat", False)
        br    = d.get("temperature_setpoint_hold_duration_heat", 0) if sm == Z2M_BOOST_MODE else 0

        if sm == "off":
            self.hvac_mode = HVACMode.OFF
        elif sm == Z2M_BOOST_MODE:
            self.hvac_mode         = HVACMode.HEAT
            self.heat_boost_active = True
            self._update_boost_remaining(br)
        elif sm == "heat" and not hold:
            self.hvac_mode = HVACMode.AUTO
        else:
            self.hvac_mode = HVACMode.HEAT

        if sm != Z2M_BOOST_MODE:
            self.pre_boost_mode = self.hvac_mode
            self.pre_boost_temp = self.target_temperature
            if self.heat_boost_active:
                self.heat_boost_active = False

    def _update_boost_remaining(self, reported: int) -> None:
        if reported >= _BOOST_OVERFLOW:
            # Z2M lost track — estimate from our own timer
            if self.heat_boost_started and self.heat_boost_duration > 0:
                elapsed = (utcnow() - self.heat_boost_started).total_seconds() / 60
                self.heat_boost_remaining = max(0, int(self.heat_boost_duration - elapsed))
            else:
                self.heat_boost_remaining = 0
        else:
            self.heat_boost_remaining = reported
            if not self.heat_boost_started:
                self.heat_boost_started  = utcnow()
                self.heat_boost_duration = reported

    # ── MQTT publish helpers ───────────────────────────────────────────────────

    async def _publish(self, payload: str) -> None:
        _LOGGER.debug("→ %s : %s", self.topic_set, payload)
        await mqtt_client.async_publish(self.hass, self.topic_set, payload)

    async def _publish_get(self) -> None:
        if self.is_trv:
            await mqtt_client.async_publish(self.hass, self.topic_get, '{"system_mode":""}')
        elif self.model == MODEL_SLR2:
            await mqtt_client.async_publish(self.hass, self.topic_get, '{"system_mode_heat":""}')
        else:
            await mqtt_client.async_publish(self.hass, self.topic_get, '{"system_mode":""}')

    # ── Climate commands ───────────────────────────────────────────────────────

    async def async_set_temperature(self, temperature: float) -> None:
        if self.model == MODEL_SLR2:
            await self._publish(f'{{"occupied_heating_setpoint_heat":{temperature}}}')
        else:
            await self._publish(f'{{"occupied_heating_setpoint":{temperature}}}')

    async def async_set_mode_off(self) -> None:
        if self.is_trv:
            await self._publish('{"system_mode":"off"}')
        elif self.model == MODEL_SLR2:
            await self._publish('{"system_mode_heat":"off","temperature_setpoint_hold_heat":"0"}')
            await sleep(0.3)
            fp = self.frost_temperature
            await self._publish(
                f'{{"occupied_heating_setpoint_heat":{fp},'
                f'"temperature_setpoint_hold_heat":"1","temperature_setpoint_hold_duration_heat":"65535"}}'
            )
        else:
            await self._publish('{"system_mode":"off","temperature_setpoint_hold":"0"}')
            await sleep(0.3)
            fp = self.frost_temperature
            await self._publish(
                f'{{"occupied_heating_setpoint":{fp},'
                f'"temperature_setpoint_hold":"1","temperature_setpoint_hold_duration":"65535"}}'
            )

    async def async_set_mode_heat(self, temperature: float) -> None:
        if self.is_trv:
            await self._publish(f'{{"system_mode":"heat","occupied_heating_setpoint":{temperature}}}')
        elif self.model == MODEL_SLR2:
            await self._publish(
                f'{{"system_mode_heat":"heat","occupied_heating_setpoint_heat":{temperature},'
                f'"temperature_setpoint_hold_heat":"1","temperature_setpoint_hold_duration_heat":"0"}}'
            )
        else:
            await self._publish(
                f'{{"system_mode":"heat","occupied_heating_setpoint":{temperature},'
                f'"temperature_setpoint_hold":"1","temperature_setpoint_hold_duration":"0"}}'
            )

    async def async_set_mode_schedule(self) -> None:
        """Auto/schedule mode — release the setpoint hold."""
        if self.is_trv:
            return  # TRVs don't have native schedule mode via Z2M hold
        if self.model == MODEL_SLR2:
            await self._publish(
                '{"system_mode_heat":"heat","temperature_setpoint_hold_heat":"0",'
                '"temperature_setpoint_hold_duration_heat":"0"}'
            )
        else:
            await self._publish(
                '{"system_mode":"heat","temperature_setpoint_hold":"0",'
                '"temperature_setpoint_hold_duration":"0"}'
            )

    async def async_boost(
        self,
        duration: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self.pre_boost_mode = self.hvac_mode
        self.pre_boost_temp = self.target_temperature
        dur  = int(duration   or self.boost_duration)
        temp = float(temperature or self.boost_temperature)

        self.heat_boost_active   = True
        self.heat_boost_started  = utcnow()
        self.heat_boost_duration = dur

        if self.is_trv:
            await self._publish(
                f'{{"system_mode":"{Z2M_BOOST_MODE}","occupied_heating_setpoint":{temp}}}'
            )
        elif self.model == MODEL_SLR2:
            await self._publish(
                f'{{"system_mode_heat":"{Z2M_BOOST_MODE}",'
                f'"temperature_setpoint_hold_heat":1,'
                f'"temperature_setpoint_hold_duration_heat":{dur},'
                f'"occupied_heating_setpoint_heat":{temp}}}'
            )
        else:
            await self._publish(
                f'{{"system_mode":"{Z2M_BOOST_MODE}",'
                f'"temperature_setpoint_hold":1,'
                f'"temperature_setpoint_hold_duration":{dur},'
                f'"occupied_heating_setpoint":{temp}}}'
            )
        _LOGGER.info("Boost started on %s: %.1f°C for %d min", self.name, temp, dur)

    async def async_end_boost(self) -> None:
        self.heat_boost_active  = False
        self.heat_boost_started = None
        if self.pre_boost_mode == HVACMode.AUTO:
            await self.async_set_mode_schedule()
        elif self.pre_boost_mode == HVACMode.HEAT and self.pre_boost_temp:
            await self.async_set_mode_heat(self.pre_boost_temp)
        else:
            await self.async_set_mode_off()
        _LOGGER.info("Boost ended on %s → returning to %s", self.name, self.pre_boost_mode)

    # ── Extended TRV commands ──────────────────────────────────────────────────

    async def async_set_thermostat_orientation(self, value: str) -> None:
        """Set orientation: 'vertical' or 'horizontal'."""
        await self._publish(f'{{"thermostat_orientation":"{value}"}}')

    async def async_set_viewing_direction(self, value: str) -> None:
        """Set display direction: 'normal' or 'upside-down'."""
        await self._publish(f'{{"viewing_direction":"{value}"}}')

    async def async_set_keypad_lockout(self, value: str) -> None:
        """Set keypad lock: 'lock' or 'unlock'."""
        await self._publish(f'{{"keypad_lockout":"{value}"}}')

    async def async_set_window_open_feature(self, enabled: bool) -> None:
        await self._publish(f'{{"window_open_feature":{str(enabled).lower()}}}')

    async def async_set_window_open_external(self, open: bool) -> None:
        await self._publish(f'{{"window_open_external":{str(open).lower()}}}')

    async def async_set_heat_available(self, available: bool) -> None:
        await self._publish(f'{{"heat_available":{str(available).lower()}}}')

    async def async_set_radiator_covered(self, covered: bool) -> None:
        await self._publish(f'{{"radiator_covered":{str(covered).lower()}}}')

    async def async_set_adaptation_run_settings(self, enabled: bool) -> None:
        await self._publish(f'{{"adaptation_run_settings":{str(enabled).lower()}}}')

    async def async_set_adaptation_run_control(self, value: str) -> None:
        """value: 'idle' | 'initiate_adaptation' | 'cancel_adaptation'."""
        await self._publish(f'{{"adaptation_run_control":"{value}"}}')

    async def async_set_programming_operation_mode(self, value: str) -> None:
        """value: 'setpoint' | 'schedule' | 'schedule_with_preheat' | 'eco'."""
        await self._publish(f'{{"programming_operation_mode":"{value}"}}')

    async def async_set_regulation_setpoint_offset(self, value: float) -> None:
        await self._publish(f'{{"regulation_setpoint_offset":{value}}}')

    async def async_set_max_heat_setpoint_limit(self, value: float) -> None:
        await self._publish(f'{{"max_heat_setpoint_limit":{value}}}')

    async def async_set_algorithm_scale_factor(self, value: int) -> None:
        await self._publish(f'{{"algorithm_scale_factor":{value}}}')

    async def async_set_mounted_mode_control(self, mounting: bool) -> None:
        """true = go to mounting mode, false = go to mounted mode."""
        await self._publish(f'{{"mounted_mode_control":{str(mounting).lower()}}}')
