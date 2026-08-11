"""Constants for Hive Local v5."""
from __future__ import annotations

DOMAIN    = "hive_local"
VERSION   = "5.0.0"

# ── Platforms ──────────────────────────────────────────────────────────────────
PLATFORMS = ["climate", "sensor", "number", "button", "select", "switch", "binary_sensor"]

# ── Config entry keys ──────────────────────────────────────────────────────────
CONF_Z2M_BASE_TOPIC   = "z2m_base_topic"
CONF_BOILER_ENTITY    = "boiler_entity"
CONF_ENABLE_DIAG      = "enable_diagnostics"
CONF_FROST_ENABLED    = "frost_protection_enabled"
CONF_FROST_TEMP       = "frost_protection_temp"
CONF_FROST_WEATHER    = "frost_protection_weather_entity"

# ── Device type keys (stored per device in hass.data) ─────────────────────────
DEVICE_TYPE_TRV       = "trv"
DEVICE_TYPE_RECEIVER  = "receiver"
DEVICE_TYPE_SENSOR    = "sensor"

# ── Receiver models ────────────────────────────────────────────────────────────
MODEL_SLR1 = "SLR1"
MODEL_SLR2 = "SLR2"  # dual channel — water scope reserved for future
MODEL_OTR1 = "OTR1"
RECEIVER_MODELS = [MODEL_SLR1, MODEL_SLR2, MODEL_OTR1]

# ── hass.data keys ─────────────────────────────────────────────────────────────
DATA_COORDINATOR = "coordinator"   # HiveLocalCoordinator (single, manages everything)
DATA_STORE       = "store"

# ── Modes ──────────────────────────────────────────────────────────────────────
MODE_SCHEDULE = "schedule"
MODE_MANUAL   = "manual"
MODE_BOOST    = "boost"
MODE_OFF      = "off"
ALL_MODES     = [MODE_SCHEDULE, MODE_MANUAL, MODE_BOOST, MODE_OFF]

# ── Defaults ───────────────────────────────────────────────────────────────────
DEFAULT_BOOST_TEMP     = 22.0
DEFAULT_BOOST_MINUTES  = 30
DEFAULT_FROST_TEMP     = 7.0
DEFAULT_TARGET_TEMP    = 20.0
DEFAULT_Z2M_TOPIC      = "zigbee2mqtt"
MAX_BOOST_MINUTES      = 360
MIN_TEMP               = 5.0
MAX_TEMP               = 32.0
TEMP_STEP              = 0.5

# ── Z2M special modes ─────────────────────────────────────────────────────────
Z2M_BOOST_MODE = "emergency_heating"

# ── Storage schema ─────────────────────────────────────────────────────────────
STORAGE_VERSION = 1
STORAGE_KEY     = DOMAIN

# ── Events ─────────────────────────────────────────────────────────────────────
EVENT_DEVICE_ADDED   = f"{DOMAIN}_device_added"
EVENT_DEVICE_REMOVED = f"{DOMAIN}_device_removed"
EVENT_ROOM_ADDED     = f"{DOMAIN}_room_added"
EVENT_ROOM_REMOVED   = f"{DOMAIN}_room_removed"
EVENT_ROOM_UPDATED   = f"{DOMAIN}_room_updated"

# ── Services ───────────────────────────────────────────────────────────────────
SVC_ROOM_BOOST           = "room_boost"
SVC_ROOM_END_BOOST       = "room_end_boost"
SVC_ROOM_SET_SCHEDULE    = "room_set_schedule"
SVC_ROOM_CLEAR_SCHEDULE  = "room_clear_schedule"
SVC_DEVICE_BOOST         = "device_boost"
SVC_DEVICE_END_BOOST     = "device_end_boost"

# ── Service attribute names ────────────────────────────────────────────────────
ATTR_TEMPERATURE        = "temperature"
ATTR_DURATION_MINUTES   = "duration_minutes"
ATTR_SCHEDULE           = "schedule"
ATTR_DEVICE_ID          = "device_id"

# ── Unique ID patterns ─────────────────────────────────────────────────────────
# Device climate:  hive_local_{device_id}_climate
# Device sensor:   hive_local_{device_id}_{sensor_type}
# Room climate:    hive_local_room_{room_id}_climate
# Room button:     hive_local_room_{room_id}_{action}
def uid_device(device_id: str, suffix: str) -> str:
    return f"{DOMAIN}_{device_id}_{suffix}"

def uid_room(room_id: str, suffix: str) -> str:
    return f"{DOMAIN}_room_{room_id}_{suffix}"
