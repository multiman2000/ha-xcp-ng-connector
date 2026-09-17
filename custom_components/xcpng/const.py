"""Constants for the XCP-ng / Xen Orchestra integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "xcpng"
MANUFACTURER = "Vates / XCP-ng"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_AUTH_METHOD = "auth_method"
CONF_API_TOKEN = "api_token"
CONF_VERIFY_SSL = "verify_ssl"

AUTH_METHOD_TOKEN = "token"
AUTH_METHOD_PASSWORD = "password"

DEFAULT_VERIFY_SSL = True
DEFAULT_PORT_HINT = 443

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 3600
CONF_SCAN_INTERVAL = "scan_interval"

# How many recent backup log entries to pull per update to find each job's
# latest run. Keeps the request cheap even after months of history.
BACKUP_LOGS_FETCH_LIMIT = 200

ATTRIBUTION = "Data provided by Xen Orchestra"

# --- XO object status / state values -----------------------------------
HOST_POWER_STATE_RUNNING = "Running"
VM_POWER_STATE_RUNNING = "Running"

BACKUP_STATUS_SUCCESS = "success"
BACKUP_STATUS_SKIPPED = "skipped"
BACKUP_STATUS_INTERRUPTED = "interrupted"
BACKUP_STATUS_FAILURE = "failure"
BACKUP_STATUS_PENDING = "pending"
BACKUP_STATUS_UNKNOWN = "unknown"
