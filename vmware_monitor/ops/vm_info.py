"""VM information queries (read-only).

Extracted from vm_lifecycle.py — contains ONLY read-only operations.
No power, create, delete, reconfigure, snapshot-create/revert/delete,
clone, or migrate code exists in this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_monitor.ops.inventory import find_vm_by_name

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


class VMNotFoundError(Exception):
    """Raised when a VM is not found by name."""


def _require_vm(si: ServiceInstance, vm_name: str) -> vim.VirtualMachine:
    """Find a VM or raise VMNotFoundError."""
    vm = find_vm_by_name(si, vm_name)
    if vm is None:
        raise VMNotFoundError(f"VM '{vm_name}' not found")
    return vm


def get_vm_info(si: ServiceInstance, vm_name: str) -> dict:
    """Get detailed VM information."""
    vm = _require_vm(si, vm_name)
    config = vm.config
    guest = vm.guest
    runtime = vm.runtime

    disks = []
    nics = []
    if config and config.hardware:
        for dev in config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualDisk):
                disks.append({
                    "label": dev.deviceInfo.label,
                    "size_gb": round(dev.capacityInKB / (1024 * 1024), 1),
                    "thin": getattr(dev.backing, "thinProvisioned", None),
                })
            elif isinstance(dev, vim.vm.device.VirtualEthernetCard):
                nics.append({
                    "label": dev.deviceInfo.label,
                    "mac": dev.macAddress,
                    "connected": dev.connectable.connected if dev.connectable else False,
                    "network": dev.backing.deviceName
                    if hasattr(dev.backing, "deviceName")
                    else str(dev.backing),
                })

    return {
        "name": vm.name,
        "power_state": str(runtime.powerState),
        "cpu": config.hardware.numCPU if config else 0,
        "memory_mb": config.hardware.memoryMB if config else 0,
        "guest_os": config.guestFullName if config else "N/A",
        "guest_id": config.guestId if config else "N/A",
        "uuid": config.uuid if config else "N/A",
        "instance_uuid": config.instanceUuid if config else "N/A",
        "host": runtime.host.name if runtime.host else "N/A",
        "ip_address": guest.ipAddress if guest else None,
        "hostname": guest.hostName if guest else None,
        "tools_status": str(guest.toolsRunningStatus) if guest else "N/A",
        "tools_version": str(guest.toolsVersion) if guest and guest.toolsVersion else "N/A",
        "disks": disks,
        "nics": nics,
        "annotation": config.annotation if config and config.annotation else "",
        "snapshot_count": _count_snapshots(vm.snapshot) if vm.snapshot else 0,
    }


def _count_snapshots(snapshot_info) -> int:
    """Count total snapshots recursively."""
    count = 0
    if snapshot_info and snapshot_info.rootSnapshotList:
        for snap in snapshot_info.rootSnapshotList:
            count += 1 + _count_children(snap)
    return count


def _count_children(snap_tree) -> int:
    count = 0
    for child in snap_tree.childSnapshotList:
        count += 1 + _count_children(child)
    return count


def list_snapshots(si: ServiceInstance, vm_name: str) -> list[dict]:
    """List all snapshots for a VM (read-only)."""
    vm = _require_vm(si, vm_name)
    if not vm.snapshot:
        return []

    results: list[dict] = []

    def _walk(snap_list, level: int = 0) -> None:
        for snap in snap_list:
            results.append({
                "name": snap.name,
                "description": snap.description,
                "created": str(snap.createTime),
                "state": str(snap.state),
                "level": level,
            })
            if snap.childSnapshotList:
                _walk(snap.childSnapshotList, level + 1)

    _walk(vm.snapshot.rootSnapshotList)
    return results
