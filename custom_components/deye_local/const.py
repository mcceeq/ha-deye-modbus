"""Constants for the Deye Local integration."""

from datetime import timedelta
from homeassistant.const import Platform

DOMAIN = "deye_modbus"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"

DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
