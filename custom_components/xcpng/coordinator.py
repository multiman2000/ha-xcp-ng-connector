"""Data update coordinator for the XCP-ng / Xen Orchestra integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import XcpngApiError, XcpngAuthError, XcpngClient, XcpngConnectionError
from .const import BACKUP_LOGS_FETCH_LIMIT, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

POOL_FIELDS = ["id", "name_label", "name_description", "master", "HA_enabled", "cpus", "tags"]
HOST_FIELDS = [
    "id",
    "name_label",
    "power_state",
    "enabled",
    "memory",
    "cpus",
    "address",
    "startTime",
    "$pool",
    "productBrand",
    "version",
]
VM_FIELDS = [
    "id",
    "name_label",
    "power_state",
    "memory",
    "CPUs",
    "$container",
    "$pool",
    "tags",
]
SR_FIELDS = [
    "id",
    "name_label",
    "physical_usage",
    "size",
    "$container",
    "content_type",
    "shared",
]
BACKUP_JOB_FIELDS = ["id", "name"]
BACKUP_LOG_FIELDS = ["id", "status", "start", "end", "jobId"]


@dataclass
class XcpngData:
    """Snapshot of everything the coordinator polled from Xen Orchestra."""

    pools: dict[str, dict[str, Any]] = field(default_factory=dict)
    hosts: dict[str, dict[str, Any]] = field(default_factory=dict)
    vms: dict[str, dict[str, Any]] = field(default_factory=dict)
    srs: dict[str, dict[str, Any]] = field(default_factory=dict)
    backup_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)


class XcpngDataUpdateCoordinator(DataUpdateCoordinator[XcpngData]):
    """Polls the XO REST API and assembles a coherent snapshot."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: XcpngClient) -> None:
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> XcpngData:
        client = self.client
        try:
            pools, hosts, vms, srs, jobs, logs = await asyncio.gather(
                client.async_list("pools", fields=POOL_FIELDS),
                client.async_list("hosts", fields=HOST_FIELDS),
                client.async_list("vms", fields=VM_FIELDS),
                client.async_list("srs", fields=SR_FIELDS),
                client.async_list("backup-jobs", fields=BACKUP_JOB_FIELDS),
                client.async_list(
                    "backup-logs",
                    fields=BACKUP_LOG_FIELDS,
                    limit=BACKUP_LOGS_FETCH_LIMIT,
                ),
            )
        except XcpngAuthError as err:
            raise ConfigEntryAuthFailed("Authentication with Xen Orchestra failed") from err
        except XcpngConnectionError as err:
            raise UpdateFailed(f"Cannot connect to Xen Orchestra: {err}") from err
        except XcpngApiError as err:
            raise UpdateFailed(f"Xen Orchestra API error: {err}") from err

        await self._async_attach_host_stats(hosts)
        self._attach_latest_logs(jobs, logs)

        return XcpngData(
            pools={item["id"]: item for item in pools},
            hosts={item["id"]: item for item in hosts},
            vms={item["id"]: item for item in vms},
            srs={item["id"]: item for item in srs},
            backup_jobs={item["id"]: item for item in jobs},
        )

    async def _async_attach_host_stats(self, hosts: list[dict[str, Any]]) -> None:
        """Best-effort fetch of live CPU/memory stats for each host.

        A single host's stats call failing (permissions, transient network
        issue, ...) must not take down the whole update.
        """
        results = await asyncio.gather(
            *(self.client.async_get_host_stats(host["id"]) for host in hosts),
            return_exceptions=True,
        )
        for host, result in zip(hosts, results):
            if isinstance(result, BaseException):
                _LOGGER.debug(
                    "Could not fetch stats for host %s: %s", host.get("id"), result
                )
                host["_stats"] = None
            else:
                host["_stats"] = result

    @staticmethod
    def _attach_latest_logs(
        jobs: list[dict[str, Any]], logs: list[dict[str, Any]]
    ) -> None:
        latest_by_job: dict[str, dict[str, Any]] = {}
        for log in logs:
            job_id = log.get("jobId")
            if not job_id:
                continue
            current = latest_by_job.get(job_id)
            if current is None or (log.get("start") or 0) > (current.get("start") or 0):
                latest_by_job[job_id] = log
        for job in jobs:
            job["_last_log"] = latest_by_job.get(job["id"])
