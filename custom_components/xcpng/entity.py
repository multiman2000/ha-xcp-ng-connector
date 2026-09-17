"""Base entity classes and device grouping for the XCP-ng integration."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import XcpngDataUpdateCoordinator


def pool_device_info(pool: dict[str, Any]) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"pool_{pool['id']}")},
        name=pool.get("name_label") or "XCP-ng Pool",
        manufacturer=MANUFACTURER,
        model="Pool",
    )


def host_device_info(host: dict[str, Any]) -> DeviceInfo:
    pool_id = host.get("$pool")
    info = DeviceInfo(
        identifiers={(DOMAIN, f"host_{host['id']}")},
        name=host.get("name_label") or "XCP-ng Host",
        manufacturer=MANUFACTURER,
        model=host.get("productBrand") or "XCP-ng Host",
        sw_version=host.get("version"),
    )
    if pool_id:
        info["via_device"] = (DOMAIN, f"pool_{pool_id}")
    return info


def vm_device_info(vm: dict[str, Any], pool_id: str | None) -> DeviceInfo:
    info = DeviceInfo(
        identifiers={(DOMAIN, f"vm_{vm['id']}")},
        name=vm.get("name_label") or "XCP-ng VM",
        manufacturer=MANUFACTURER,
        model="Virtual Machine",
    )
    container = vm.get("$container")
    if container and container != pool_id:
        info["via_device"] = (DOMAIN, f"host_{container}")
    elif pool_id:
        info["via_device"] = (DOMAIN, f"pool_{pool_id}")
    return info


def backup_hub_device_info(entry_id: str, host: str) -> DeviceInfo:
    hostname = host.removeprefix("https://").removeprefix("http://").rstrip("/")
    return DeviceInfo(
        identifiers={(DOMAIN, f"xoa_{entry_id}")},
        name=f"Xen Orchestra ({hostname})",
        manufacturer=MANUFACTURER,
        model="Xen Orchestra Appliance",
    )


class XcpngEntity(CoordinatorEntity[XcpngDataUpdateCoordinator]):
    """Common base: disables itself when its underlying object disappears."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XcpngDataUpdateCoordinator,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        return super().available and self._source_object() is not None

    def _source_object(self) -> dict[str, Any] | None:
        """Return the current raw XO object backing this entity, if any."""
        raise NotImplementedError


def register_dynamic_entities(
    coordinator: XcpngDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    id_getter: Callable[[], Iterable[str]],
    factory: Callable[[set[str]], list[Entity]],
) -> None:
    """Add entities for ids that exist now, then keep watching for new ones.

    XO objects (VMs especially) can be created after this integration is
    already running, so platforms use this instead of a one-shot setup.
    """
    known: set[str] = set()

    def _check_for_new_ids() -> None:
        current_ids = set(id_getter())
        new_ids = current_ids - known
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(factory(new_ids))

    _check_for_new_ids()
    coordinator.async_add_listener(_check_for_new_ids)
