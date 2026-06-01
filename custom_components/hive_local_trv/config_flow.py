"""Config flow for Hive Local TRV — DIAGNOSTIC BUILD.

Every step is wrapped in try/except and logged at WARNING level
so it appears in the HA log regardless of log level settings.
Check Settings → System → Logs after attempting to add the integration.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

_LOGGER.warning("DIAG [config_flow] module load started")

try:
    from homeassistant.core import callback
    _LOGGER.warning("DIAG [config_flow] homeassistant.core imported OK")
except Exception as exc:
    _LOGGER.error("DIAG [config_flow] FAILED to import homeassistant.core: %s", exc)
    raise

try:
    from homeassistant.helpers import selector
    _LOGGER.warning("DIAG [config_flow] homeassistant.helpers.selector imported OK")
except Exception as exc:
    _LOGGER.error("DIAG [config_flow] FAILED to import selector: %s", exc)
    raise

try:
    from homeassistant.helpers.schema_config_entry_flow import (
        SchemaConfigFlowHandler,
        SchemaFlowFormStep,
        SchemaOptionsFlowHandler,
    )
    _LOGGER.warning("DIAG [config_flow] SchemaConfigFlowHandler imported OK")
except Exception as exc:
    _LOGGER.error("DIAG [config_flow] FAILED to import SchemaConfigFlowHandler: %s", exc)
    raise

try:
    from .const import (
        CONF_BOILER_ENTITY,
        CONF_PERSON_ENTITIES,
        CONF_Z2M_BASE_TOPIC,
        CONFIG_VERSION,
        DEFAULT_Z2M_BASE_TOPIC,
        DOMAIN,
    )
    _LOGGER.warning(
        "DIAG [config_flow] .const imported OK — DOMAIN=%s CONFIG_VERSION=%s",
        DOMAIN, CONFIG_VERSION,
    )
except Exception as exc:
    _LOGGER.error("DIAG [config_flow] FAILED to import from .const: %s", exc)
    raise

_LOGGER.warning("DIAG [config_flow] all imports complete, defining schema functions")


def _setup_schema(handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler) -> vol.Schema:
    """Schema for initial setup step."""
    _LOGGER.warning("DIAG [config_flow] _setup_schema called — handler type: %s", type(handler).__name__)
    try:
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_Z2M_BASE_TOPIC,
                    default=DEFAULT_Z2M_BASE_TOPIC,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(placeholder="zigbee2mqtt")
                ),
            }
        )
        _LOGGER.warning("DIAG [config_flow] _setup_schema built successfully")
        return schema
    except Exception as exc:
        _LOGGER.error("DIAG [config_flow] _setup_schema FAILED: %s", exc, exc_info=True)
        raise


def _options_schema(handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler) -> vol.Schema:
    """Schema for options flow."""
    _LOGGER.warning("DIAG [config_flow] _options_schema called — handler type: %s", type(handler).__name__)
    try:
        options = handler.options if isinstance(handler.options, dict) else {}
        _LOGGER.warning("DIAG [config_flow] options data: %s", options)

        current_boiler  = options.get(CONF_BOILER_ENTITY)
        current_persons = options.get(CONF_PERSON_ENTITIES, [])

        schema = vol.Schema(
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
                    selector.EntitySelectorConfig(domain="person", multiple=True)
                ),
            }
        )
        _LOGGER.warning("DIAG [config_flow] _options_schema built successfully")
        return schema
    except Exception as exc:
        _LOGGER.error("DIAG [config_flow] _options_schema FAILED: %s", exc, exc_info=True)
        raise


_LOGGER.warning("DIAG [config_flow] defining CONFIG_FLOW and OPTIONS_FLOW dicts")

CONFIG_FLOW: dict[str, SchemaFlowFormStep] = {
    "user": SchemaFlowFormStep(_setup_schema),
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep] = {
    "init": SchemaFlowFormStep(_options_schema),
}

_LOGGER.warning("DIAG [config_flow] defining HiveLocalTRVConfigFlow class")


class HiveLocalTRVConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """Config flow for Hive Local TRV — DIAGNOSTIC BUILD."""

    config_flow  = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    VERSION = CONFIG_VERSION

    def __init_subclass__(cls, **kwargs: Any) -> None:
        _LOGGER.warning("DIAG [config_flow] __init_subclass__ called for %s", cls.__name__)
        super().__init_subclass__(**kwargs)

    @callback
    def async_config_entry_title(self, options: dict[str, Any]) -> str:
        """Title for the config entry."""
        _LOGGER.warning("DIAG [config_flow] async_config_entry_title called — options: %s", options)
        try:
            base = options.get(CONF_Z2M_BASE_TOPIC, "zigbee2mqtt")
            title = f"Hive TRVs ({base})"
            _LOGGER.warning("DIAG [config_flow] title will be: %s", title)
            return title
        except Exception as exc:
            _LOGGER.error("DIAG [config_flow] async_config_entry_title FAILED: %s", exc, exc_info=True)
            return "Hive TRVs"


_LOGGER.warning("DIAG [config_flow] module load COMPLETE — HiveLocalTRVConfigFlow defined")
