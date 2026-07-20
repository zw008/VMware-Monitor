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
from vmware_policy import (
    apply_read_only_gate,
    mtime_cached_loader,
    sanitize,
    set_environment_resolver,
    vmware_tool,
)

# Internal VMware monitoring modules (all read-only operations)
from vmware_monitor.config import CONFIG_FILE, load_config
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
from vmware_monitor.ops.attention import get_cross_vcenter_attention
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
from vmware_monitor.ops.investigate_datastore import (
    DatastoreNotFoundError,
    get_datastore_investigation_bundle,
)
from vmware_monitor.ops.investigate_host import (
    HostNotFoundError,
    get_host_investigation_bundle,
)
from vmware_monitor.ops.investigate_vm import get_vm_investigation_bundle
from vmware_monitor.ops.performance import get_host_performance, get_vm_performance
from vmware_monitor.ops.snapshots import list_snapshot_aging
from vmware_monitor.ops.vm_info import VMNotFoundError, get_vm_info, list_snapshots
from vmware_monitor.scanner.log_scanner import scan_host_logs as _ops_scan_host_logs

logger = logging.getLogger(__name__)


def _safe_error(exc: Exception, tool: str) -> str:
    """Return an agent-safe error string; log full detail server-side only.

    Raw exception text can carry API response bodies, internal paths, or
    host:port pairs. Full traceback goes to the server log; the agent sees only
    a control-char-stripped, length-capped message.

    Every exception this skill raises on purpose passes through: the builtin
    validation errors, and the domain exceptions defined under
    ``vmware_monitor.ops``. Those three cover this skill's most common failure —
    a name that does not resolve — and each carries the sentence naming the
    listing tool that produces a valid one. Omitting them replaced that sentence
    with ``VMNotFoundError: operation failed.`` on the way to the agent, so the
    teaching text was written, printed in full by the CLI, and discarded at the
    one surface where a model would have used it.

    ``TimeoutError`` and ``ConnectionError`` are here for the same reason: the
    CLI path catches ``OSError`` and prints a retry hint, and the two surfaces
    should not disagree about what a dropped connection means.

    ``OSError`` itself is here because ``config.py`` raises exactly one — the
    missing-password error, this family's most common first-run failure, whose
    entire remedy is the env var name it carries. Its subclasses
    ``FileNotFoundError``, ``PermissionError``, ``TimeoutError`` and
    ``ConnectionError`` were already allowed, so admitting the base class
    widens exposure only to the remaining OS-level subtypes.

    Anything else is reduced to its type — an unplanned exception's text was
    written for a developer reading a traceback, not for an agent choosing what
    to do next, and it is the one that can carry credentials.
    """
    logger.error("Tool %s failed", tool, exc_info=True)
    _passthrough = (
        ValueError,
        FileNotFoundError,
        KeyError,
        PermissionError,
        TimeoutError,
        ConnectionError,
        OSError,
        VMNotFoundError,
        HostNotFoundError,
        DatastoreNotFoundError,
    )
    if isinstance(exc, _passthrough):
        return sanitize(str(exc), 300)
    return f"{type(exc).__name__}: operation failed."


_DOCTOR_HINT = "Run 'vmware-monitor doctor' to verify connectivity and credentials."


def _catch_tool_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Translate tool exceptions into an error payload.

    Every tool returns a dict — list-returning tools return the family list
    envelope (``{items, returned, limit, total, truncated, hint}``) rather than
    a bare ``list[dict]``, so the error payload is a plain dict too and matches
    the return annotation FastMCP validates against. Passes the real tool name
    (fn.__name__) to _safe_error instead of the old literal "monitor".
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return {"error": _safe_error(e, fn.__name__), "hint": _DOCTOR_HINT}

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


def _ensure_conn_mgr() -> ConnectionManager:
    """Lazily build the shared ConnectionManager (does not connect anything)."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_MONITOR_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr


def _get_connection(target: Optional[str] = None) -> Any:
    """Return a pyVmomi ServiceInstance, lazily initialising the manager."""
    return _ensure_conn_mgr().connect(target)


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

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    plus ``mode`` ("full"/"compact"); ``total`` is the real post-filter count, so
    read ``truncated`` before summarising. Each VM entry carries ``folder_path``,
    its vCenter inventory folder path (e.g. ``/Colocation/Colo - ISER``).

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
) -> dict:
    """[READ] List ESXi hosts with CPU cores, memory, version, VM count, and uptime.

    Returns the list envelope {items, returned, limit, total, truncated, hint}.
    ``total`` is the real host count, so a full page that matches it is stated
    to be complete instead of leaving you to guess.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of hosts to return (None = all).
    """
    si = _get_connection(target)
    return list_hosts(si, limit=limit)


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
) -> dict:
    """[READ] List datastores with capacity, free space, type, and VM count.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total`` — read ``truncated`` before summarising.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of datastores to return (None = all).
    """
    si = _get_connection(target)
    return list_datastores(si, limit=limit)


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
) -> dict:
    """[READ] List clusters with host count, DRS/HA status, and resource totals.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total`` — read ``truncated`` before summarising.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of clusters to return (None = all).
    """
    si = _get_connection(target)
    return list_clusters(si, limit=limit)


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
def vm_investigation_bundle(
    vm_name: str,
    target: Optional[str] = None,
    hours: int = 24,
) -> dict:
    """[READ] "What is happening around this VM?" — one correlated drill-down.

    Collects and *correlates* everything around a single VM so you don't stitch
    vm_info + vm_list_snapshots + get_alarms + vm_performance + get_events
    yourself (which a smaller model often mis-orders): the VM's state, the host it
    runs on, its cluster context, the datastores backing it, its snapshots and
    triggered alarms, live performance, and a merged **event timeline** correlating
    recent events from the VM, host, cluster and datastores (newest first). All
    cross-object reads are batched — cheap even on large fleets. Aggregation happens
    in the tool; explain the result in operational language, do not dump it raw.

    Use this AFTER cluster_health_summary points at a problem VM, or whenever the
    operator asks "what's going on with <vm>?". Point-in-time snapshot — no trending.

    Args:
        vm_name: Exact VM name. Unknown names return a teaching error naming how to
            list VMs. Get the name from list_virtual_machines or
            cluster_health_summary first.
        target: Optional vCenter/ESXi target name from config (default target if omitted).
        hours: Event-timeline look-back window in hours (default 24).
    """
    si = _get_connection(target)
    return get_vm_investigation_bundle(si, vm_name, hours=hours)


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
def host_investigation_bundle(
    host_name: str,
    target: Optional[str] = None,
    hours: int = 24,
) -> dict:
    """[READ] "What is happening around this ESXi host?" — one correlated drill-down.

    Collects and *correlates* everything around a single host: its state (connection,
    CPU/memory pressure, ESXi version, uptime), its cluster context, a rollup of the
    VMs it runs (total / powered-on + a sample), the datastores it mounts, triggered
    alarms across host/cluster/datastore, live performance, and a merged **event
    timeline** correlating recent events from the host, cluster and datastores. All
    reads are batched. Aggregation happens in the tool; explain it in operational
    language, do not dump it raw.

    Use this AFTER cluster_health_summary flags a host, or when the operator asks
    "what's going on with host <x>?". Point-in-time snapshot — no trending.

    Args:
        host_name: Exact ESXi host name. Unknown names return a teaching error.
            Get the name from list_esxi_hosts or cluster_health_summary first.
        target: Optional vCenter/ESXi target name from config (default if omitted).
        hours: Event-timeline look-back window in hours (default 24).
    """
    si = _get_connection(target)
    return get_host_investigation_bundle(si, host_name, hours=hours)


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
def datastore_investigation_bundle(
    datastore_name: str,
    target: Optional[str] = None,
    hours: int = 24,
) -> dict:
    """[READ] "What is happening around this datastore?" — one correlated drill-down.

    Collects and *correlates* everything around a single datastore: its capacity /
    free space / accessibility, the hosts that mount it, a rollup of the VMs it backs
    (total / powered-on + a sample), triggered alarms across datastore/host, and a
    merged **event timeline** correlating recent events from the datastore and its
    hosts. All reads are batched. Aggregation happens in the tool; explain it in
    operational language, do not dump it raw. (Per-datastore latency is a separate
    perf report, not included here.)

    Use this AFTER cluster_health_summary flags storage pressure, or when the operator
    asks "what's going on with datastore <x>?". Point-in-time snapshot — no trending.

    Args:
        datastore_name: Exact datastore name. Unknown names return a teaching error.
            Get the name from list_all_datastores or datastore_capacity first.
        target: Optional vCenter/ESXi target name from config (default if omitted).
        hours: Event-timeline look-back window in hours (default 24).
    """
    si = _get_connection(target)
    return get_datastore_investigation_bundle(si, datastore_name, hours=hours)


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
def cross_vcenter_attention(
    cluster_filter: Optional[str] = None,
    top_n: int = 10,
) -> dict:
    """[READ] "What needs attention now?" across EVERY configured vCenter — one list.

    Rolls every configured target's cluster-health summary into a single, globally
    ranked ``top_issues`` list (worst first, each tagged with its ``vcenter``) plus a
    per-target rollup — the "where do I look first, anywhere in the estate?" view.
    Use this instead of calling cluster_health_summary once per target and merging
    yourself. Aggregation happens in the tool; lead with ``top_issues`` and explain
    in operational language.

    Degrades gracefully: a target that cannot be reached (or errors mid-summary) is
    listed under ``unreachable`` with a reason, and the rest still aggregate — so a
    single dead vCenter never sinks the view. Point-in-time snapshot — no trending.

    Args:
        cluster_filter: Case-insensitive cluster substring applied to every target
            (None = all clusters).
        top_n: Cap the merged top_issues focus list (default 10). ``issues_total``
            reports the pre-cap count.
    """
    sessions, unreachable = _ensure_conn_mgr().connect_all()
    return get_cross_vcenter_attention(
        sessions, unreachable=unreachable, cluster_filter=cluster_filter, top_n=top_n
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
) -> dict:
    """[READ] List networks with name, attached VM count, and accessibility.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total`` — read ``truncated`` before summarising.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of networks to return (None = all).
    """
    si = _get_connection(target)
    return list_networks(si, limit=limit)


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
) -> dict:
    """[READ] Get active/triggered alarms across the VMware inventory.

    Each alarm includes suggested_actions with ready-to-use hints pointing to
    the correct companion skill and tool for remediation.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total``. An empty ``items`` with ``truncated`` False means
    there genuinely are no active alarms — never report "no data" otherwise.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of alarms to return (None = all). Use when many alarms are active.
    """
    si = _get_connection(target)
    return get_active_alarms(si, limit=limit)


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
) -> dict:
    """[READ] Get recent vCenter/ESXi events filtered by severity.

    Returns the list envelope {items, returned, limit, total, truncated, hint}.
    No row limit is applied, so ``truncated`` is False; ``total`` is null
    because vCenter's event collector applies its own bounds — widen ``hours``
    if you need to be sure nothing older is being missed.

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
) -> dict:
    """[READ] Get hardware sensor status (temperature, voltage, fan, ...) for all hosts.

    Each entry includes host, sensor_name, type, reading, unit, and status
    (green/yellow/red from healthState.key). Use to spot failing hardware
    before it causes an outage.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total``. Empty ``items`` means no host exposes sensor data
    (e.g. nested ESXi), not that the query failed.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of sensor rows to return (None = all).
    """
    si = _get_connection(target)
    return get_host_hardware_status(si, limit=limit)


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
) -> dict:
    """[READ] Get host service status (running state and startup policy).

    Each entry includes host, service key, label, running (bool), and policy
    (on/off/automatic). Use to check whether SSH, NTP, or the firewall service
    is in the expected state.

    Returns the list envelope {items, returned, limit, total, truncated, hint}.
    Every matching host is enumerated, so ``truncated`` is always False — this
    is the complete picture.

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
) -> dict:
    """[READ] Scan recent ESXi host syslog lines for error/warning patterns.

    Reads the last ``lines`` entries of the hostd/vmkernel/vpxa logs on each
    host via the diagnostic system and returns only the lines matching known
    trouble patterns (error, fail, critical, panic, lost access, timeout, …).
    Each entry has severity, source (``host_log:<key>``), message, time, and
    entity (host name). Empty ``items`` means no matching lines were found.

    Returns the list envelope {items, returned, limit, total, truncated, hint}.
    ``total`` is null on purpose: only the last ``lines`` entries per log are
    read, so this is "errors within the scanned window", not "all errors ever".

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
def vm_list_snapshots(vm_name: str, target: Optional[str] = None) -> dict:
    """[READ] List all snapshots of a VM, including the nesting hierarchy.

    Returns the list envelope {items, returned, limit, total, truncated, hint},
    one entry per snapshot with name, description, created timestamp,
    state, and level (0 = root; children are level+1). Empty ``items`` with
    ``truncated`` False means the VM genuinely has no snapshots. Read-only —
    this skill cannot create,
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
) -> dict:
    """[READ] Real-time CPU/memory/disk/network utilisation per ESXi host.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total`` (hosts that actually reported metrics).
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
) -> dict:
    """[READ] Real-time CPU/memory/disk/network utilisation per virtual machine.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total`` (VMs that actually reported metrics) — with the
    default limit of 25, ``truncated`` tells you whether more VMs are behind it.
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
) -> dict:
    """[READ] Per-host ESXi management certificate expiry.

    An expired ESXi cert drops host management — this surfaces it before the
    outage. Returns the list envelope {items, returned, limit, total,
    truncated, hint} with a real ``total``; each row has host, not_after,
    days_until_expiry, and an ``expiring`` flag
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
def license_status(target: Optional[str] = None) -> dict:
    """[READ] vCenter/ESXi license inventory with usage and expiry.

    Returns the list envelope {items, returned, limit, total, truncated, hint},
    one row per license: name, edition_key, total/used units,
    unlimited flag (row total==0), and expiration. Use to catch over-allocation
    or an approaching license expiry. Every license is enumerated, so
    ``truncated`` is always False — this is the complete inventory.

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
) -> dict:
    """[READ] Per-host NTP configuration health (servers + ntpd service state).

    Returns the list envelope {items, returned, limit, total, truncated, hint};
    every matching host is enumerated, so ``truncated`` is always False.
    Each row has host, ntp_servers, ntpd_running, ntpd_policy, and a ``healthy`` flag
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
) -> dict:
    """[READ] Per-datastore capacity with thin-provisioning over-commit.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total``.
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
) -> dict:
    """[READ] Per-resource-pool CPU/memory reservation, limit, and current usage.

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total``; each row has
    name, cpu_reservation_mhz, cpu_limit_mhz, cpu_usage_mhz,
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
) -> dict:
    """[READ] In-flight (and optionally just-completed) vCenter tasks.

    Answers "why is the cluster busy?". Returns the list envelope {items,
    returned, limit, total, truncated, hint} with a real ``total``; each row has
    name, entity, state,
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
) -> dict:
    """[READ] Currently authenticated vCenter/ESXi sessions (who is logged in).

    Returns the list envelope {items, returned, limit, total, truncated, hint}
    with a real ``total``; each row has
    user_name, full_name, login_time, last_active, ip_address, and a
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
# Read-only gate
# ---------------------------------------------------------------------------


def _config_read_only() -> Optional[bool]:
    """Best-effort read of ``read_only`` from the config file.

    Runs at import time, when no config file need exist yet (tests, ``--help``,
    smoke checks), so every failure degrades to "not configured" and lets the
    env vars decide. None and False are equivalent here — config is the last
    link in the precedence chain — but None keeps 'not configured'
    distinguishable from 'configured off' in logs and debugging.

    Resolved through the same VMWARE_MONITOR_CONFIG override the connection layer
    uses. Reading the default path instead would silently ignore settings in an
    operator's custom config file — a control that appears configured and does
    nothing, which is the exact failure this work exists to remove.
    """
    try:
        _cfg_path = os.environ.get("VMWARE_MONITOR_CONFIG")
        return load_config(Path(_cfg_path) if _cfg_path else None).read_only
    except Exception:  # noqa: BLE001 — absent/unreadable config is not an error here
        return None


# Applied once, after every tool above has registered. This skill is read-only
# by design — every tool is marked [READ], so the gate has nothing to remove.
# It is wired up anyway for interface consistency with the rest of the family,
# and so that "zero write tools" stays provable rather than merely documented
# (issue #31).
WITHHELD_WRITE_TOOLS: list[str] = apply_read_only_gate(
    mcp, "vmware-monitor", config_flag=_config_read_only()
)


# ---------------------------------------------------------------------------
# Environment declaration
# ---------------------------------------------------------------------------


_cached_config = mtime_cached_loader("VMWARE_MONITOR_CONFIG", CONFIG_FILE, load_config)


def _environment_for(target: Optional[str]) -> str:
    """Report the environment a target declares, for policy scoping.

    Policy rules scope by environment ("irreversible work in production needs a
    second person"), and vmware-policy cannot read this skill's config itself.
    Registering this lookup is what lets those rules fire at all. Reloaded on
    config.yaml mtime change so an edit takes effect without restarting the
    server. The config is cached via :func:`vmware_policy.mtime_cached_loader`,
    so repeated tool calls pay one ``os.stat`` instead of a full YAML parse.
    """
    try:
        return _cached_config().environment_for(target)
    except Exception:  # noqa: BLE001 — an unreadable config means "undeclared"
        return ""


set_environment_resolver(_environment_for)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
