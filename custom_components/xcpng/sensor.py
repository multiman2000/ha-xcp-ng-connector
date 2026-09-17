"""Sensor platform for the XCP-ng / Xen Orchestra integration."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BACKUP_STATUS_UNKNOWN, DOMAIN
from .coordinator import XcpngDataUpdateCoordinator
from .entity import (
    XcpngEntity,
    backup_hub_device_info,
    host_device_info,
    pool_device_info,
    register_dynamic_entities,
    vm_device_info,
)
from .helpers import host_cpu_usage_percent, usage_percent

BACKUP_STATUS_OPTIONS = [
    "success",
    "skipped",
    "interrupted",
    "failure",
    "pending",
    "never_run",
    BACKUP_STATUS_UNKNOWN,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors, including any created later by watching the coordinator."""
    coordinator: XcpngDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.pools.keys(),
        lambda ids: [
            entity
            for pool_id in ids
            for entity in (
                PoolVmsRunningSensor(coordinator, pool_id),
                PoolVmsTotalSensor(coordinator, pool_id),
                PoolCpuUsageSensor(coordinator, pool_id),
                PoolMemoryUsageSensor(coordinator, pool_id),
            )
        ],
    )

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.hosts.keys(),
        lambda ids: [
            entity
            for host_id in ids
            for entity in (
                HostCpuUsageSensor(coordinator, host_id),
                HostMemoryUsageSensor(coordinator, host_id),
                HostUptimeSensor(coordinator, host_id),
            )
        ],
    )

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.srs.keys(),
        lambda ids: [SrUsageSensor(coordinator, sr_id) for sr_id in ids],
    )

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.vms.keys(),
        lambda ids: [VmMemoryUsageSensor(coordinator, vm_id) for vm_id in ids],
    )

    register_dynamic_entities(
        coordinator,
        async_add_entities,
        lambda: coordinator.data.backup_jobs.keys(),
        lambda ids: [
            BackupJobStatusSensor(coordinator, entry, job_id) for job_id in ids
        ],
    )


def _epoch_to_datetime(value: float | int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, tz=timezone.utc)


class PoolVmsRunningSensor(XcpngEntity, SensorEntity):
    """Number of running VMs in a pool."""

    _attr_translation_key = "pool_vms_running"
    _attr_native_unit_of_measurement = "VMs"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, pool_id: str) -> None:
        self._pool_id = pool_id
        super().__init__(
            coordinator,
            f"{pool_id}_vms_running",
            pool_device_info(coordinator.data.pools[pool_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.pools.get(self._pool_id)

    @property
    def native_value(self) -> int | None:
        if self._source_object() is None:
            return None
        return sum(
            1
            for vm in self.coordinator.data.vms.values()
            if vm.get("$pool") == self._pool_id and vm.get("power_state") == "Running"
        )


class PoolVmsTotalSensor(XcpngEntity, SensorEntity):
    """Total number of VMs in a pool, regardless of power state."""

    _attr_translation_key = "pool_vms_total"
    _attr_native_unit_of_measurement = "VMs"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, pool_id: str) -> None:
        self._pool_id = pool_id
        super().__init__(
            coordinator,
            f"{pool_id}_vms_total",
            pool_device_info(coordinator.data.pools[pool_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.pools.get(self._pool_id)

    @property
    def native_value(self) -> int | None:
        if self._source_object() is None:
            return None
        return sum(
            1 for vm in self.coordinator.data.vms.values() if vm.get("$pool") == self._pool_id
        )


class PoolCpuUsageSensor(XcpngEntity, SensorEntity):
    """Average CPU usage across every host in the pool."""

    _attr_translation_key = "pool_cpu_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, pool_id: str) -> None:
        self._pool_id = pool_id
        super().__init__(
            coordinator,
            f"{pool_id}_cpu_usage",
            pool_device_info(coordinator.data.pools[pool_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.pools.get(self._pool_id)

    @property
    def native_value(self) -> float | None:
        if self._source_object() is None:
            return None
        values = [
            usage
            for host in self.coordinator.data.hosts.values()
            if host.get("$pool") == self._pool_id
            and (usage := host_cpu_usage_percent(host.get("_stats"))) is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 1)


class PoolMemoryUsageSensor(XcpngEntity, SensorEntity):
    """Aggregate memory usage across every host in the pool."""

    _attr_translation_key = "pool_memory_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, pool_id: str) -> None:
        self._pool_id = pool_id
        super().__init__(
            coordinator,
            f"{pool_id}_memory_usage",
            pool_device_info(coordinator.data.pools[pool_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.pools.get(self._pool_id)

    @property
    def native_value(self) -> float | None:
        if self._source_object() is None:
            return None
        total_size = total_usage = 0
        for host in self.coordinator.data.hosts.values():
            if host.get("$pool") != self._pool_id:
                continue
            memory = host.get("memory") or {}
            total_size += memory.get("size") or 0
            total_usage += memory.get("usage") or 0
        return usage_percent(total_usage, total_size)


class HostCpuUsageSensor(XcpngEntity, SensorEntity):
    """Live CPU usage of one host, averaged across its cores."""

    _attr_translation_key = "host_cpu_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, host_id: str) -> None:
        self._host_id = host_id
        super().__init__(
            coordinator,
            f"{host_id}_cpu_usage",
            host_device_info(coordinator.data.hosts[host_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.hosts.get(self._host_id)

    @property
    def native_value(self) -> float | None:
        host = self._source_object()
        if host is None:
            return None
        return host_cpu_usage_percent(host.get("_stats"))


class HostMemoryUsageSensor(XcpngEntity, SensorEntity):
    """Memory usage of one host."""

    _attr_translation_key = "host_memory_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, host_id: str) -> None:
        self._host_id = host_id
        super().__init__(
            coordinator,
            f"{host_id}_memory_usage",
            host_device_info(coordinator.data.hosts[host_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.hosts.get(self._host_id)

    @property
    def native_value(self) -> float | None:
        host = self._source_object()
        if host is None:
            return None
        memory = host.get("memory") or {}
        return usage_percent(memory.get("usage"), memory.get("size"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        host = self._source_object()
        if host is None:
            return None
        memory = host.get("memory") or {}
        return {
            "memory_used_bytes": memory.get("usage"),
            "memory_total_bytes": memory.get("size"),
        }


class HostUptimeSensor(XcpngEntity, SensorEntity):
    """Timestamp the host last booted."""

    _attr_translation_key = "host_uptime"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, host_id: str) -> None:
        self._host_id = host_id
        super().__init__(
            coordinator,
            f"{host_id}_uptime",
            host_device_info(coordinator.data.hosts[host_id]),
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.hosts.get(self._host_id)

    @property
    def native_value(self) -> datetime | None:
        host = self._source_object()
        if host is None:
            return None
        return _epoch_to_datetime(host.get("startTime"))


class SrUsageSensor(XcpngEntity, SensorEntity):
    """Storage repository space usage."""

    _attr_translation_key = "sr_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, sr_id: str) -> None:
        self._sr_id = sr_id
        sr = coordinator.data.srs[sr_id]
        container = sr.get("$container")
        pool = coordinator.data.pools.get(container)
        host = coordinator.data.hosts.get(container)
        if pool is not None:
            device_info = pool_device_info(pool)
        elif host is not None:
            device_info = host_device_info(host)
        else:
            device_info = pool_device_info({"id": container or sr_id, "name_label": sr.get("name_label")})
        super().__init__(coordinator, f"{sr_id}_usage", device_info)
        self._attr_name = sr.get("name_label")

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.srs.get(self._sr_id)

    @property
    def native_value(self) -> float | None:
        sr = self._source_object()
        if sr is None:
            return None
        return usage_percent(sr.get("physical_usage"), sr.get("size"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        sr = self._source_object()
        if sr is None:
            return None
        return {
            "used_bytes": sr.get("physical_usage"),
            "size_bytes": sr.get("size"),
            "content_type": sr.get("content_type"),
            "shared": sr.get("shared"),
        }


class VmMemoryUsageSensor(XcpngEntity, SensorEntity):
    """Memory usage reported by a VM's guest tools."""

    _attr_translation_key = "vm_memory_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: XcpngDataUpdateCoordinator, vm_id: str) -> None:
        self._vm_id = vm_id
        vm = coordinator.data.vms[vm_id]
        super().__init__(
            coordinator, f"{vm_id}_memory_usage", vm_device_info(vm, vm.get("$pool"))
        )

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.vms.get(self._vm_id)

    @property
    def native_value(self) -> float | None:
        vm = self._source_object()
        if vm is None:
            return None
        memory = vm.get("memory") or {}
        return usage_percent(memory.get("usage"), memory.get("size"))


class BackupJobStatusSensor(XcpngEntity, SensorEntity):
    """Status of the most recent run of an XOA backup job."""

    _attr_translation_key = "backup_job_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = BACKUP_STATUS_OPTIONS

    def __init__(
        self, coordinator: XcpngDataUpdateCoordinator, entry: ConfigEntry, job_id: str
    ) -> None:
        self._job_id = job_id
        job = coordinator.data.backup_jobs[job_id]
        super().__init__(
            coordinator,
            f"{job_id}_status",
            backup_hub_device_info(entry.entry_id, entry.data[CONF_HOST]),
        )
        self._attr_name = job.get("name") or "Backup job"

    def _source_object(self) -> dict[str, Any] | None:
        return self.coordinator.data.backup_jobs.get(self._job_id)

    @property
    def native_value(self) -> str:
        job = self._source_object()
        last_log = job.get("_last_log") if job else None
        if last_log is None:
            return "never_run"
        return last_log.get("status") or BACKUP_STATUS_UNKNOWN

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        job = self._source_object()
        if job is None:
            return None
        last_log = job.get("_last_log")
        if last_log is None:
            return {"job_id": self._job_id}
        start = _epoch_to_datetime(last_log.get("start"))
        end = _epoch_to_datetime(last_log.get("end"))
        duration = None
        if start is not None and end is not None:
            duration = round((end - start).total_seconds())
        return {
            "job_id": self._job_id,
            "last_run_start": start.isoformat() if start else None,
            "last_run_end": end.isoformat() if end else None,
            "last_run_duration_seconds": duration,
        }
