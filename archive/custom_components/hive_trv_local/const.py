"""Constants for Hive TRV Local v4."""
from __future__ import annotations

DOMAIN    = "hive_trv_local"

# ── Entry types ────────────────────────────────────────────────────────────────
ENTRY_TYPE_TRV      = "trv"
ENTRY_TYPE_RECEIVER = "receiver"
ENTRY_TYPE_GROUPS   = "groups"

# ── Config versions ────────────────────────────────────────────────────────────
CONFIG_VERSION_DEVICE = 1
CONFIG_VERSION_GROUPS = 1
SCHEMA_VERSION        = 1

# ── Config keys ────────────────────────────────────────────────────────────────
CONF_ENTRY_TYPE      = "entry_type"
CONF_MQTT_TOPIC      = "mqtt_topic"
CONF_DEVICE_NAME     = "device_name"
CONF_MODEL           = "model"
CONF_BOILER_ENTITY   = "boiler_entity"
CONF_SHOW_HEAT_SCHED = "show_heat_schedule_mode"
CONF_SHOW_WATER_SCHED= "show_water_schedule_mode"
CONF_ENABLE_DIAG     = "enable_diagnostics"

# ── Receiver models ────────────────────────────────────────────────────────────
MODEL_SLR1 = "SLR1"
MODEL_SLR2 = "SLR2"
MODEL_OTR1 = "OTR1"
RECEIVER_MODELS = [MODEL_SLR1, MODEL_SLR2, MODEL_OTR1]

# ── Platforms ──────────────────────────────────────────────────────────────────
PLATFORMS_TRV      = ["climate", "sensor", "number"]
PLATFORMS_RECEIVER = ["climate", "sensor", "button", "number", "select"]
PLATFORMS_GROUPS   = ["climate", "button", "number"]

# ── hass.data keys ─────────────────────────────────────────────────────────────
DATA_STORE   = "store"
DATA_BOILER  = "boiler_mgr"

# ── Group modes ────────────────────────────────────────────────────────────────
MODE_MANUAL   = "manual"
MODE_SCHEDULE = "schedule"
MODE_BOOST    = "boost"
MODE_OFF      = "off"

# ── Defaults ───────────────────────────────────────────────────────────────────
DEFAULT_BOOST_TEMP           = 22.0
DEFAULT_BOOST_MINUTES        = 30
DEFAULT_FROST_TEMP           = 7.0
DEFAULT_HEATING_BOOST_TEMP   = 25.0
DEFAULT_HEATING_BOOST_MINS   = 30
DEFAULT_WATER_BOOST_MINS     = 30
MAXIMUM_BOOST_MINUTES        = 360

# ── Hive boost MQTT mode ───────────────────────────────────────────────────────
HIVE_BOOST = "emergency_heating"

# ── Group events ───────────────────────────────────────────────────────────────
EVENT_ROOM_ADDED   = f"{DOMAIN}_room_added"
EVENT_ROOM_REMOVED = f"{DOMAIN}_room_removed"
EVENT_ROOM_UPDATED = f"{DOMAIN}_room_updated"

# ── Group services ─────────────────────────────────────────────────────────────
SERVICE_GROUP_BOOST            = "group_boost"
SERVICE_GROUP_END_BOOST        = "group_end_boost"
SERVICE_GROUP_SET_SCHEDULE     = "group_set_schedule"
SERVICE_GROUP_CLEAR_SCHEDULE   = "group_clear_schedule"
SERVICE_GROUP_ADVANCE_SCHEDULE = "group_advance_schedule"

ATTR_BOOST_TEMPERATURE = "temperature"
ATTR_BOOST_DURATION    = "duration_minutes"
ATTR_SCHEDULE          = "schedule"
