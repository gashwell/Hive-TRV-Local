"""Constants for Hive Local TRV."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "hive_local_trv"
CONFIG_VERSION = 1
MIN_HA_VERSION = "2024.1.0"

# ── Config / options keys ──────────────────────────────────────────────────────
CONF_Z2M_BASE_TOPIC  = "z2m_base_topic"
CONF_BOILER_ENTITY   = "boiler_entity"
CONF_PERSON_ENTITIES = "person_entities"
CONF_ROOMS           = "rooms"

# ── hass.data keys ─────────────────────────────────────────────────────────────
DATA_HUB   = "hub"
DATA_STORE = "store"

# ── Z2M MQTT topics ────────────────────────────────────────────────────────────
TOPIC_BRIDGE_DEVICES          = "{base}/bridge/devices"
TOPIC_BRIDGE_REQUEST_DEVICES  = "{base}/bridge/request/devices"
TOPIC_BRIDGE_RESPONSE_DEVICES = "{base}/bridge/response/devices"
TOPIC_DEVICE_STATE            = "{base}/{name}"
TOPIC_DEVICE_SET              = "{base}/{name}/set"

# ── Supported Hive TRV model strings ──────────────────────────────────────────
SUPPORTED_TRV_MODELS = {"UK7004240", "TRV001"}

# ── Defaults ───────────────────────────────────────────────────────────────────
DEFAULT_Z2M_BASE_TOPIC  = "zigbee2mqtt"
DEFAULT_MIN_TEMP        = 5.0
DEFAULT_MAX_TEMP        = 32.0
DEFAULT_FROST_TEMP      = 7.0
DEFAULT_TEMP_STEP       = 0.5
DEFAULT_BOOST_TEMP      = 22.0
DEFAULT_BOOST_MINUTES   = 30

# ── TRV operating modes ────────────────────────────────────────────────────────
MODE_OFF      = "off"
MODE_MANUAL   = "manual"
MODE_SCHEDULE = "schedule"
MODE_BOOST    = "boost"
MODE_AWAY     = "away"
MODE_HOLIDAY  = "holiday"
ALL_MODES     = [MODE_OFF, MODE_MANUAL, MODE_SCHEDULE, MODE_BOOST, MODE_AWAY, MODE_HOLIDAY]

# ── Schedule day indices (ISO: Mon=0, Sun=6) ───────────────────────────────────
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# ── Sweep interval ─────────────────────────────────────────────────────────────
SWEEP_INTERVAL_S = 30

# ── External sensor heartbeat ──────────────────────────────────────────────────
EXT_SENSOR_HEARTBEAT_S = 180

# ── Platforms ──────────────────────────────────────────────────────────────────
PLATFORMS = ["climate", "sensor", "button", "number", "select"]

# ── Services ───────────────────────────────────────────────────────────────────
SERVICE_BOOST            = "boost"
SERVICE_END_BOOST        = "end_boost"
SERVICE_SET_SCHEDULE     = "set_schedule"
SERVICE_CLEAR_SCHEDULE   = "clear_schedule"
SERVICE_ADVANCE_SCHEDULE = "advance_schedule"
SERVICE_SET_HOLIDAY      = "set_holiday"
SERVICE_CANCEL_HOLIDAY   = "cancel_holiday"
SERVICE_ADD_ROOM         = "add_room"
SERVICE_REMOVE_ROOM      = "remove_room"

ATTR_BOOST_TEMPERATURE  = "temperature"
ATTR_BOOST_DURATION     = "duration"
ATTR_SCHEDULE           = "schedule"
ATTR_ROOM_NAME          = "room_name"
ATTR_ROOM_TRVS          = "trv_entity_ids"
ATTR_ROOM_SENSORS       = "temp_sensor_entity_ids"
ATTR_DEPARTURE          = "departure"
ATTR_RETURN             = "return"
