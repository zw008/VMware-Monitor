"""MCP server wrapping VMware Monitor read-only operations.

This module exposes **read-only** VMware vCenter/ESXi monitoring tools via
the Model Context Protocol (MCP) using stdio transport.  Each ``@mcp.tool()``
function delegates to the corresponding function in the ``vmware_monitor``
package (ops.inventory, ops.health, ops.vm_info).

**NO destructive operations exist in this module or anywhere in the
vmware-monitor codebase**: no power_on, power_off, create, delete,
reconfigure, snapshot-create/revert/delete, clone, or migrate.

Security considerations
-----------------------
* **All tools are read-only**: Every tool only queries vSphere state;
  none can modify VMs, hosts, or configuration.
* **Credential handling**: Credentials are loaded from environment
  variables / ``.env`` file — never passed via MCP messages.
* **Transport**: Uses stdio transport (local only); no network listener.

Source: https://github.com/zw008/VMware-Monitor
License: MIT
"""

import functools
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

# MCP SDK — Model Context Protocol server framework
from mcp.server.fastmcp import FastMCP
from vmware_policy import sanitize, vmware_tool

# Internal VMware monitoring modules (all read-only operations)
from vmware_monitor.config import load_config
from vmware_monitor.connection import ConnectionManager
from vmware_monitor.ops.health import (
    get_active_alarms,
    get_host_hardware_status,
    get_recent_events,
)
from vmware_monitor.ops.health import get_host_services as _ops_get_host_services
from vmware_monitor.ops.activity import get_active_sessions, get_active_tasks
from vmware_monitor.ops.capacity import (
    get_datastore_capacity,
    get_resource_pool_usage,
)
from vmware_monitor.ops.cluster_summary import get_cluster_health_summary
from vmware_monitor.ops.infra_health import (
    get_certificate_status,
    get_license_status,
    get_ntp_status,
)
from vmware_monitor.ops.inventory import (
    list_clusters,
    list_datastores,
    list_hosts,
    list_networks,
    list_vms,
)
from vmware_monitor.ops.performance import get_host_performance, get_vm_performance
from vmware_monitor.ops.snapshots import list_snapshot_aging
from vmware_monitor.ops.vm_info import get_vm_info, list_snapshots
from vmware_monitor.scanner.log_scanner import scan_host_logs as _ops_scan_host_logs

logger = logging.getLogger(__name__)


def _safe_error(exc: Exception, tool: str) -> str:
    """Return an agent-safe error string; log full detail server-side only.

    Raw exception text can carry API response bodies, internal paths, or
    host:port pairs. Full traceback goes to the server log; the agent sees only
    a control-char-stripped, length-capped message. Intentional validation
    errors (ValueError/FileNotFoundError/KeyError/PermissionError) pass through.
    """
    logger.error("Tool %s failed", tool, exc_info=True)
    if isinstance(exc, (ValueError, FileNotFoundError, KeyError, PermissionError)):
        return sanitize(str(exc), 300)
    return f"{type(exc).__name__}: operation failed."


_DOCTOR_HINT = "Run 'vmware-monitor doctor' to verify connectivity and credentials."


def _catch_tool_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Translate tool exceptions into an error payload shaped like the tool's
    return annotation.

    Tools annotated ``-> list[dict]`` must return a *list* on error too —
    returning a bare error dict trips FastMCP structured-output validation,
    raising ToolError so the teaching hint never reaches the agent. Also
    passes the real tool name (fn.__name__) to _safe_error instead of the
    old literal "monitor".
    """
    returns_list = str(fn.__annotations__.get("return", "")).startswith("list")

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            err = {"error": _safe_error(e, fn.__name__), "hint": _DOCTOR_HINT}
            return [err] if returns_list else err

    return wrapper


mcp = FastMCP(
    "vmware-monitor",
    instructions=(
        "VMware vCenter/ESXi read-only monitoring. "
        "Query inventory, check health/alarms, and view VM info. "
        "No destructive operations — code-level enforced."
    ),
)

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_conn_mgr: Optional[ConnectionManager] = None


def _get_connection(target: Optional[str] = None) -> Any:
    """Return a pyVmomi ServiceInstance, lazily initialising the manager."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_MONITOR_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr.connect(target)


# ---------------------------------------------------------------------------
# Inventory tools (read-only)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def list_virtual_machines(
    target: Optional[str] = None,
    limit: Optional[int] = None,
    sort_by: str = "name",
    power_state: Optional[str] = None,
    fields: Optional[list[str]] = None,
    folder_filter: Optional[str] = None,
) -> dict:
    """[READ] List virtual machines with optional filtering, sorting, and field selection.

    Returns a dict: {total, mode, vms, hint}. Each VM entry includes a
    ``folder_path`` field showing the vCenter inventory folder path
    (e.g. ``/Colocation/Colo - ISER``).

    Auto-compact: when no limit/fields are set and inventory exceeds 50 VMs,
    returns compact fields (name, power_state, cpu, memory_mb, folder_path) to
    keep context manageable. Set limit or fields to override.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of VMs to return (None = all).
        sort_by: Sort field: "name" | "cpu" | "memory_mb" | "power_state" | "folder_path".
        power_state: Filter by power state: "poweredOn" | "poweredOff" | "suspended".
        fields: Return only these fields (None = auto-select based on inventory size).
            Available: name, power_state, cpu, memory_mb, guest_os, ip_address,
                       host, uuid, tools_status, folder_path.
        folder_filter: Case-insensitive substring match against folder_path.
            Example: ``folder_filter="Colocation"`` returns VMs anywhere under
            a Colocation folder, including nested subfolders.
    """
    si = _get_connection(target)
    return list_vms(
        si,
        limit=limit,
        sort_by=sort_by,
        power_state=power_state,
        fields=fields,
        folder_filter=folder_filter,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def list_esxi_hosts(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] List ESXi hosts with CPU cores, memory, version, VM count, and uptime.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of hosts to return (None = all).
    """
    si = _get_connection(target)
    results = list_hosts(si)
    if limit is not None:
        results = results[:limit]
    return results


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def list_all_datastores(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] List datastores with capacity, free space, type, and VM count.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of datastores to return (None = all).
    """
    si = _get_connection(target)
    results = list_datastores(si)
    if limit is not None:
        results = results[:limit]
    return results


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def list_all_clusters(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] List clusters with host count, DRS/HA status, and resource totals.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of clusters to return (None = all).
    """
    si = _get_connection(target)
    results = list_clusters(si)
    if limit is not None:
        results = results[:limit]
    return results


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def cluster_health_summary(
    target: Optional[str] = None,
    cluster_filter: Optional[str] = None,
    include_vms: bool = True,
    top_n: int = 10,
) -> dict:
    """[READ] One-glance health rollup for every cluster — "is anything on fire?".

    Aggregates hosts, VM power state, live CPU/memory pressure, and triggered
    alarms per cluster in three batched server-side passes (not one call per
    object), assigns each cluster an opinionated status ("ok"/"warn"/"critical"),
    AND flattens the individual anomalies into a ranked ``top_issues`` focus list
    — the headline for large environments where scanning every cluster row is too
    slow. Use this FIRST for a cross-cluster triage view instead of stitching
    list_all_clusters + list_esxi_hosts + get_alarms yourself; then drill into
    those tools for detail on whatever ``top_issues`` points at.

    Returns {totals, top_issues, issues_total, clusters, snapshot,
    customization_hint}. Lead with ``top_issues`` (the top N things wrong right
    now, worst first), show the ``clusters`` table as context, and always echo
    ``customization_hint`` as the closing line. ``issues_total`` reveals how many
    anomalies existed before the top_n cap. Point-in-time snapshot — no trending.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        cluster_filter: Case-insensitive substring to show only matching clusters
            (None = all clusters plus a standalone-hosts row).
        include_vms: Roll up VM total/powered-on counts (default True). Set False
            to skip the VM inventory pass on very large fleets when you only need
            host/alarm/capacity signals.
        top_n: Cap the top_issues focus list at this many entries (default 10).
            Use 5 for an even tighter view, or 0 to omit the list.
    """
    si = _get_connection(target)
    return get_cluster_health_summary(
        si, cluster_filter=cluster_filter, include_vms=include_vms, top_n=top_n
    )


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def list_all_networks(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] List networks with name, attached VM count, and accessibility.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of networks to return (None = all).
    """
    si = _get_connection(target)
    results = list_networks(si)
    if limit is not None:
        results = results[:limit]
    return results


# ---------------------------------------------------------------------------
# Health tools (read-only)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def get_alarms(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] Get active/triggered alarms across the VMware inventory.

    Each alarm includes suggested_actions with ready-to-use hints pointing to
    the correct companion skill and tool for remediation.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of alarms to return (None = all). Use when many alarms are active.
    """
    si = _get_connection(target)
    results = get_active_alarms(si)
    if limit is not None:
        results = results[:limit]
    return results


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def get_events(
    hours: int = 24,
    severity: str = "warning",
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] Get recent vCenter/ESXi events filtered by severity.

    Args:
        hours: How many hours back to query (default 24).
        severity: Minimum severity level: "critical", "warning", or "info".
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_recent_events(si, hours=hours, severity=severity)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def get_host_sensors(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] Get hardware sensor status (temperature, voltage, fan, ...) for all hosts.

    Each entry includes host, sensor_name, type, reading, unit, and status
    (green/yellow/red from healthState.key). Use to spot failing hardware
    before it causes an outage. Returns an empty list when no host exposes
    sensor data (e.g. nested ESXi).

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of sensor rows to return (None = all).
    """
    si = _get_connection(target)
    results = get_host_hardware_status(si)
    if limit is not None:
        results = results[:limit]
    return results


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def get_host_services(
    host_name: Optional[str] = None,
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] Get host service status (running state and startup policy).

    Each entry includes host, service key, label, running (bool), and policy
    (on/off/automatic). Use to check whether SSH, NTP, or the firewall service
    is in the expected state.

    Args:
        host_name: Filter to a single host by exact name (None = all hosts).
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return _ops_get_host_services(si, host_name=host_name)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def host_log_scan(
    host_name: Optional[str] = None,
    lines: int = 500,
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] Scan recent ESXi host syslog lines for error/warning patterns.

    Reads the last ``lines`` entries of the hostd/vmkernel/vpxa logs on each
    host via the diagnostic system and returns only the lines matching known
    trouble patterns (error, fail, critical, panic, lost access, timeout, …).
    Each entry has severity, source (``host_log:<key>``), message, time, and
    entity (host name). Returns an empty list when no matching lines are found.

    Only errors/warnings are returned, not the full log, so output stays small
    even on large clusters. Filter to one host with ``host_name`` to keep the
    scan fast on environments with many hosts.

    Args:
        host_name: Filter to a single host by exact name (None = all hosts).
        lines: How many recent lines per log to scan (default 500).
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return _ops_scan_host_logs(si, host_name=host_name, lines=lines)


# ---------------------------------------------------------------------------
# VM info tool (read-only)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def vm_info(vm_name: str, target: Optional[str] = None) -> dict:
    """[READ] Get detailed information about a specific VM (CPU, memory, disks, NICs, snapshots).

    Args:
        vm_name: Exact name of the virtual machine.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_vm_info(si, vm_name)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def vm_list_snapshots(vm_name: str, target: Optional[str] = None) -> list[dict]:
    """[READ] List all snapshots of a VM, including the nesting hierarchy.

    Returns one entry per snapshot with name, description, created timestamp,
    state, and level (0 = root; children are level+1). Returns an empty list
    when the VM has no snapshots. Read-only — this skill cannot create,
    revert, or delete snapshots (use vmware-aiops for those operations).
    Exposes the same data as the CLI command `vmware-monitor vm snapshot-list`
    (was missing from MCP until 2026-06-08 — CLI/MCP parity, 踩坑 #34).

    Args:
        vm_name: Exact name of the virtual machine.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_snapshots(si, vm_name)


# ---------------------------------------------------------------------------
# Performance tools (read-only — real-time PerfManager counters)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def host_performance(
    host_name: Optional[str] = None,
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] Real-time CPU/memory/disk/network utilisation per ESXi host.

    Unlike list_esxi_hosts (static config: cores, total GB), this returns LIVE
    utilisation from the 20-second PerfManager interval: cpu_usage_pct,
    mem_usage_pct, mem_consumed_mb, disk_kbps, net_kbps. Busiest hosts first.
    Disconnected hosts and hosts without a real-time provider are skipped (not
    reported as zero). Point-in-time only — no historical trend is retained.

    Args:
        host_name: Filter to a single host by exact name (None = all hosts).
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of host rows to return (None = all).
    """
    si = _get_connection(target)
    return get_host_performance(si, host_name=host_name, limit=limit)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def vm_performance(
    vm_name: Optional[str] = None,
    target: Optional[str] = None,
    limit: Optional[int] = 25,
) -> list[dict]:
    """[READ] Real-time CPU/memory/disk/network utilisation per virtual machine.

    LIVE utilisation (cpu_usage_pct, mem_usage_pct, mem_consumed_mb,
    disk_read_kbps, disk_write_kbps, net_kbps), busiest VMs first. Only
    powered-on VMs have a real-time provider; powered-off VMs are skipped.
    Defaults to the top 25 — pass limit=None for the full fleet. Point-in-time
    only; for trends use a metrics store.

    Args:
        vm_name: Filter to a single VM by exact name (None = all powered-on VMs).
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of VM rows to return (default 25; None = all).
    """
    si = _get_connection(target)
    return get_vm_performance(si, vm_name=vm_name, limit=limit)


# ---------------------------------------------------------------------------
# Snapshot aging (read-only — inventory-wide sprawl analysis)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def snapshot_aging(
    age_threshold_days: int = 30,
    only_old: bool = False,
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """[READ] Sweep ALL VMs for snapshots and flag old / sprawling ones.

    Where vm_list_snapshots covers one VM, this scans the whole inventory and
    judges age. Returns {total_snapshots, old_snapshots, vms_with_snapshots,
    threshold_days, snapshots[], hint}. Each row has age_days, is_old, and an
    est_size_mb lower-bound (snapshotData+snapshotMemory; delta-disk growth is
    not separable per-snapshot via the API). Read-only — delete snapshots via
    vmware-aiops.

    Args:
        age_threshold_days: Age above which a snapshot is flagged "old" (default 30).
        only_old: When True, return only snapshots older than the threshold.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of snapshot rows to return (None = all).
    """
    si = _get_connection(target)
    return list_snapshot_aging(
        si, age_threshold_days=age_threshold_days, only_old=only_old, limit=limit
    )


# ---------------------------------------------------------------------------
# Infrastructure health (read-only — certificates, licenses, NTP)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def certificate_status(
    warn_days: int = 30,
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] Per-host ESXi management certificate expiry.

    An expired ESXi cert drops host management — this surfaces it before the
    outage. Returns host, not_after, days_until_expiry, and an ``expiring`` flag
    (within warn_days or already expired), soonest-to-expire first. Uses the
    API-native certificateInfo (no PEM parsing).

    Args:
        warn_days: Flag certs expiring within this many days (default 30).
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of host rows to return (None = all).
    """
    si = _get_connection(target)
    return get_certificate_status(si, warn_days=warn_days, limit=limit)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def license_status(target: Optional[str] = None) -> list[dict]:
    """[READ] vCenter/ESXi license inventory with usage and expiry.

    Returns one row per license: name, edition_key, total/used units,
    unlimited flag (total==0), and expiration. Use to catch over-allocation or
    an approaching license expiry.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_license_status(si)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def ntp_status(
    host_name: Optional[str] = None,
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] Per-host NTP configuration health (servers + ntpd service state).

    Returns host, ntp_servers, ntpd_running, ntpd_policy, and a ``healthy`` flag
    (servers configured AND ntpd running). NOTE: the SOAP API does not expose
    the live clock offset/stratum — this reports configuration health only (the
    actionable signal). For actual offset use esxcli on the host.

    Args:
        host_name: Filter to a single host by exact name (None = all hosts).
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_ntp_status(si, host_name=host_name)


# ---------------------------------------------------------------------------
# Capacity analytics (read-only — over-commit and resource pools)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def datastore_capacity(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] Per-datastore capacity with thin-provisioning over-commit.

    Adds the risk signal list_all_datastores lacks: overcommit_pct
    (provisioned / capacity * 100). Over 100% means more space is promised to
    VMs than physically exists — a thin datastore can fill up while still
    showing free space. Returns capacity_gb, free_gb, committed_gb,
    provisioned_gb, used_pct, overcommit_pct; riskiest first. Point-in-time.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of datastore rows to return (None = all).
    """
    si = _get_connection(target)
    return get_datastore_capacity(si, limit=limit)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def resource_pool_usage(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] Per-resource-pool CPU/memory reservation, limit, and current usage.

    Returns name, cpu_reservation_mhz, cpu_limit_mhz, cpu_usage_mhz,
    mem_reservation_mb, mem_limit_mb, mem_usage_mb. A limit of -1 means
    unlimited. Use to spot pools near their reservation/limit. Sorted by memory
    usage descending.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of pool rows to return (None = all).
    """
    si = _get_connection(target)
    return get_resource_pool_usage(si, limit=limit)


# ---------------------------------------------------------------------------
# Activity tracking (read-only — tasks and sessions)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def active_tasks(
    include_recent: bool = True,
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] In-flight (and optionally just-completed) vCenter tasks.

    Answers "why is the cluster busy?". Returns name, entity, state,
    progress_pct, start_time, user, active flag, and error (for failed recent
    tasks). Running/queued first. Read-only — cancel tasks via vmware-aiops.

    Args:
        include_recent: Also include recently completed/failed tasks (default True).
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of task rows to return (None = all).
    """
    si = _get_connection(target)
    return get_active_tasks(si, include_recent=include_recent, limit=limit)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@_catch_tool_errors
def active_sessions(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] Currently authenticated vCenter/ESXi sessions (who is logged in).

    Returns user_name, full_name, login_time, last_active, ip_address, and a
    ``current`` flag for this skill's own session. Requires Sessions privilege;
    low-privilege accounts get a single explanatory row instead of a traceback.
    Read-only — terminating sessions is not supported here.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of session rows to return (None = all).
    """
    si = _get_connection(target)
    return get_active_sessions(si, limit=limit)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
