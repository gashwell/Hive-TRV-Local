"""Config flow for Hive Local — heating only via ZBMINIR2."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
)

from . import const


def required(
    key: str, options: dict[str, Any], default: Any | None = None
) -> vol.Required:
    """Return vol.Required with suggested value."""
    if isinstance(options, dict) and key in options:
        suggested_value = options[key]
    elif default is not None:
        suggested_value = default
    else:
        return vol.Required(key)
    return vol.Required(key, description={"suggested_value": suggested_value})


def optional(
    key: str, options: dict[str, Any], default: Any | None = None
) -> vol.Optional:
    """Return vol.Optional with suggested value."""
    if isinstance(options, dict) and key in options:
        suggested_value = options[key]
    elif default is not None:
        suggested_value = default
    else:
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": suggested_value})


async def general_options_schema(
    handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler,
) -> vol.Schema:
    """Options schema — TRV topic, schedule mode, and ZBMINIR2 switch."""
    return vol.Schema(
        {
            required(const.CONF_MQTT_TOPIC, handler.options): selector.TextSelector(),
            required(
                const.CONF_SHOW_HEAT_SCHEDULE_MODE, handler.options, default=True
            ): selector.BooleanSelector(),
            optional(
                const.CONF_BOILER_SWITCH, handler.options, default=""
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
            ),
            optional(
                const.CONF_Z2M_SWITCH_TOPIC, handler.options, default="zigbee2mqtt/boiler_switch"
            ): selector.TextSelector(),
        }
    )


async def general_config_schema(
    handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler,
) -> vol.Schema:
    """Initial config schema — name, TRV topic, schedule mode, and ZBMINIR2 switch."""
    return vol.Schema(
        {
            required(CONF_NAME, handler.options): selector.TextSelector(),
            required(const.CONF_MQTT_TOPIC, handler.options): selector.TextSelector(),
            required(
                const.CONF_SHOW_HEAT_SCHEDULE_MODE, handler.options, default=True
            ): selector.BooleanSelector(),
            optional(
                const.CONF_BOILER_SWITCH, handler.options, default=""
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
            ),
            optional(
                const.CONF_Z2M_SWITCH_TOPIC, handler.options, default="zigbee2mqtt/boiler_switch"
            ): selector.TextSelector(),
        }
    )


CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(general_config_schema),
}
OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(general_options_schema),
}


# mypy: ignore-errors
class ConfigFlowHandler(SchemaConfigFlowHandler, domain=const.DOMAIN):
    """Handle a config or options flow for Hive Local."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    VERSION = const.CONFIG_VERSION

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""
