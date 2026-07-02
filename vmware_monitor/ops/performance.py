"""Real-time performance counters for hosts and VMs (read-only).

Wraps the vSphere PerfManager to return CPU / memory / disk / network
utilisation for ESXi hosts and virtual machines. This is the one monitoring
area that inventory/health do NOT cover: those return static config (cores,
total GB) and state, never live utilisation.

All functions here are strictly read-only — QueryPerf and
QueryPerfProviderSummary never mutate vSphere state.

Honesty note: these are *point-in-time* real-time samples (the 20-second
provider interval). Longitudinal trends are not retained by this skill — for
historical trending, point vCenter/Aria at a metrics store. We never fabricate
a "trend" from a single sample.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim
from vmware_policy import sanitize

from vmware_monitor.ops._collect import _collect

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

# Curated counter set: "<group>.<name>.<rollup>" → (output_key, divisor, unit).
# Divisor converts the raw vSphere value to a human unit:
#   cpu/mem usage come as hundredths of a percent (5000 → 50.0%)
#   *.consumed / memory come as KB → MB
#   disk/net rates come as KB/s
_HOST_COUNTERS: dict[str, tuple[str, float, str]] = {
    "cpu.usage.average": ("cpu_usage_pct", 100.0, "%"),
    "mem.usage.average": ("mem_usage_pct", 100.0, "%"),
    "mem.consumed.average": ("mem_consumed_mb", 1024.0, "MB"),
    "disk.usage.average": ("disk_kbps", 1.0, "KB/s"),
    "net.usage.average": ("net_kbps", 1.0, "KB/s"),
}

_VM_COUNTERS: dict[str, tuple[str, float, str]] = {
    "cpu.usage.average": ("cpu_usage_pct", 100.0, "%"),
    "mem.usage.average": ("mem_usage_pct", 100.0, "%"),
    "mem.consumed.average": ("mem_consumed_mb", 1024.0, "MB"),
    "virtualDisk.read.average": ("disk_read_kbps", 1.0, "KB/s"),
    "virtualDisk.write.average": ("disk_write_kbps", 1.0, "KB/s"),
    "net.usage.average": ("net_kbps", 1.0, "KB/s"),
}


def _counter_map(perf_mgr: vim.PerformanceManager) -> dict[str, int]:
    """Map "<group>.<name>.<rollup>" → counterId for the whole vCenter once."""
    return {
        f"{c.groupInfo.key}.{c.nameInfo.key}.{c.rollupType}": c.key for c in perf_mgr.perfCounter
    }


def _sample_entity(
    perf_mgr: vim.PerformanceManager,
    counter_ids: dict[str, int],
    entity: vim.ManagedEntity,
    wanted: dict[str, tuple[str, float, str]],
    samples: int = 3,
) -> dict | None:
    """Query real-time counters for one entity; return averaged latest values.

    Returns None when the entity has no real-time provider (e.g. a powered-off
    VM, or a host that only exposes historical intervals) — the caller skips it
    rather than reporting a misleading zero.
    """
    metric_ids = []
    by_id: dict[int, tuple[str, float, str]] = {}
    for wire_name, meta in wanted.items():
        cid = counter_ids.get(wire_name)
        if cid is None:
            continue
        metric_ids.append(vim.PerformanceManager.MetricId(counterId=cid, instance=""))
        by_id[cid] = meta
    if not metric_ids:
        return None

    summary = perf_mgr.QueryPerfProviderSummary(entity)
    if not summary.currentSupported:
        # Only historical intervals available — real-time sampling impossible.
        return None
    interval = summary.refreshRate

    spec = vim.PerformanceManager.QuerySpec(
        entity=entity,
        metricId=metric_ids,
        intervalId=interval,
        maxSample=samples,
    )
    results = perf_mgr.QueryPerf(querySpec=[spec])
    if not results:
        return None

    out: dict[str, float] = {}
    for metric in results[0].value:
        meta = by_id.get(metric.id.counterId)
        if meta is None:
            continue
        out_key, divisor, _unit = meta
        vals = [v for v in metric.value if v >= 0]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        out[out_key] = round(avg / divisor, 2)
    return out or None


def get_host_performance(
    si: ServiceInstance,
    host_name: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Real-time CPU/memory/disk/network utilisation per ESXi host.

    Args:
        si: vSphere ServiceInstance.
        host_name: Filter to a single host by exact name (None = all hosts).
        limit: Max number of host rows to return (None = all).

    Returns one dict per host with cpu_usage_pct, mem_usage_pct,
    mem_consumed_mb, disk_kbps, net_kbps. Hosts that are disconnected or expose
    no real-time provider are skipped (not reported as zero).
    """
    content = si.RetrieveContent()
    perf = content.perfManager
    counter_ids = _counter_map(perf)

    # Batch name + connectionState for every host in one PropertyCollector call,
    # then drive QueryPerf from that set (issue #31: the per-host lazy reads used
    # to be one round-trip each before any limit applied).
    results: list[dict] = []
    for host, p in _collect(si, [vim.HostSystem], ["name", "runtime.connectionState"]):
        name = p.get("name", "")
        if host_name and name != host_name:
            continue
        if str(p.get("runtime.connectionState", "")) != "connected":
            continue
        metrics = _sample_entity(perf, counter_ids, host, _HOST_COUNTERS)
        if metrics is None:
            continue
        row = {"host": sanitize(name)}
        row.update(metrics)
        results.append(row)

    results.sort(key=lambda x: x.get("cpu_usage_pct", 0), reverse=True)
    if limit is not None:
        results = results[:limit]
    return results


def get_vm_performance(
    si: ServiceInstance,
    vm_name: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Real-time CPU/memory/disk/network utilisation per virtual machine.

    Only powered-on VMs have a real-time provider; powered-off VMs are skipped.
    Sorted by CPU usage descending so the busiest VMs surface first.

    Args:
        si: vSphere ServiceInstance.
        vm_name: Filter to a single VM by exact name (None = all powered-on VMs).
        limit: Max number of VM rows to return (None = all). Defaults applied by
            the caller — large fleets should pass a limit to keep context small.
    """
    content = si.RetrieveContent()
    perf = content.perfManager
    counter_ids = _counter_map(perf)

    # Batch name + powerState for every VM in one PropertyCollector call, then
    # drive QueryPerf from that set (issue #31: the per-VM lazy reads used to be
    # one round-trip each before any limit applied).
    results: list[dict] = []
    for vm, p in _collect(si, [vim.VirtualMachine], ["name", "runtime.powerState"]):
        name = p.get("name", "")
        if vm_name and name != vm_name:
            continue
        if str(p.get("runtime.powerState", "")) != "poweredOn":
            continue
        metrics = _sample_entity(perf, counter_ids, vm, _VM_COUNTERS)
        if metrics is None:
            continue
        row = {"name": sanitize(name)}
        row.update(metrics)
        results.append(row)

    results.sort(key=lambda x: x.get("cpu_usage_pct", 0), reverse=True)
    if limit is not None:
        results = results[:limit]
    return results
