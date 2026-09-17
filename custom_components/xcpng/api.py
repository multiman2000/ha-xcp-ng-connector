"""Thin async client for the Xen Orchestra REST API (/rest/v0).

Only the read-only pieces needed to monitor an XCP-ng pool/hosts/VMs/SRs
and XOA (Xen Orchestra Appliance) backup jobs are implemented. See
https://docs.xen-orchestra.com/automation/restapi for the upstream docs.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

REST_BASE = "rest/v0"


class XcpngApiError(Exception):
    """Generic error talking to the Xen Orchestra REST API."""


class XcpngAuthError(XcpngApiError):
    """Raised when authentication fails (HTTP 401)."""


class XcpngConnectionError(XcpngApiError):
    """Raised when the host cannot be reached at all."""


class XcpngClient:
    """Small wrapper around the XO REST API using an existing aiohttp session."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        *,
        api_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Create the client.

        `session` is expected to already be configured for TLS verification
        (see `homeassistant.helpers.aiohttp_client.async_get_clientsession`),
        so this class does not touch SSL settings itself.
        """
        self._session = session
        origin = self._normalize_host(host)
        self._origin = origin
        self._base_url = f"{origin}/{REST_BASE}"
        self._api_token = api_token
        self._username = username
        self._password = password

    @staticmethod
    def _normalize_host(host: str) -> str:
        host = host.strip()
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        return host.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_token:
            # The XO REST API expects the token as a cookie, not a bearer
            # header. Setting it directly avoids surprises from aiohttp's
            # cookie jar (domain/secure-flag handling) with self-signed certs.
            headers["Cookie"] = f"authenticationToken={self._api_token}"
        return headers

    def _auth(self) -> aiohttp.BasicAuth | None:
        if self._api_token:
            return None
        if self._username is not None and self._password is not None:
            return aiohttp.BasicAuth(self._username, self._password)
        return None

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a path. `path` may be a full URL/href or a relative one."""
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        elif path.startswith("/"):
            # href values returned by the API are rooted at the server, e.g.
            # "/rest/v0/hosts/<uuid>".
            url = f"{self._origin}{path}"
        else:
            url = f"{self._base_url}/{path}"

        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                auth=self._auth(),
                params=params,
            ) as resp:
                if resp.status == 401:
                    raise XcpngAuthError(f"Authentication failed for {url}")
                if resp.status >= 400:
                    body = await resp.text()
                    raise XcpngApiError(
                        f"Request to {url} failed with HTTP {resp.status}: {body[:200]}"
                    )
                return await resp.json(content_type=None)
        except aiohttp.ClientConnectorError as err:
            raise XcpngConnectionError(f"Cannot connect to {url}: {err}") from err
        except aiohttp.ClientError as err:
            raise XcpngApiError(f"Error requesting {url}: {err}") from err

    async def async_list(
        self, collection: str, fields: list[str] | None = None, **params: Any
    ) -> list[dict[str, Any]]:
        """Return a collection, optionally projected to a set of fields.

        Without `fields`, the API returns plain href strings, so callers
        that need data (not just ids) should always pass `fields`.
        """
        query: dict[str, Any] = dict(params)
        if fields:
            query["fields"] = ",".join(fields)
        result = await self._request(collection, params=query)
        if not isinstance(result, list):
            raise XcpngApiError(f"Expected a list from {collection}, got {type(result)}")
        return result

    async def async_get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fetch a single full object by href or relative path."""
        result = await self._request(path, params=params)
        if not isinstance(result, dict):
            raise XcpngApiError(f"Expected an object from {path}, got {type(result)}")
        return result

    async def async_get_host_stats(
        self, host_id: str, granularity: str = "seconds"
    ) -> dict[str, Any]:
        return await self.async_get(
            f"hosts/{host_id}/stats", params={"granularity": granularity}
        )

    async def async_test_connection(self) -> None:
        """Raise if the credentials/URL don't work. Used by the config flow."""
        await self.async_list("pools", fields=["id"])
