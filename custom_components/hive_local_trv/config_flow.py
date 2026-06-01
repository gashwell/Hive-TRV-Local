"""Config flow — Hive Local TRV.

Initial setup only asks for the Zigbee2MQTT base topic.
TRVs are discovered automatically once the integration is running.
Boiler entity and geofencing persons are configured via Options after install.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BOILER_ENTITY,
    CONF_PERSON_ENTITIES,
    CONF_Z2M_BASE_TOPIC,
    DEFAULT_Z2M_BASE_TOPIC,
    DOMAIN,
)


class HiveLocalTRVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — minimal single step: just the Z2M base topic.

    TRVs are auto-discovered after setup. Use the Configure button
    (Settings → Integrations → Hive Local TRV → Configure) to add
    a boiler entity or geofencing persons at any time.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Single-step setup: Zigbee2MQTT base topic only."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not mqtt.async_get_mqtt_data(self.hass):
                errors["base"] = "mqtt_unavailable"
            else:
                base = user_input[CONF_Z2M_BASE_TOPIC].strip().rstrip("/")
                await self.async_set_unique_id(base)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Hive TRVs",
                    data={
                        CONF_Z2M_BASE_TOPIC: base,
                        CONF_BOILER_ENTITY: None,
                        CONF_PERSON_ENTITIES: [],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_Z2M_BASE_TOPIC, default=DEFAULT_Z2M_BASE_TOPIC
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(placeholder="zigbee2mqtt")
                    ),
                }
            ),
            description_placeholders={
                "note": (
                    "TRVs are discovered automatically. "
                    "Use Configure to add a boiler entity or geofencing after install."
                )
            },
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        entry: config_entries.ConfigEntry,
    ) -> HiveLocalTRVOptionsFlow:
        """Return the options flow."""
        return HiveLocalTRVOptionsFlow(entry)


class HiveLocalTRVOptionsFlow(config_entries.OptionsFlow):
    """Options flow — add/change boiler entity and geofencing persons."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialise."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_BOILER_ENTITY: user_input.get(CONF_BOILER_ENTITY) or None,
                    CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES) or [],
                },
            )

        # Prefer options values (re-configure), fall back to original data
        current_boiler = self._entry.options.get(
            CONF_BOILER_ENTITY, self._entry.data.get(CONF_BOILER_ENTITY)
        )
        current_persons = self._entry.options.get(
            CONF_PERSON_ENTITIES, self._entry.data.get(CONF_PERSON_ENTITIES, [])
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BOILER_ENTITY,
                        description={"suggested_value": current_boiler},
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["climate", "switch", "input_boolean"]
                        )
                    ),
                    vol.Optional(
                        CONF_PERSON_ENTITIES,
                        description={"suggested_value": current_persons},
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="person", multiple=True
                        )
                    ),
                }
            ),
        )
