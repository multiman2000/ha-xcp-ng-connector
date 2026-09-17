"""Config flow for the XCP-ng / Xen Orchestra integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import XcpngApiError, XcpngAuthError, XcpngClient, XcpngConnectionError
from .const import (
    AUTH_METHOD_PASSWORD,
    AUTH_METHOD_TOKEN,
    CONF_API_TOKEN,
    CONF_AUTH_METHOD,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

AUTH_METHOD_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[AUTH_METHOD_TOKEN, AUTH_METHOD_PASSWORD],
        mode=SelectSelectorMode.LIST,
        translation_key=CONF_AUTH_METHOD,
    )
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
        vol.Required(CONF_AUTH_METHOD, default=AUTH_METHOD_TOKEN): AUTH_METHOD_SELECTOR,
    }
)
TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})
PASSWORD_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def _async_validate_and_get_pool_id(hass, data: dict[str, Any]) -> str | None:
    """Try to talk to the XO REST API and return an id to key uniqueness on."""
    session = async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL])
    if data[CONF_AUTH_METHOD] == AUTH_METHOD_TOKEN:
        client = XcpngClient(session, data[CONF_HOST], api_token=data[CONF_API_TOKEN])
    else:
        client = XcpngClient(
            session,
            data[CONF_HOST],
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
        )
    pools = await client.async_list("pools", fields=["id"])
    return pools[0]["id"] if pools else None


class XcpngConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for XCP-ng / Xen Orchestra."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._reauth_entry_id: str | None = None

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication after the coordinator got a 401."""
        self._reauth_entry_id = self.context["entry_id"]
        self._data = dict(entry_data)
        if entry_data.get(CONF_AUTH_METHOD) == AUTH_METHOD_TOKEN:
            return await self.async_step_token()
        return await self.async_step_password()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = user_input
            if user_input[CONF_AUTH_METHOD] == AUTH_METHOD_TOKEN:
                return await self.async_step_token()
            return await self.async_step_password()

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_step_credentials("token", TOKEN_SCHEMA, user_input)

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_step_credentials(
            "password", PASSWORD_SCHEMA, user_input
        )

    async def _async_step_credentials(
        self,
        step_id: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._data, **user_input}
            try:
                pool_id = await _async_validate_and_get_pool_id(self.hass, data)
            except XcpngAuthError:
                errors["base"] = "invalid_auth"
            except XcpngConnectionError:
                errors["base"] = "cannot_connect"
            except XcpngApiError:
                _LOGGER.exception("Unexpected error validating XCP-ng connection")
                errors["base"] = "unknown"
            else:
                if self._reauth_entry_id is not None:
                    entry = self.hass.config_entries.async_get_entry(
                        self._reauth_entry_id
                    )
                    return self.async_update_reload_and_abort(entry, data=data)
                if pool_id is not None:
                    await self.async_set_unique_id(pool_id)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_HOST], data=data)

        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return XcpngOptionsFlow()


class XcpngOptionsFlow(OptionsFlow):
    """Let the user tune the polling interval after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL, step=5)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
