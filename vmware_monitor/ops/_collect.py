"""Batched PropertyCollector retrieval shared across ops modules.

Every ``ops`` query that sweeps the inventory (VMs, hosts, datastores, resource
pools, snapshots, alarms …) must fetch the properties it needs in a single
server-side ``PropertyCollector.RetrievePropertiesEx`` call rather than touching
pyVmomi *lazy* attributes one object at a time. On large inventories the lazy
pattern is one SOAP round-trip per property per object — tens of thousands of
round-trips — which is the root cause of GitHub issue #31 (queries timing out
even with a small ``limit``, because the limit was applied only after the full
collection).

This module owns the single implementation of that batched retrieval so all ops
modules reuse it instead of re-deriving a ContainerView walk with lazy access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim, vmodl

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


def _collect_objects(
    si: ServiceInstance, objs: list, obj_type, paths: list[str]
) -> list[tuple[object, dict]]:
    """Batch-retrieve ``paths`` for a known list of managed objects in one call.

    ``_collect`` sweeps a whole container view, but some properties live on a
    *different* managed object reachable only by reference from the swept object
    (e.g. ``HostServiceSystem.serviceInfo`` or ``HostCertificateManager.
    certificateInfo``, referenced from ``HostSystem.configManager``). A container
    view over ``HostSystem`` cannot cross that boundary, so the naive code reads
    ``ref.serviceInfo`` once per host — one lazy SOAP round-trip per host, the
    same issue #31 class problem, just one hop removed.

    This helper collapses those N per-host reads into a single
    ``RetrievePropertiesEx`` by building one ``ObjectSpec`` per already-known
    reference (no traversal, no container view). Callers collect the references
    in their first batched pass, then fetch the boundary property for all of
    them here in a second batched pass.

    Args:
        si: vSphere ServiceInstance.
        objs: Already-known managed objects (references) to fetch ``paths`` for.
            Duplicates are de-duplicated. An empty list yields ``[]`` with no
            server call.
        obj_type: The managed-object type of every entry in ``objs``, e.g.
            ``vim.HostServiceSystem``.
        paths: Property paths to fetch, e.g. ``["serviceInfo"]``.

    Returns:
        List of ``(managed_object, {path: value})`` tuples in server order.
    """
    unique = list(dict.fromkeys(objs))
    if not unique:
        return []
    content = si.RetrieveContent()
    object_set = [
        vmodl.query.PropertyCollector.ObjectSpec(obj=o, skip=False) for o in unique
    ]
    prop_spec = vmodl.query.PropertyCollector.PropertySpec(
        type=obj_type, pathSet=list(paths), all=False
    )
    filter_spec = vmodl.query.PropertyCollector.FilterSpec(
        objectSet=object_set, propSet=[prop_spec]
    )
    options = vmodl.query.PropertyCollector.RetrieveOptions(maxObjects=_PC_PAGE_SIZE)
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
