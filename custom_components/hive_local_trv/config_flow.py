"""Config flow for Hive Local TRV."""
from __future__ import annotations

import logging
from typing import Any

_L = logging.getLogger("custom_components.hive_local_trv.config_flow")
_L.warning("HIVE_DIAG config_flow: module import started")

try:
    import voluptuous as vol
    from homeassistant import config_entries
    from homeassistant.core import callback
    from homeassistant.helpers import selector
    _L.warning("HIVE_DIAG config_flow: imports OK")
except Exception as exc:
    _L.error("HIVE_DIAG config_flow: import FAILED: %s", exc, exc_info=True)
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
    _L.warning("HIVE_DIAG config_flow: const OK — DOMAIN=%s", DOMAIN)
except Exception as exc:
    _L.error("HIVE_DIAG config_flow: const FAILED: %s", exc, exc_info=True)
    raise

_L.warning("HIVE_DIAG config_flow: defining flow class")


class HiveLocalTRVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — single step: Z2M base topic only."""

    VERSION = CONFIG_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show setup form or process submission."""
        _L.warning("HIVE_DIAG async_step_user called — user_input=%s", user_input)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base = user_input[CONF_Z2M_BASE_TOPIC].strip().rstrip("/")
                _L.warning("HIVE_DIAG async_step_user: base_topic=%s", base)
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
            except Exception as exc:
                _L.error("HIVE_DIAG async_step_user: submit FAILED: %s", exc, exc_info=True)
                errors["base"] = "unknown"

        _L.warning("HIVE_DIAG async_step_user: building form schema")
        try:
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_Z2M_BASE_TOPIC,
                        default=DEFAULT_Z2M_BASE_TOPIC,
                    ): selector.TextSelector(),
                }
            )
            _L.warning("HIVE_DIAG async_step_user: schema OK, showing form")
            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors=errors,
            )
        except Exception as exc:
            _L.error("HIVE_DIAG async_step_user: form FAILED: %s", exc, exc_info=True)
            raise

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "HiveLocalTRVOptionsFlow":
        """Return the options flow handler."""
        _L.warning("HIVE_DIAG async_get_options_flow called")
        return HiveLocalTRVOptionsFlow()


class HiveLocalTRVOptionsFlow(config_entries.OptionsFlow):
    """Options flow — boiler entity and geofencing."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show options form or save."""
        _L.warning("HIVE_DIAG options async_step_init — user_input=%s", user_input)

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_BOILER_ENTITY: user_input.get(CONF_BOILER_ENTITY) or None,
                    CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES) or [],
                },
            )

        try:
            entry = self.config_entry
            current_boiler  = entry.options.get(CONF_BOILER_ENTITY)  or entry.data.get(CONF_BOILER_ENTITY)
            current_persons = entry.options.get(CONF_PERSON_ENTITIES) or entry.data.get(CONF_PERSON_ENTITIES, [])
        except Exception as exc:
            _L.error("HIVE_DIAG options: reading config_entry FAILED: %s", exc, exc_info=True)
            current_boiler  = None
            current_persons = []

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
                        selector.EntitySelectorConfig(domain="person", multiple=True)
                    ),
                }
            ),
        )


_L.warning("HIVE_DIAG config_flow: module load COMPLETE")
