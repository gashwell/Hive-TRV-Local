"""Config flow for Hive Local v5.

Single config entry. All device and room management is in the options flow.
Setup just asks for Z2M base topic.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_BOILER_ENTITY, CONF_ENABLE_DIAG,
    CONF_FROST_ENABLED, CONF_FROST_TEMP, CONF_FROST_WEATHER,
    CONF_Z2M_BASE_TOPIC,
    DATA_COORDINATOR, DEFAULT_Z2M_TOPIC, DEVICE_TYPE_RECEIVER,
    DEVICE_TYPE_SENSOR, DEVICE_TYPE_TRV, DOMAIN,
    MODEL_OTR1, MODEL_SLR1, MODEL_SLR2, RECEIVER_MODELS,
)

_LOGGER = logging.getLogger(__name__)


class HiveLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup — just the Z2M base topic."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Hive Local",
                data={
                    CONF_Z2M_BASE_TOPIC: user_input.get(
                        CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC
                    ).strip(),
                    CONF_BOILER_ENTITY:  None,
                    CONF_ENABLE_DIAG:    False,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_Z2M_BASE_TOPIC,
                    default=DEFAULT_Z2M_TOPIC,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> "HiveLocalOptionsFlow":
        return HiveLocalOptionsFlow()


class HiveLocalOptionsFlow(config_entries.OptionsFlow):
    """Full management — devices, rooms, settings."""

    def __init__(self) -> None:
        # Device wizard state
        self._dev_type:    str  = DEVICE_TYPE_TRV
        self._dev_topic:   str  = ""
        self._dev_name:    str  = ""
        self._dev_model:   str  = MODEL_SLR1
        self._dev_id:      str  = ""
        # Room wizard state
        self._room_name:   str        = ""
        self._room_id:     str        = ""
        self._room_devs:   list[str]  = []
        self._room_sensors:list[str]  = []
        self._edit_room_id:str        = ""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _coordinator(self):
        return self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id, {}
        ).get(DATA_COORDINATOR)

    def _store(self):
        c = self._coordinator()
        return c.store if c else None

    def _z2m_base(self) -> str:
        opts = self.config_entry.options or {}
        data = self.config_entry.data or {}
        return opts.get(CONF_Z2M_BASE_TOPIC, data.get(CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC))

    def _all_devices(self) -> dict:
        s = self._store()
        return s.get_all_devices() if s else {}

    def _all_rooms(self) -> dict:
        s = self._store()
        return s.get_all_rooms() if s else {}

    def _ungrouped_trv_ids(self, exclude_room: str | None = None) -> list[str]:
        """Return TRV device IDs not currently in any room (optionally excluding one room)."""
        s = self._store()
        if not s:
            return []
        all_grouped: set[str] = set()
        for rid, rd in s.get_all_rooms().items():
            if rid == exclude_room:
                continue
            all_grouped.update(rd.get("device_ids", []))
        return [
            did for did, dd in s.get_all_devices().items()
            if dd.get("type") == DEVICE_TYPE_TRV and did not in all_grouped
        ]

    def _discovered_z2m_topics(self) -> dict[str, str]:
        """Return {topic: friendly_name} for Z2M climate entities not already registered.

        Z2M registers climate entities with entity_id like climate.living_room_trv.
        The friendly name is best read from:
        1. hass.states — the friendly_name attribute on the live state
        2. entity registry original_name / name
        3. The entity_id slug converted to title case as a fallback

        The "topic" key we store is the Z2M MQTT topic, which for Z2M is:
          {base_topic}/{friendly_name}
        We derive this from the entity_id slug since Z2M slugifies friendly names
        the same way HA does (lowercase, underscores).
        We also include the real entity_id so the user can verify.
        """
        from homeassistant.helpers import device_registry as dr
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        base    = self._z2m_base()

        existing_topics = {
            d.get("mqtt_topic", "")
            for d in self._all_devices().values()
            if d.get("mqtt_topic")
        }

        result: dict[str, str] = {}
        for entry in ent_reg.entities.values():
            if entry.platform != "mqtt":
                continue
            if not entry.entity_id.startswith("climate."):
                continue
            uid = entry.unique_id or ""
            # Skip our own room entities
            if uid.startswith(f"{DOMAIN}_") and uid.endswith("_climate"):
                continue

            # ── Derive friendly name ─────────────────────────────────────────
            friendly = ""

            # 1. Live state friendly_name (most reliable — set by Z2M)
            state = self.hass.states.get(entry.entity_id)
            if state:
                friendly = state.attributes.get("friendly_name", "")

            # 2. Device registry name
            if not friendly and entry.device_id:
                device = dev_reg.async_get(entry.device_id)
                if device:
                    friendly = device.name_by_user or device.name or ""

            # 3. Entity registry name
            if not friendly:
                friendly = entry.name or entry.original_name or ""

            # 4. Fall back to the raw HA entity_id
            if not friendly:
                friendly = entry.entity_id

            # ── Derive Z2M topic ─────────────────────────────────────────────
            # Z2M topic = base_topic/friendly_name
            # If uid looks like a topic already (contains /) use it directly
            if "/" in uid:
                topic = uid
            else:
                # Build from friendly name — Z2M uses the friendly_name as the topic segment
                topic = f"{base}/{friendly}"

            if topic in existing_topics:
                continue

            result[topic] = friendly

        return result

    def _open_meteo_weather_entity(self) -> str | None:
        """Return the first Open-Meteo weather entity_id if installed and loaded."""
        from homeassistant.helpers import entity_registry as er
        # Check config entries for open_meteo domain
        for ce in self.hass.config_entries.async_entries("open_meteo"):
            if ce.state.value != "loaded":
                continue
            # Find weather entity for this entry
            ent_reg = er.async_get(self.hass)
            for entry in ent_reg.entities.values():
                if (entry.config_entry_id == ce.entry_id
                        and entry.entity_id.startswith("weather.")):
                    return entry.entity_id
        return None

    def _registered_receivers(self) -> dict[str, str]:
        """Return {device_id: name} for all registered receiver devices."""
        return {
            did: dd.get("name", did)
            for did, dd in self._all_devices().items()
            if dd.get("type") == DEVICE_TYPE_RECEIVER
        }

    def _no_rooms_result(self) -> config_entries.FlowResult:
        return self.async_create_entry(title="", data=self.config_entry.options or {})

    # ── Top-level menu ─────────────────────────────────────────────────────────

    async def async_step_init(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "manage_devices":    "Devices — add and remove TRVs, receivers, sensors",
                "manage_rooms":      "Rooms — create and manage heating zones",
                "on_demand_heating": "On-demand heating — link TRVs and rooms to receiver",
                "settings":          "Settings — boiler, Z2M topic, frost protection",
            },
        )

    # ── Settings ───────────────────────────────────────────────────────────────

    async def async_step_settings(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        weather_entity   = self._open_meteo_weather_entity()
        open_meteo_ok    = weather_entity is not None

        if user_input is not None:
            c = self._coordinator()
            if c:
                c.update_boiler_entity(user_input.get(CONF_BOILER_ENTITY) or None)
                # Update global frost protection on coordinator
                frost_enabled = user_input.get(CONF_FROST_ENABLED, False)
                frost_temp    = float(user_input.get(CONF_FROST_TEMP, 2.0))
                c.update_frost_protection(
                    enabled=frost_enabled,
                    threshold=frost_temp,
                    weather_entity=weather_entity if frost_enabled else None,
                )
            new_opts = {
                **(self.config_entry.options or {}),
                CONF_Z2M_BASE_TOPIC: user_input.get(CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC),
                CONF_BOILER_ENTITY:  user_input.get(CONF_BOILER_ENTITY) or None,
                CONF_ENABLE_DIAG:    user_input.get(CONF_ENABLE_DIAG, False),
                CONF_FROST_ENABLED:  user_input.get(CONF_FROST_ENABLED, False),
                CONF_FROST_TEMP:     float(user_input.get(CONF_FROST_TEMP, 2.0)),
                CONF_FROST_WEATHER:  weather_entity,
            }
            return self.async_create_entry(title="", data=new_opts)

        merged = {**(self.config_entry.data or {}), **(self.config_entry.options or {})}

        schema: dict = {
            vol.Required(
                CONF_Z2M_BASE_TOPIC,
                default=merged.get(CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                CONF_BOILER_ENTITY,
                description={"suggested_value": merged.get(CONF_BOILER_ENTITY)},
            ): selector.EntitySelector(selector.EntitySelectorConfig(
                domain=["climate", "switch", "input_boolean"]
            )),
        }

        if open_meteo_ok:
            schema[vol.Optional(
                CONF_FROST_ENABLED,
                default=merged.get(CONF_FROST_ENABLED, False),
            )] = selector.BooleanSelector()
            schema[vol.Optional(
                CONF_FROST_TEMP,
                default=merged.get(CONF_FROST_TEMP, 2.0),
            )] = selector.NumberSelector(selector.NumberSelectorConfig(
                min=-10, max=10, step=0.5,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.SLIDER,
            ))

        schema[vol.Optional(
            CONF_ENABLE_DIAG,
            default=merged.get(CONF_ENABLE_DIAG, False),
        )] = selector.BooleanSelector()

        frost_hint = (
            f"Open-Meteo detected — using {weather_entity}. "
            "Enable to fire the boiler when outdoor temperature falls to or below the threshold, "
            "regardless of individual TRV frost settings."
            if open_meteo_ok else
            "Install Open-Meteo via HACS to enable weather-based boiler frost protection."
        )

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(schema),
            description_placeholders={"frost_hint": frost_hint},
        )

    # ── Device management menu ─────────────────────────────────────────────────

    async def async_step_manage_devices(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="manage_devices",
            menu_options={
                "add_trv":       "Add a TRV",
                "add_receiver":  "Add a receiver (SLR1 / SLR2 / OTR1)",
                "add_sensor":    "Add a temperature sensor",
                "remove_device": "Remove a device",
            },
        )

    # ── Add TRV ────────────────────────────────────────────────────────────────

    async def async_step_add_trv(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 1: browse discovered Z2M devices or enter topic manually."""
        errors: dict = {}
        discovered = self._discovered_z2m_topics()

        if user_input is not None:
            selected = (user_input.get("z2m_entity") or "").strip()
            manual   = (user_input.get("mqtt_topic")  or "").strip()
            topic    = selected or manual
            if not topic:
                errors["z2m_entity"] = "required"
            else:
                self._dev_topic = topic
                self._dev_name  = discovered.get(topic, "").split(" (")[0] or topic.split("/")[-1]
                self._dev_type  = DEVICE_TYPE_TRV
                return await self.async_step_confirm_device()

        schema: dict = {}
        if discovered:
            schema[vol.Optional("z2m_entity")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in sorted(discovered.items(), key=lambda x: x[1])
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        schema[vol.Optional("mqtt_topic")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )
        return self.async_show_form(
            step_id="add_trv",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "count": str(len(discovered)),
                "hint":  (
                    f"{len(discovered)} TRV(s) detected in Z2M. Select one or enter the topic manually."
                    if discovered else
                    f"No Z2M TRVs detected yet. Enter the full topic manually, e.g. {self._z2m_base()}/Living Room TRV"
                ),
            },
            errors=errors,
        )

    # ── Add Receiver ───────────────────────────────────────────────────────────

    async def async_step_add_receiver(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 1: browse or enter topic."""
        errors: dict = {}
        discovered = self._discovered_z2m_topics()

        if user_input is not None:
            selected = (user_input.get("z2m_entity") or "").strip()
            manual   = (user_input.get("mqtt_topic")  or "").strip()
            topic    = selected or manual
            if not topic:
                errors["z2m_entity"] = "required"
            else:
                self._dev_topic = topic
                self._dev_name  = discovered.get(topic, "").split(" (")[0] or topic.split("/")[-1]
                self._dev_type  = DEVICE_TYPE_RECEIVER
                return await self.async_step_receiver_model()

        schema: dict = {}
        if discovered:
            schema[vol.Optional("z2m_entity")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in sorted(discovered.items(), key=lambda x: x[1])
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        schema[vol.Optional("mqtt_topic")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )
        return self.async_show_form(
            step_id="add_receiver",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "hint": (
                    f"{len(discovered)} device(s) detected. Select your receiver or enter its topic manually."
                    if discovered else
                    f"Enter the full receiver topic, e.g. {self._z2m_base()}/Hive Receiver"
                ),
            },
            errors=errors,
        )

    async def async_step_receiver_model(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._dev_model = user_input.get("model", MODEL_SLR1)
            return await self.async_step_confirm_device()
        return self.async_show_form(
            step_id="receiver_model",
            data_schema=vol.Schema({
                vol.Required("model", default=MODEL_SLR1): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=RECEIVER_MODELS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={"topic": self._dev_topic},
        )

    # ── Add Sensor ─────────────────────────────────────────────────────────────

    async def async_step_add_sensor(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        if user_input is not None:
            entity_id = user_input.get("sensor_entity", "").strip()
            name      = user_input.get("sensor_name", "").strip()
            if not entity_id:
                errors["sensor_entity"] = "required"
            elif not name:
                errors["sensor_name"] = "required"
            else:
                device_id = str(uuid.uuid4())[:8]
                data = {
                    "type":      DEVICE_TYPE_SENSOR,
                    "name":      name,
                    "entity_id": entity_id,
                }
                c = self._coordinator()
                if c:
                    await c.async_add_device(device_id, data)
                return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema({
                vol.Required("sensor_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Required("sensor_name"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            errors=errors,
        )

    # ── Confirm device (shared by TRV and receiver) ────────────────────────────

    async def async_step_confirm_device(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        if user_input is not None:
            name = user_input.get("device_name", "").strip()
            if not name:
                errors["device_name"] = "required"
            else:
                device_id = str(uuid.uuid4())[:8]
                data: dict = {
                    "type":       self._dev_type,
                    "name":       name,
                    "mqtt_topic": self._dev_topic,
                }
                if self._dev_type == DEVICE_TYPE_RECEIVER:
                    data["model"] = self._dev_model
                c = self._coordinator()
                if c:
                    await c.async_add_device(device_id, data)
                return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="confirm_device",
            data_schema=vol.Schema({
                vol.Required(
                    "device_name",
                    description={"suggested_value": self._dev_name},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            description_placeholders={
                "topic": self._dev_topic,
                "type":  "TRV" if self._dev_type == DEVICE_TYPE_TRV else f"Receiver ({self._dev_model})",
            },
        )

    # ── On-demand heating ─────────────────────────────────────────────────────

    async def async_step_on_demand_heating(self, user_input: dict | None = None) -> config_entries.FlowResult:
        """Top-level on-demand heating menu.

        Shows all registered TRVs and rooms with their current receiver link,
        then lets the user pick which one to configure.
        """
        store     = self._store()
        devices   = self._all_devices()
        rooms     = self._all_rooms()
        receivers = self._registered_receivers()

        options: dict[str, str] = {}

        # Rooms first
        for rid, rd in sorted(rooms.items(), key=lambda x: x[1].get("name","")):
            name     = rd.get("name", rid)
            recv_id  = rd.get("receiver_device_id","")
            recv_lbl = receivers.get(recv_id, "not linked") if recv_id else "not linked"
            options[f"room:{rid}"] = f"{name}  →  {recv_lbl}"

        # Individual TRVs
        for did, dd in sorted(devices.items(), key=lambda x: x[1].get("name","")):
            if dd.get("type") != DEVICE_TYPE_TRV:
                continue
            name     = dd.get("name", did)
            recv_id  = dd.get("receiver_device_id","")
            recv_lbl = receivers.get(recv_id, "not linked") if recv_id else "not linked"
            in_room  = store.room_for_device(did) if store else None
            room_tag = f" (in room)" if in_room else " (standalone)"
            options[f"trv:{did}"] = f"{name}{room_tag}  →  {recv_lbl}"

        if not options:
            return self.async_show_form(
                step_id="on_demand_heating",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "hint": "No TRVs or rooms configured yet. Add a TRV first via Devices."
                },
            )

        if not receivers:
            return self.async_show_form(
                step_id="on_demand_heating",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "hint": "No receiver registered yet. Add a receiver first via Devices."
                },
            )

        # Handle selection
        if user_input is not None:
            target = user_input.get("target", "")
            if target.startswith("room:"):
                self._edit_room_id   = target[5:]
                self._link_device_id = ""
            else:
                self._link_device_id = target[4:]  # strip "trv:"
                self._edit_room_id   = ""
            return await self.async_step_assign_receiver()

        return self.async_show_form(
            step_id="on_demand_heating",
            data_schema=vol.Schema({
                vol.Required("target"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in options.items()
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
            description_placeholders={
                "hint": (
                    "Select a TRV or room to configure. "
                    "The current receiver link is shown next to each name. "
                    "When a TRV or room calls for heat, its linked receiver "
                    "will fire the boiler automatically."
                ),
            },
        )

    async def async_step_on_demand_heating_confirm(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        pass  # handled inline in on_demand_heating step below

    # ── Shared receiver assignment step ───────────────────────────────────────

    async def async_step_assign_receiver(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Assign a receiver to the selected TRV or room."""
        receivers = self._registered_receivers()
        devices   = self._all_devices()
        rooms     = self._all_rooms()

        is_room = bool(self._edit_room_id)
        if is_room:
            target_name    = rooms.get(self._edit_room_id, {}).get("name", self._edit_room_id)
            current_recv   = rooms.get(self._edit_room_id, {}).get("receiver_device_id","")
        else:
            target_name    = devices.get(self._link_device_id, {}).get("name", self._link_device_id)
            current_recv   = devices.get(self._link_device_id, {}).get("receiver_device_id","")

        if user_input is not None:
            recv_id = user_input.get("receiver_device_id") or None
            c       = self._coordinator()
            store   = self._store()

            if is_room:
                if store:
                    rd = dict(store.get_room(self._edit_room_id) or {})
                    rd["receiver_device_id"] = recv_id
                    await store.async_save_room(self._edit_room_id, rd)
                if c:
                    c.assign_room_receiver(self._edit_room_id, recv_id)
            else:
                if c:
                    await c.async_assign_device_receiver(self._link_device_id, recv_id)

            return self.async_create_entry(title="", data=self.config_entry.options or {})

        options = [selector.SelectOptionDict(value="", label="None — remove receiver link")]
        options += [
            selector.SelectOptionDict(value=did, label=name)
            for did, name in sorted(receivers.items(), key=lambda x: x[1])
        ]

        action = "room" if is_room else "TRV"
        return self.async_show_form(
            step_id="assign_receiver",
            data_schema=vol.Schema({
                vol.Optional(
                    "receiver_device_id",
                    default=current_recv or "",
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={
                "target_name": target_name,
                "target_type": action,
                "hint": (
                    f"When {target_name} calls for heat, the selected receiver "
                    "will be commanded to fire the boiler via MQTT."
                ),
            },
        )

    # ── Link TRV to receiver ───────────────────────────────────────────────────

    async def async_step_link_trv_receiver(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 1 — pick which TRV to configure on-demand heating for."""
        devices   = self._all_devices()
        receivers = self._registered_receivers()

        # All TRVs — grouped or standalone (they can all have a receiver)
        trv_options = [
            selector.SelectOptionDict(value=did, label=dd.get("name", did))
            for did, dd in sorted(devices.items(), key=lambda x: x[1].get("name",""))
            if dd.get("type") == DEVICE_TYPE_TRV
        ]

        if not trv_options:
            return self._no_rooms_result()

        if not receivers:
            return self.async_show_form(
                step_id="link_trv_receiver",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "hint": "No receivers registered yet. Add a receiver first via Manage Devices → Add a receiver."
                },
            )

        if user_input is not None:
            self._link_device_id = user_input.get("device_id", "")
            return await self.async_step_link_trv_receiver_assign()

        return self.async_show_form(
            step_id="link_trv_receiver",
            data_schema=vol.Schema({
                vol.Required("device_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=trv_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={
                "hint": (
                    "Select a TRV to configure. When this TRV calls for heat, "
                    "its assigned receiver will be commanded to fire the boiler. "
                    "TRVs inside a room inherit the room's receiver — you can "
                    "override that here."
                ),
            },
        )

    async def async_step_link_trv_receiver_assign(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 2 — pick which receiver to assign to this TRV."""
        devices   = self._all_devices()
        receivers = self._registered_receivers()
        device    = devices.get(self._link_device_id, {})
        dev_name  = device.get("name", self._link_device_id)
        current   = device.get("receiver_device_id", "")

        if user_input is not None:
            recv_id = user_input.get("receiver_device_id") or None
            c = self._coordinator()
            if c:
                await c.async_assign_device_receiver(self._link_device_id, recv_id)
            return self.async_create_entry(title="", data=self.config_entry.options or {})

        options = [selector.SelectOptionDict(value="", label="None — remove receiver link")]
        options += [
            selector.SelectOptionDict(value=did, label=name)
            for did, name in sorted(receivers.items(), key=lambda x: x[1])
        ]

        return self.async_show_form(
            step_id="link_trv_receiver_assign",
            data_schema=vol.Schema({
                vol.Optional(
                    "receiver_device_id",
                    default=current or "",
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={
                "device_name": dev_name,
                "hint": (
                    f"When {dev_name} calls for heat, the selected receiver "
                    "will be commanded to heat via MQTT. "
                    "Select None to remove the link."
                ),
            },
        )

    # ── Remove Device ──────────────────────────────────────────────────────────

    async def async_step_remove_device(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        devices = self._all_devices()
        if not devices:
            return self._no_rooms_result()

        if user_input is not None:
            device_id = user_input.get("device_id")
            if device_id:
                c = self._coordinator()
                if c:
                    await c.async_remove_device(device_id)
            return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema({
                vol.Required("device_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=did,
                                label=f"{dd.get('name', did)} ({dd.get('type', '?')})"
                            )
                            for did, dd in sorted(devices.items(), key=lambda x: x[1].get("name", ""))
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    # ── Room management menu ───────────────────────────────────────────────────

    async def async_step_manage_rooms(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="manage_rooms",
            menu_options={
                "create_room": "Create a new room",
                "edit_room":   "Edit room members",
                "remove_room": "Remove a room",
            },
        )

    # ── Create Room ────────────────────────────────────────────────────────────

    async def async_step_create_room(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        if user_input is not None:
            name = user_input.get("room_name", "").strip()
            if not name:
                errors["room_name"] = "required"
            else:
                self._room_name = name
                return await self.async_step_room_members()
        return self.async_show_form(
            step_id="create_room",
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.TextSelector()
            }),
            errors=errors,
        )

    async def async_step_room_members(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Pick TRVs for this room from registered ungrouped TRVs."""
        errors: dict = {}
        ungrouped = self._ungrouped_trv_ids()
        devices   = self._all_devices()

        # Build options: {device_id: name}
        options = [
            selector.SelectOptionDict(
                value=did,
                label=devices[did].get("name", did)
            )
            for did in ungrouped if did in devices
        ]

        if user_input is not None:
            chosen = user_input.get("device_ids") or []
            if not chosen:
                errors["device_ids"] = "required"
            else:
                self._room_devs = chosen
                return await self.async_step_room_sensors()

        return self.async_show_form(
            step_id="room_members",
            data_schema=vol.Schema({
                vol.Required("device_ids"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options if options else [],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
            description_placeholders={
                "room_name": self._room_name,
                "count":     str(len(ungrouped)),
                "hint":      (
                    f"{len(ungrouped)} TRV(s) available."
                    if ungrouped else
                    "No ungrouped TRVs available. Add TRVs first via Manage Devices."
                ),
            },
            errors=errors,
        )

    async def async_step_room_sensors(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Optionally pick standalone temperature sensors for this room."""
        if user_input is not None:
            self._room_sensors = user_input.get("sensor_ids") or []
            return await self.async_step_room_receiver()

        # Get registered sensor devices
        devices = self._all_devices()
        sensor_options = [
            selector.SelectOptionDict(
                value=did,
                label=devices[did].get("name", did)
            )
            for did, dd in devices.items()
            if dd.get("type") == DEVICE_TYPE_SENSOR
        ]

        schema: dict = {}
        if sensor_options:
            schema[vol.Optional("sensor_ids")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sensor_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="room_sensors",
            data_schema=vol.Schema(schema) if schema else vol.Schema({}),
            description_placeholders={
                "room_name": self._room_name,
                "hint": (
                    "Select any temperature sensors to include in room temperature averaging."
                    if sensor_options else
                    "No standalone sensors registered. You can add them later via Manage Devices."
                ),
            },
        )

    async def async_step_room_receiver(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 4 of 4 — assign a receiver/boiler to this room (optional)."""
        receivers = self._registered_receivers()

        if user_input is not None:
            self._room_receiver = user_input.get("receiver_device_id") or None
            return await self._do_create_room()

        if not receivers:
            # No receivers registered — skip this step
            self._room_receiver = None
            return await self._do_create_room()

        options = [selector.SelectOptionDict(value="", label="None (no receiver assigned)")]
        options += [
            selector.SelectOptionDict(value=did, label=name)
            for did, name in sorted(receivers.items(), key=lambda x: x[1])
        ]

        return self.async_show_form(
            step_id="room_receiver",
            data_schema=vol.Schema({
                vol.Optional("receiver_device_id", default=""): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={
                "room_name": self._room_name,
                "hint": (
                    "Select the receiver that controls heating for this room. "
                    "When any TRV in this room calls for heat, the receiver will be "
                    "told to heat. Leave as None if using the global boiler entity in Settings."
                ),
            },
        )

    async def _do_create_room(self) -> config_entries.FlowResult:
        room_id   = str(uuid.uuid4())
        room_data = {
            "name":               self._room_name,
            "device_ids":         self._room_devs,
            "sensor_ids":         self._room_sensors,
            "schedule":           [],
            "boost_temp":         22.0,
            "boost_minutes":      30,
            "receiver_device_id": getattr(self, "_room_receiver", None),
        }
        c = self._coordinator()
        if c:
            await c.async_add_room(room_id, room_data)
        return self.async_create_entry(title="", data=self.config_entry.options or {})

    # ── Edit Room ──────────────────────────────────────────────────────────────

    async def async_step_edit_room(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self._no_rooms_result()

        if user_input is not None:
            self._edit_room_id = user_input.get("room_id", "")
            return await self.async_step_edit_room_members()

        return self.async_show_form(
            step_id="edit_room",
            data_schema=vol.Schema({
                vol.Required("room_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=rid, label=rd.get("name", rid)
                            )
                            for rid, rd in sorted(
                                rooms.items(), key=lambda x: x[1].get("name", "")
                            )
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_edit_room_members(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        room_data   = self._all_rooms().get(self._edit_room_id, {})
        current_devs = room_data.get("device_ids", [])
        current_sens = room_data.get("sensor_ids", [])

        # TRVs available = ungrouped + current room's members
        ungrouped = self._ungrouped_trv_ids(exclude_room=self._edit_room_id)
        available = sorted(set(current_devs) | set(ungrouped))
        devices   = self._all_devices()

        trv_options = [
            selector.SelectOptionDict(value=did, label=devices[did].get("name", did))
            for did in available if did in devices
        ]
        sensor_options = [
            selector.SelectOptionDict(value=did, label=devices[did].get("name", did))
            for did, dd in devices.items()
            if dd.get("type") == DEVICE_TYPE_SENSOR
        ]

        if user_input is not None:
            new_devs = user_input.get("device_ids") or []
            new_sens = user_input.get("sensor_ids")  or []
            if not new_devs:
                errors["device_ids"] = "required"
            else:
                c = self._coordinator()
                if c:
                    await c.async_update_room(self._edit_room_id, new_devs, new_sens)
                # Get store first — used for all updates below
                store = self._store()

                # Update receiver assignment
                new_receiver = user_input.get("receiver_device_id") or None
                if store:
                    rd2 = dict(store.get_room(self._edit_room_id) or {})
                    rd2["receiver_device_id"] = new_receiver
                    await store.async_save_room(self._edit_room_id, rd2)
                if c:
                    c.assign_room_receiver(self._edit_room_id, new_receiver)

                # Update frost settings
                frost_enabled = user_input.get("frost_enabled", False)
                frost_temp    = float(user_input.get("frost_temperature", 2.0))
                weather_eid   = self._open_meteo_weather_entity()
                if store:
                    rd = dict(store.get_room(self._edit_room_id) or {})
                    rd["frost_enabled"]  = frost_enabled
                    rd["frost_temp"]     = frost_temp
                    rd["weather_entity"] = weather_eid if frost_enabled else None
                    await store.async_save_room(self._edit_room_id, rd)
                    # Update live room object
                    if c:
                        room = c.get_room(self._edit_room_id)
                        if room:
                            room._frost_enabled  = frost_enabled
                            room._frost_temp     = frost_temp
                            room._weather_entity = weather_eid if frost_enabled else None
            if not errors:
                return self.async_create_entry(title="", data=self.config_entry.options or {})

        schema: dict = {
            vol.Required("device_ids", default=current_devs): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=trv_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
        if sensor_options:
            schema[vol.Optional("sensor_ids", default=current_sens)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sensor_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )

        # Add frost protection fields if Open-Meteo is available
        weather_entity     = self._open_meteo_weather_entity()
        open_meteo_ok      = weather_entity is not None
        current_frost      = room_data.get("frost_enabled", False)
        current_frost_temp = float(room_data.get("frost_temp", 2.0))

        if open_meteo_ok:
            schema[vol.Optional("frost_enabled",     default=current_frost)]      = selector.BooleanSelector()
            schema[vol.Optional("frost_temperature", default=current_frost_temp)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-10, max=10, step=0.5,
                    unit_of_measurement="°C",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            )

        # Receiver selector
        receivers = self._registered_receivers()
        current_receiver = room_data.get("receiver_device_id", "")
        if receivers:
            recv_options = [selector.SelectOptionDict(value="", label="None")]
            recv_options += [
                selector.SelectOptionDict(value=did, label=name)
                for did, name in sorted(receivers.items(), key=lambda x: x[1])
            ]
            schema[vol.Optional("receiver_device_id", default=current_receiver or "")] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=recv_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            )

        frost_hint = (
            f"Open-Meteo detected ({weather_entity}). Toggle frost protection below."
            if open_meteo_ok else
            "Install Open-Meteo via HACS to enable weather-based frost protection."
        )

        return self.async_show_form(
            step_id="edit_room_members",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "room_name":  room_data.get("name", self._edit_room_id),
                "frost_hint": frost_hint,
            },
            errors=errors,
        )

    # ── Remove Room ────────────────────────────────────────────────────────────

    async def async_step_remove_room(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self._no_rooms_result()

        if user_input is not None:
            room_id = user_input.get("room_id")
            if room_id:
                c = self._coordinator()
                if c:
                    await c.async_remove_room(room_id)
            return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="remove_room",
            data_schema=vol.Schema({
                vol.Required("room_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=rid, label=rd.get("name", rid)
                            )
                            for rid, rd in sorted(
                                rooms.items(), key=lambda x: x[1].get("name", "")
                            )
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )
