"""Z2M bridge device auto-discovery for Hive Local v5.

Subscribes to {base_topic}/bridge/devices (retained MQTT message Z2M
publishes on startup). Parses the device list, identifies Hive TRVs and
receivers, and auto-registers any not already in storage.

Re-checks every 5 minutes to pick up newly paired devices.

Z2M bridge/devices payload is a JSON array:
[
  {
    "ieee_address": "0x3410f4fffe630dad",
    "type": "EndDevice",
    "friendly_name": "Hive TRV Entrance",
    "definition": {
      "model": "UK7004240",
      "vendor": "Hive",
      "description": "Radiator valve"
    },
    "supported": true,
    ...
  },
  ...
]
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.mqtt import client as mqtt_client
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import utcnow

from .const import (
    DEVICE_TYPE_TRV,
    DOMAIN,
)

if TYPE_CHECKING:
    from .coordinator import HiveLocalCoordinator

_LOGGER = logging.getLogger(__name__)

# Z2M definition model strings that map to our device types
_TRV_MODELS: set[str] = {
    "UK7004240",   # Hive Radiator Valve / Danfoss Ally TRV
    "TRV001",
    "eTRV0100", "eTRV0103", "eTRV0111",  # Danfoss Ally
    "014G2461",    # Danfoss Ally (alternate)
    "SORB",        # Bitron TRV
    "POPP-009501", # POPP TRV
}

DISCOVERY_INTERVAL = timedelta(minutes=5)


class HiveDiscovery:
    """Subscribes to Z2M bridge/devices and auto-registers Hive devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: "HiveLocalCoordinator",
        base_topic: str,
    ) -> None:
        self.hass        = hass
        self.coordinator = coordinator
        self.base_topic  = base_topic.rstrip("/")
        self._unsub_mqtt = None
        self._unsub_poll = None
        self._last_seen: dict[str, str] = {}  # ieee → friendly_name

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Subscribe to bridge/devices and start the poll timer."""
        topic = f"{self.base_topic}/bridge/devices"
        self._unsub_mqtt = await mqtt_client.async_subscribe(
            self.hass, topic, self._on_bridge_devices, 1
        )
        _LOGGER.info("Hive discovery: subscribed to %s", topic)

        # Poll timer — re-request device list every 5 min
        self._unsub_poll = async_track_time_interval(
            self.hass, self._poll, DISCOVERY_INTERVAL
        )

    async def async_unload(self) -> None:
        if self._unsub_mqtt:
            self._unsub_mqtt()
        if self._unsub_poll:
            self._unsub_poll()

    # ── MQTT handler ───────────────────────────────────────────────────────────

    @callback
    def _on_bridge_devices(self, message: ReceiveMessage) -> None:
        """Handle incoming bridge/devices payload."""
        try:
            devices: list[dict] = json.loads(message.payload)
        except (json.JSONDecodeError, TypeError):
            _LOGGER.warning("Discovery: bad JSON from bridge/devices")
            return
        self.hass.async_create_task(
            self._process_devices(devices),
            name="hive_local_discovery",
        )

    @callback
    def _poll(self, _now: Any) -> None:
        """Re-request the device list from Z2M."""
        self.hass.async_create_task(
            mqtt_client.async_publish(
                self.hass,
                f"{self.base_topic}/bridge/request/devices",
                "",
            ),
            name="hive_local_discovery_poll",
        )
        _LOGGER.debug("Discovery: requested device refresh from Z2M")

    # ── Device processing ──────────────────────────────────────────────────────

    async def _process_devices(self, devices: list[dict]) -> None:
        """Identify Hive devices in the Z2M device list and register new ones."""
        existing_topics: set[str] = {
            d.get("mqtt_topic", "")
            for d in self.coordinator.store.get_all_devices().values()
            if d.get("mqtt_topic")
        }

        new_count = 0
        for device in devices:
            result = self._classify(device)
            if result is None:
                continue

            device_type, model, friendly_name = result
            topic = f"{self.base_topic}/{friendly_name}"

            if topic in existing_topics:
                continue  # already registered

            ieee = device.get("ieee_address", "")
            if ieee in self._last_seen:
                continue  # already queued this session

            self._last_seen[ieee] = friendly_name
            device_id = str(uuid.uuid4())[:8]
            data: dict = {
                "type":       device_type,
                "name":       friendly_name,
                "mqtt_topic": topic,
            }
            _LOGGER.info(
                "Discovery: auto-registering %s '%s' @ %s",
                device_type, friendly_name, topic,
            )
            await self.coordinator.async_add_device(device_id, data)
            new_count += 1

        if new_count:
            _LOGGER.info("Discovery: registered %d new device(s)", new_count)

    def _classify(
        self, device: dict
    ) -> tuple[str, str, str] | None:
        """Return (device_type, model, friendly_name) or None if not a Hive device."""
        definition = device.get("definition") or {}
        model      = definition.get("model", "")
        vendor     = (definition.get("vendor") or "").lower()
        friendly   = device.get("friendly_name", "")
        supported  = device.get("supported", False)

        if not friendly or not supported:
            return None

        # Skip Z2M coordinator itself
        if friendly == "Coordinator":
            return None

        # TRV?
        if model in _TRV_MODELS:
            return (DEVICE_TYPE_TRV, model, friendly)

        # Receivers (SLR1/SLR2/OTR1) are no longer part of this integration.
        # Only TRVs are auto-discovered. The ZBMINIR2 is a plain HA switch entity
        # configured in Settings — it does not need to be discovered here.
        return None
