"""Constants for the Deye Modbus integration."""

from datetime import timedelta
DOMAIN = "deye_modbus"
# Dynamic platforms driven by external definitions
PLATFORMS: list[str] = ["sensor", "number", "select", "switch", "datetime", "time"]

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
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_CONNECTION_TYPE = CONNECTION_TYPE_RTU
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 502
DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"  # None/Even/Odd as N/E/O for pymodbus
DEFAULT_STOPBITS = 1
DEFAULT_SLAVE_ID = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=2)
DEFINITION_SCAN_INTERVAL = timedelta(seconds=1)
SLOW_POLL_INTERVAL = timedelta(seconds=5)

# High-frequency poll spans (address, count) for realtime values
FAST_POLL_SPANS: list[tuple[int, int]] = [
    (150, 9),   # voltages
    (160, 25),  # currents/power around 0x00A0-0x00B8
    (173, 8),   # output/load power
    (182, 8),   # battery temp/voltage/SOC/PV power
    (190, 5),   # battery power/current, frequencies
]
