"""Constants for Hive Local Thermostat."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

MIN_HA_VERSION = "2025.4"

DOMAIN = "hive_local"
CONFIG_VERSION = 1

CONF_MQTT_TOPIC         = "mqtt_topic"
CONF_BOILER_SWITCH      = "boiler_switch"
CONF_Z2M_SWITCH_TOPIC  = "z2m_switch_topic"
CONF_MODEL = "model"
CONF_SHOW_HEAT_SCHEDULE_MODE = "show_heat_schedule_mode"
CONF_SHOW_WATER_SCHEDULE_MODE = "show_water_schedule_mode"

MODEL_ZBMINIR2 = "ZBMINIR2"

MODELS = [
    MODEL_ZBMINIR2,
]

# Water heating not applicable for ZBMINIR2 solution
MODEL_SLR2 = None  # kept for compatibility reference only

HIVE_BOOST = "emergency_heat"

DEFAULT_FROST_TEMPERATURE = 12
DEFAULT_HEATING_BOOST_MINUTES = 120
DEFAULT_HEATING_BOOST_TEMPERATURE = 25
DEFAULT_WATER_BOOST_MINUTES = 60

MAXIMUM_BOOST_MINUTES = 180
