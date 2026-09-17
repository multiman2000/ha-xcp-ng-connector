"""The XCP-ng / Xen Orchestra integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import XcpngApiError, XcpngAuthError, XcpngClient
from .const import (
    AUTH_METHOD_TOKEN,
    CONF_API_TOKEN,
    CONF_AUTH_METHOD,
    CONF_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import XcpngDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up XCP-ng / Xen Orchestra from a config entry."""
    data = entry.data
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True))

    if data.get(CONF_AUTH_METHOD) == AUTH_METHOD_TOKEN:
        client = XcpngClient(session, data[CONF_HOST], api_token=data[CONF_API_TOKEN])
    else:
        client = XcpngClient(
            session,
            data[CONF_HOST],
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
        )

    coordinator = XcpngDataUpdateCoordinator(hass, entry, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except XcpngAuthError as err:
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err
    except XcpngApiError as err:
        raise ConfigEntryNotReady(f"Could not reach Xen Orchestra: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
