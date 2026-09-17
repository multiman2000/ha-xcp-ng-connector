"""Diagnostics support for the XCP-ng / Xen Orchestra integration."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_TOKEN, DOMAIN
from .coordinator import XcpngDataUpdateCoordinator

TO_REDACT = {CONF_API_TOKEN, "password", "username", "host", "address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: XcpngDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "data": async_redact_data(asdict(coordinator.data), TO_REDACT),
    }
