"""Constants for Hive TRV Local v3."""
from __future__ import annotations

DOMAIN    = "hive_trv_local"
PLATFORMS = ["climate", "button", "number"]

# ── Config entry ───────────────────────────────────────────────────────────────
CONFIG_VERSION = 1
SCHEMA_VERSION = 1

CONF_BOILER_ENTITY      = "boiler_entity"
CONF_ENABLE_DIAGNOSTICS = "enable_diagnostics"
CONF_Z2M_BASE_TOPIC     = "z2m_base_topic"

ENTRY_DEFAULTS: dict = {
    CONF_BOILER_ENTITY:      None,
    CONF_ENABLE_DIAGNOSTICS: False,
    CONF_Z2M_BASE_TOPIC:     "zigbee2mqtt",
}

# ── hass.data keys ─────────────────────────────────────────────────────────────
DATA_STORE   = "store"
DATA_BOILER  = "boiler_mgr"

# ── Modes ──────────────────────────────────────────────────────────────────────
MODE_MANUAL   = "manual"
MODE_SCHEDULE = "schedule"
MODE_BOOST    = "boost"
MODE_OFF      = "off"

# ── Boost defaults ─────────────────────────────────────────────────────────────
DEFAULT_BOOST_TEMP    = 22.0
DEFAULT_BOOST_MINUTES = 30
DEFAULT_FROST_TEMP    = 7.0

# ── Services ───────────────────────────────────────────────────────────────────
SERVICE_BOOST            = "boost"
SERVICE_END_BOOST        = "end_boost"
SERVICE_SET_SCHEDULE     = "set_schedule"
SERVICE_CLEAR_SCHEDULE   = "clear_schedule"
SERVICE_ADVANCE_SCHEDULE = "advance_schedule"

# ── Events ─────────────────────────────────────────────────────────────────────
EVENT_ROOM_ADDED   = f"{DOMAIN}_room_added"
EVENT_ROOM_REMOVED = f"{DOMAIN}_room_removed"
EVENT_ROOM_UPDATED = f"{DOMAIN}_room_updated"

# ── Service attribute names ────────────────────────────────────────────────────
ATTR_BOOST_TEMPERATURE = "temperature"
ATTR_BOOST_DURATION    = "duration_minutes"
ATTR_SCHEDULE          = "schedule"
