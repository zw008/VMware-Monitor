"""Inventory queries for vCenter/ESXi resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim, vmodl
from vmware_policy import sanitize

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


# Server-side page size for PropertyCollector. Large inventories are streamed in
# batches of this many objects; the helper transparently follows continuation
# tokens, so the caller always gets the full result set.
_PC_PAGE_SIZE = 1000


def _collect(
    si: ServiceInstance, obj_type: list, paths: list[str]
) -> list[tuple[object, dict]]:
    """Batch-retrieve ``paths`` for every ``obj_type`` object in one operation.

    Uses ``PropertyCollector.RetrievePropertiesEx`` so all requested properties
    for all matching objects are fetched in a single server-side call (paged via
    continuation tokens), instead of one lazy SOAP round-trip per property per
    object. This is the difference between seconds and minutes on inventories
    with thousands of VMs/hosts (GitHub issue #31).

    Args:
        si: vSphere ServiceInstance.
        obj_type: Single-element list with the managed-object type to collect,
            e.g. ``[vim.VirtualMachine]``.
        paths: Property paths to fetch, e.g. ``["name", "runtime.powerState"]``.
            Array properties (e.g. ``vm``) come back as lists; unset properties
            are simply absent from the returned dict.

    Returns:
        List of ``(managed_object, {path: value})`` tuples in server order.
    """
    content = si.RetrieveContent()
    view = content.viewManager.CreateContainerView(
        content.rootFolder, obj_type, True
    )
    try:
        traversal = vmodl.query.PropertyCollector.TraversalSpec(
            name="traverseView", type=vim.view.ContainerView, path="view", skip=False
        )
        obj_spec = vmodl.query.PropertyCollector.ObjectSpec(
            obj=view, skip=True, selectSet=[traversal]
        )
        prop_spec = vmodl.query.PropertyCollector.PropertySpec(
            type=obj_type[0], pathSet=list(paths), all=False
        )
        filter_spec = vmodl.query.PropertyCollector.FilterSpec(
            objectSet=[obj_spec], propSet=[prop_spec]
        )
        options = vmodl.query.PropertyCollector.RetrieveOptions(
            maxObjects=_PC_PAGE_SIZE
        )
        pc = content.propertyCollector
        results: list[tuple[object, dict]] = []
        batch = pc.RetrievePropertiesEx([filter_spec], options)
        while batch is not None:
            for obj_content in batch.objects:
                props = {p.name: p.val for p in (obj_content.propSet or [])}
                results.append((obj_content.obj, props))
            token = getattr(batch, "token", None)
            if not token:
                break
            batch = pc.ContinueRetrievePropertiesEx(token)
        return results
    finally:
        view.Destroy()


def folder_path(managed_entity) -> str:
    """Return the vCenter inventory folder path for a managed entity.

    Walks ``parent`` references up the inventory tree, stopping at the
    enclosing Datacenter. The Datacenter's root vmFolder (named ``vm`` by
    default) is omitted so the returned path matches what users see in the
    vSphere UI under "VMs and Templates".

    Args:
        managed_entity: Any vim.ManagedEntity (VirtualMachine, Folder, etc.).

    Returns:
        Forward-slash separated path beginning with ``/``. Returns ``"/"`` for
        entities that sit directly in the datacenter vmFolder. vApps are
        included in the path as folders.

    Examples:
        ``"/"`` — VM at the root of the datacenter vmFolder
        ``"/Colocation"`` — VM in a top-level "Colocation" folder
        ``"/Colocation/Colo - ISER"`` — VM nested in a department subfolder
        ``"/My vApp"`` — VM inside a vApp at the root
    """
    parts: list[str] = []
    p = getattr(managed_entity, "parent", None)
    # Walk upward, stopping at the Datacenter boundary so the path is
    # relative to the dc-level vmFolder (which is itself omitted).
    while p is not None:
        if isinstance(p, vim.Datacenter):
            break
        # Skip the dc's root vmFolder ("vm"); its direct parent is the dc.
        if isinstance(p, vim.Folder) and isinstance(getattr(p, "parent", None), vim.Datacenter):
            break
        parts.append(sanitize(p.name))
        p = getattr(p, "parent", None)
    if not parts:
        return "/"
    return "/" + "/".join(reversed(parts))


_VM_SORT_KEYS = {"name", "cpu", "memory_mb", "power_state", "folder_path"}
_COMPACT_FIELDS = ("name", "power_state", "cpu", "memory_mb", "folder_path")
_VM_VALID_FIELDS = {
    "name", "power_state", "cpu", "memory_mb", "guest_os",
    "ip_address", "host", "uuid", "tools_status", "folder_path",
}
_VM_PROPS = [
    "name",
    "parent",
    "runtime.powerState",
    "runtime.host",
    "config.hardware.numCPU",
    "config.hardware.memoryMB",
    "config.guestFullName",
    "config.uuid",
    "guest.ipAddress",
    "guest.toolsRunningStatus",
]


def _folder_map(si: ServiceInstance) -> dict:
    """Map moRef -> (name, parent_moRef, is_datacenter) for path-bearing containers.

    Fetches ``name``/``parent`` for every Folder, vApp, and Datacenter in three
    batched calls so ``_resolve_folder_path`` can walk the inventory tree locally
    instead of triggering a round-trip per ancestor per VM.
    """
    fmap: dict = {}
    for obj_type, is_dc in (
        ([vim.Folder], False),
        ([vim.VirtualApp], False),
        ([vim.Datacenter], True),
    ):
        for obj, p in _collect(si, obj_type, ["name", "parent"]):
            fmap[obj] = (sanitize(p.get("name", "")), p.get("parent"), is_dc)
    return fmap


def _resolve_folder_path(parent_ref, fmap: dict) -> str:
    """Compute a VM's folder path from a prefetched ``_folder_map``.

    Mirrors ``folder_path()`` but resolves ancestors from the local map. Stops at
    the Datacenter boundary and omits the datacenter's root ``vm`` folder so the
    result matches the vSphere "VMs and Templates" view.
    """
    parts: list[str] = []
    p = parent_ref
    while p is not None:
        entry = fmap.get(p)
        if entry is None:
            break
        name, grandparent, is_dc = entry
        if is_dc:
            break
        # Skip the dc's root vmFolder ("vm"): its direct parent is a Datacenter.
        gp = fmap.get(grandparent)
        if gp is not None and gp[2]:
            break
        parts.append(name)
        p = grandparent
    if not parts:
        return "/"
    return "/" + "/".join(reversed(parts))


def list_vms(
    si: ServiceInstance,
    limit: int | None = None,
    sort_by: str = "name",
    power_state: str | None = None,
    fields: list[str] | None = None,
    folder_filter: str | None = None,
    compact_threshold: int = 50,
) -> dict:
    """List virtual machines with optional filtering, sorting, and field selection.

    Returns a dict with keys:
        total   - total VMs after filtering
        mode    - "full" or "compact" (auto-selected when total > compact_threshold)
        vms     - list of VM dicts
        hint    - optional suggestion when compact mode is auto-selected

    Auto-compact: when no explicit limit/fields are set and total VMs exceed
    compact_threshold (default 50), only compact fields are returned to keep
    context manageable. Use limit or fields to override.

    Args:
        si: vSphere ServiceInstance.
        limit: Max number of VMs to return (None = all).
        sort_by: Sort field: "name" | "cpu" | "memory_mb" | "power_state" | "folder_path".
        power_state: Filter by power state: "poweredOn" | "poweredOff" | "suspended".
        fields: Return only these fields (None = auto).
            Available: name, power_state, cpu, memory_mb, guest_os, ip_address,
                       host, uuid, tools_status, folder_path.
        folder_filter: Case-insensitive substring match against folder_path.
            Example: "Colocation" returns VMs anywhere under a Colocation folder
            (including nested subfolders like /Colocation/Colo - ISER).
        compact_threshold: Auto-compact when VM count exceeds this (default 50).
    """
    # Batched lookups: host moRef -> name, and the folder tree, so per-VM host
    # and folder_path resolution don't each trigger round-trips.
    host_names = {obj: p.get("name") for obj, p in _collect(si, [vim.HostSystem], ["name"])}
    fmap = _folder_map(si)

    results = []
    for _obj, p in _collect(si, [vim.VirtualMachine], _VM_PROPS):
        host_ref = p.get("runtime.host")
        guest_os = p.get("config.guestFullName")
        tools = p.get("guest.toolsRunningStatus")
        entry = {
            "name": sanitize(p.get("name", "")),
            "power_state": str(p.get("runtime.powerState", "N/A")),
            "cpu": p.get("config.hardware.numCPU") or 0,
            "memory_mb": p.get("config.hardware.memoryMB") or 0,
            "guest_os": sanitize(guest_os) if guest_os else "N/A",
            "ip_address": p.get("guest.ipAddress"),
            "host": sanitize(host_names.get(host_ref) or "N/A") if host_ref else "N/A",
            "uuid": p.get("config.uuid") or "N/A",
            "tools_status": str(tools) if tools else "N/A",
            "folder_path": _resolve_folder_path(p.get("parent"), fmap),
        }
        results.append(entry)

    # Filter by power state
    if power_state:
        results = [r for r in results if power_state.lower() in r["power_state"].lower()]

    # Filter by folder path (case-insensitive substring)
    if folder_filter:
        needle = folder_filter.lower()
        results = [r for r in results if needle in r["folder_path"].lower()]

    # Sort
    sort_key = sort_by if sort_by in _VM_SORT_KEYS else "name"
    results = sorted(results, key=lambda x: x[sort_key])

    total = len(results)

    # Limit
    if limit is not None and limit > 0:
        results = results[:limit]

    # Determine mode and field selection
    explicit_fields = bool(fields)
    explicit_limit = limit is not None and limit > 0

    if not explicit_fields and not explicit_limit and total > compact_threshold:
        # Auto-compact: large inventory, no explicit constraints
        mode = "compact"
        results = [{k: r[k] for k in _COMPACT_FIELDS if k in r} for r in results]
        hint = (
            f"Large inventory ({total} VMs): showing compact fields only. "
            "Use --limit N or --fields to get full details."
        )
    else:
        mode = "full"
        hint = None
        if fields:
            keep = [f for f in fields if f in _VM_VALID_FIELDS]
            if keep:
                results = [{k: r[k] for k in keep if k in r} for r in results]

    return {"total": total, "mode": mode, "vms": results, "hint": hint}


_HOST_PROPS = [
    "name",
    "runtime.connectionState",
    "runtime.powerState",
    "hardware.cpuInfo.numCpuCores",
    "hardware.cpuInfo.numCpuThreads",
    "hardware.memorySize",
    "config.product.version",
    "config.product.build",
    "vm",
    "summary.quickStats.uptime",
]
_DS_PROPS = [
    "name",
    "summary.type",
    "summary.freeSpace",
    "summary.capacity",
    "summary.accessible",
    "summary.url",
    "vm",
]
_CLUSTER_PROPS = [
    "name",
    "host",
    "configuration.drsConfig.enabled",
    "configuration.drsConfig.defaultVmBehavior",
    "configuration.dasConfig.enabled",
    "summary.totalCpu",
    "summary.totalMemory",
]
_NET_PROPS = ["name", "vm", "summary.accessible"]


def list_hosts(si: ServiceInstance) -> list[dict]:
    """List all ESXi hosts with basic info."""
    results = []
    for _obj, p in _collect(si, [vim.HostSystem], _HOST_PROPS):
        mem = p.get("hardware.memorySize")
        results.append({
            "name": p.get("name", ""),
            "connection_state": str(p.get("runtime.connectionState", "N/A")),
            "power_state": str(p.get("runtime.powerState", "N/A")),
            "cpu_cores": p.get("hardware.cpuInfo.numCpuCores") or 0,
            "cpu_threads": p.get("hardware.cpuInfo.numCpuThreads") or 0,
            "memory_gb": round(mem / (1024**3)) if mem else 0,
            "esxi_version": p.get("config.product.version") or "N/A",
            "esxi_build": p.get("config.product.build") or "N/A",
            "vm_count": len(p.get("vm") or []),
            "uptime_seconds": p.get("summary.quickStats.uptime") or 0,
        })
    return sorted(results, key=lambda x: x["name"])


def list_datastores(si: ServiceInstance) -> list[dict]:
    """List all datastores with capacity info."""
    results = []
    for _obj, p in _collect(si, [vim.Datastore], _DS_PROPS):
        free = p.get("summary.freeSpace")
        cap = p.get("summary.capacity")
        results.append({
            "name": p.get("name", ""),
            "type": p.get("summary.type"),
            "free_gb": round(free / (1024**3), 1) if free else 0,
            "total_gb": round(cap / (1024**3), 1) if cap else 0,
            "accessible": p.get("summary.accessible"),
            "url": p.get("summary.url"),
            "vm_count": len(p.get("vm") or []),
        })
    return sorted(results, key=lambda x: x["name"])


def list_clusters(si: ServiceInstance) -> list[dict]:
    """List all clusters with configuration info."""
    results = []
    for _obj, p in _collect(si, [vim.ClusterComputeResource], _CLUSTER_PROPS):
        total_mem = p.get("summary.totalMemory")
        drs_behavior = p.get("configuration.drsConfig.defaultVmBehavior")
        results.append({
            "name": p.get("name", ""),
            "host_count": len(p.get("host") or []),
            "drs_enabled": bool(p.get("configuration.drsConfig.enabled")),
            "drs_behavior": str(drs_behavior) if drs_behavior else "N/A",
            "ha_enabled": bool(p.get("configuration.dasConfig.enabled")),
            "total_cpu_mhz": p.get("summary.totalCpu") or 0,
            "total_memory_gb": round(total_mem / (1024**3)) if total_mem else 0,
        })
    return sorted(results, key=lambda x: x["name"])


def list_networks(si: ServiceInstance) -> list[dict]:
    """List all networks."""
    results = []
    for _obj, p in _collect(si, [vim.Network], _NET_PROPS):
        accessible = p.get("summary.accessible")
        results.append({
            "name": p.get("name", ""),
            "vm_count": len(p.get("vm") or []),
            "accessible": accessible if accessible is not None else True,
        })
    return sorted(results, key=lambda x: x["name"])


def find_vm_by_name(si: ServiceInstance, vm_name: str) -> vim.VirtualMachine | None:
    """Find a VM by exact name. Returns None if not found."""
    for obj, p in _collect(si, [vim.VirtualMachine], ["name"]):
        if p.get("name") == vm_name:
            return obj
    return None
