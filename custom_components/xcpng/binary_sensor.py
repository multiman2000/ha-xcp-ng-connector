"""Binary sensor platform for the XCP-ng / Xen Orchestra integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HOST_POWER_STATE_RUNNING, VM_POWER_STATE_RUNNING
from .coordinator import XcpngDataUpdateCoordinator
from .entity import (
    XcpngEntity,
    backup_hub_device_info,
    host_device_info,
    pool_device_info,
    register_dynamic_entities,
    vm_device_info,
)

FAILED_BACKUP_STATUSES = {"failure", "interrupted"}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensors, watching the coordinator for new objects."""
    coordinator: XcpngDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.pools.keys(),
        lambda ids: [PoolHaEnabledBinarySensor(coordinator, pool_id) for pool_id in ids],
    )

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.hosts.keys(),
        lambda ids: [
            entity
            for host_id in ids
            for entity in (
                HostRunningBinarySensor(coordinator, host_id),
                HostMaintenanceBinarySensor(coordinator, host_id),
            )
        ],
    )

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.vms.keys(),
        lambda ids: [VmRunningBinarySensor(coordinator, vm_id) for vm_id in ids],
    )

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.backup_jobs.keys(),
        lambda ids: [
            BackupJobFailedBinarySensor(coordinator, entry, job_id) for job_id in ids
        ],
    )


class PoolHaEnabledBinarySensor(XcpngEntity, BinarySensorEntity):
    """Whether High Availability is enabled on the pool."""

    _attr_translation_key = "pool_ha_enabled"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, pool_id: str) -> None:
        self._pool_id = pool_id
        super().__init__(
            coordinator,
            f"{pool_id}_ha_enabled",
            pool_device_info(coordinator.data.pools[pool_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.pools.get(self._pool_id)

    @property
    def is_on(self) -> bool | None:
        pool = self._source_object()
        if pool is None:
            return None
        return bool(pool.get("HA_enabled"))


class HostRunningBinarySensor(XcpngEntity, BinarySensorEntity):
    """Whether a host is powered on and reachable."""

    _attr_translation_key = "host_running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, host_id: str) -> None:
        self._host_id = host_id
        super().__init__(
            coordinator,
            f"{host_id}_running",
            host_device_info(coordinator.data.hosts[host_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.hosts.get(self._host_id)

    @property
    def is_on(self) -> bool | None:
        host = self._source_object()
        if host is None:
            return None
        return host.get("power_state") == HOST_POWER_STATE_RUNNING


class HostMaintenanceBinarySensor(XcpngEntity, BinarySensorEntity):
    """On when the host is disabled (in maintenance mode)."""

    _attr_translation_key = "host_maintenance_mode"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, host_id: str) -> None:
        self._host_id = host_id
        super().__init__(
            coordinator,
            f"{host_id}_maintenance_mode",
            host_device_info(coordinator.data.hosts[host_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.hosts.get(self._host_id)

    @property
    def is_on(self) -> bool | None:
        host = self._source_object()
        if host is None:
            return None
        return not host.get("enabled", True)


class VmRunningBinarySensor(XcpngEntity, BinarySensorEntity):
    """Whether a VM is currently running."""

    _attr_translation_key = "vm_running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, vm_id: str) -> None:
        self._vm_id = vm_id
        vm = coordinator.data.vms[vm_id]
        super().__init__(coordinator, f"{vm_id}_running", vm_device_info(vm, vm.get("$pool")))

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.vms.get(self._vm_id)

    @property
    def is_on(self) -> bool | None:
        vm = self._source_object()
        if vm is None:
            return None
        return vm.get("power_state") == VM_POWER_STATE_RUNNING


class BackupJobFailedBinarySensor(XcpngEntity, BinarySensorEntity):
    """On when the last run of a backup job failed or was interrupted."""

    _attr_translation_key = "backup_job_failed"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self, coordinator: XcpngDataUpdateCoordinator, entry: ConfigEntry, job_id: str
    ) -> None:
        self._job_id = job_id
        job = coordinator.data.backup_jobs[job_id]
        super().__init__(
            coordinator,
            f"{job_id}_failed",
            backup_hub_device_info(entry.entry_id, entry.data[CONF_HOST]),
        )
        self._attr_name = f"{job.get('name') or 'Backup job'} failed"

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.backup_jobs.get(self._job_id)

    @property
    def is_on(self) -> bool | None:
        job = self._source_object()
        if job is None:
            return None
        last_log = job.get("_last_log")
        if last_log is None:
            return False
        return last_log.get("status") in FAILED_BACKUP_STATUSES
