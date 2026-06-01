"""Config flow for Hive Local TRV.

Uses the modern SchemaConfigFlowHandler pattern as recommended by
HA integration quality guidelines. Initial setup is a single field
(Z2M base topic). All other settings are in the options flow, accessible
via Configure after installation.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_BOILER_ENTITY,
    CONF_PERSON_ENTITIES,
    CONF_Z2M_BASE_TOPIC,
    CONFIG_VERSION,
    DEFAULT_Z2M_BASE_TOPIC,
    DOMAIN,
)


def _setup_schema(handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler) -> vol.Schema:
    """Schema for initial setup — Z2M base topic only."""
    return vol.Schema(
        {
            vol.Required(
                CONF_Z2M_BASE_TOPIC,
                default=DEFAULT_Z2M_BASE_TOPIC,
            ): selector.TextSelector(
                selector.TextSelectorConfig(placeholder="zigbee2mqtt")
            ),
        }
    )


def _options_schema(handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler) -> vol.Schema:
    """Schema for options — boiler entity and geofencing persons."""
    options = handler.options if isinstance(handler.options, dict) else {}
    current_boiler  = options.get(CONF_BOILER_ENTITY)
    current_persons = options.get(CONF_PERSON_ENTITIES, [])

    schema: dict = {
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
            selector.EntitySelectorConfig(domain="person", multiple=True)
        ),
    }
    return vol.Schema(schema)


CONFIG_FLOW: dict[str, SchemaFlowFormStep] = {
    "user": SchemaFlowFormStep(_setup_schema),
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep] = {
    "init": SchemaFlowFormStep(_options_schema),
}


class HiveLocalTRVConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """Config flow for Hive Local TRV.

    SchemaConfigFlowHandler handles async_step_user, unique ID management,
    and options flow wiring automatically.
    """

    config_flow  = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    VERSION = CONFIG_VERSION

    @callback
    def async_config_entry_title(self, options: dict[str, Any]) -> str:
        """Title for the config entry."""
        base = options.get(CONF_Z2M_BASE_TOPIC, "zigbee2mqtt")
        return f"Hive TRVs ({base})"
