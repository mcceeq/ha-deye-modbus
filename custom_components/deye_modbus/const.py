"""Constants for the Deye Modbus integration."""

from datetime import timedelta
DOMAIN = "deye_modbus"
# Dynamic platforms driven by external definitions
PLATFORMS: list[str] = ["sensor", "number", "select", "switch"]

CONF_CONNECTION_TYPE = "connection_type"
CONNECTION_TYPE_RTU = "rtu"
CONNECTION_TYPE_TCP = "tcp"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_DEVICE = "device"
CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_SLAVE_ID = "slave_id"

DEFAULT_CONNECTION_TYPE = CONNECTION_TYPE_RTU
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 502
DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"  # None/Even/Odd as N/E/O for pymodbus
DEFAULT_STOPBITS = 1
DEFAULT_SLAVE_ID = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=1)
DEFINITION_SCAN_INTERVAL = timedelta(seconds=1)
