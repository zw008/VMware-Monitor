"""Capacity analytics: datastore over-commit and resource-pool usage (read-only).

Inventory's `list_datastores` returns free/total only. This module adds the
operational risk signal: thin-provisioning over-commit (provisioned space that
exceeds physical capacity) and resource-pool reservation/usage. Both are
point-in-time — see honesty note.

Read-only.

Honesty note: these are *snapshots*, not trends. True capacity trending
(growth rate, days-until-full) needs retained history, which this skill does
not store — pair vCenter/Aria with a metrics store for that. We compute
over-commit from current values and never extrapolate a fake runway date.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim
from vmware_policy import sanitize

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_GB = 1024**3


def _get_objects(si: ServiceInstance, obj_type: list) -> list:
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(content.rootFolder, obj_type, True)
    try:
        return list(container.view)
    finally:
        container.Destroy()


def get_datastore_capacity(
    si: ServiceInstance,
    limit: int | None = None,
) -> list[dict]:
    """Per-datastore capacity with thin-provisioning over-commit.

    Returns name, type, capacity_gb, free_gb, committed_gb (allocated),
    provisioned_gb (committed + uncommitted thin reservations), used_pct, and
    overcommit_pct (provisioned / capacity * 100). overcommit_pct > 100 means
    more space is promised to VMs than the datastore physically has — a thin
    datastore can fill up even while showing free space. Sorted by over-commit
    descending so the riskiest datastores surface first.

    Args:
        si: vSphere ServiceInstance.
        limit: Max number of datastore rows to return (None = all).
    """
    results: list[dict] = []
    for ds in _get_objects(si, [vim.Datastore]):
        summary = ds.summary
        capacity = summary.capacity or 0
        free = summary.freeSpace or 0
        uncommitted = getattr(summary, "uncommitted", 0) or 0
        committed = capacity - free
        provisioned = committed + uncommitted
        used_pct = round(committed / capacity * 100, 1) if capacity else 0.0
        overcommit_pct = round(provisioned / capacity * 100, 1) if capacity else 0.0
        results.append(
            {
                "name": sanitize(ds.name),
                "type": summary.type,
                "capacity_gb": round(capacity / _GB, 1),
                "free_gb": round(free / _GB, 1),
                "committed_gb": round(committed / _GB, 1),
                "provisioned_gb": round(provisioned / _GB, 1),
                "used_pct": used_pct,
                "overcommit_pct": overcommit_pct,
            }
        )
    results.sort(key=lambda x: x["overcommit_pct"], reverse=True)
    if limit is not None:
        results = results[:limit]
    return results


def get_resource_pool_usage(
    si: ServiceInstance,
    limit: int | None = None,
) -> list[dict]:
    """Per-resource-pool CPU/memory reservation, limit, and current usage.

    Returns name, cpu_reservation_mhz, cpu_limit_mhz, cpu_usage_mhz,
    mem_reservation_mb, mem_limit_mb, mem_usage_mb. A limit of -1 means
    unlimited (vSphere's sentinel). The implicit cluster root pool ("Resources")
    is included. Sorted by memory usage descending.

    Args:
        si: vSphere ServiceInstance.
        limit: Max number of pool rows to return (None = all).
    """
    results: list[dict] = []
    for pool in _get_objects(si, [vim.ResourcePool]):
        cfg = pool.config
        qs = pool.summary.quickStats if pool.summary else None
        cpu_alloc = cfg.cpuAllocation if cfg else None
        mem_alloc = cfg.memoryAllocation if cfg else None
        results.append(
            {
                "name": sanitize(pool.name),
                "cpu_reservation_mhz": cpu_alloc.reservation if cpu_alloc else 0,
                "cpu_limit_mhz": cpu_alloc.limit if cpu_alloc else -1,
                "cpu_usage_mhz": qs.overallCpuUsage if qs else 0,
                "mem_reservation_mb": mem_alloc.reservation if mem_alloc else 0,
                "mem_limit_mb": mem_alloc.limit if mem_alloc else -1,
                "mem_usage_mb": qs.guestMemoryUsage if qs else 0,
            }
        )
    results.sort(key=lambda x: x["mem_usage_mb"], reverse=True)
    if limit is not None:
        results = results[:limit]
    return results
