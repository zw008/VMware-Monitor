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

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

# MCP SDK — Model Context Protocol server framework
from mcp.server.fastmcp import FastMCP
from vmware_policy import vmware_tool

# Internal VMware monitoring modules (all read-only operations)
from vmware_monitor.config import load_config
from vmware_monitor.connection import ConnectionManager
from vmware_monitor.ops.health import get_active_alarms, get_recent_events
from vmware_monitor.ops.inventory import (
    list_clusters,
    list_datastores,
    list_hosts,
    list_vms,
)
from vmware_monitor.ops.vm_info import get_vm_info

logger = logging.getLogger(__name__)

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

_conn_mgr: ConnectionManager | None = None


def _get_connection(target: str | None = None) -> Any:
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


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_virtual_machines(
    target: str | None = None,
    limit: int | None = None,
    sort_by: str = "name",
    power_state: str | None = None,
    fields: list[str] | None = None,
) -> dict:
    """[READ] List virtual machines with optional filtering, sorting, and field selection.

    Returns a dict: {total, mode, vms, hint}.
    Auto-compact: when no limit/fields are set and inventory exceeds 50 VMs,
    returns compact fields (name, power_state, cpu, memory_mb) to keep context
    manageable. Set limit or fields to override.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of VMs to return (None = all).
        sort_by: Sort field: "name" | "cpu" | "memory_mb" | "power_state".
        power_state: Filter by power state: "poweredOn" | "poweredOff" | "suspended".
        fields: Return only these fields (None = auto-select based on inventory size).
            Available: name, power_state, cpu, memory_mb, guest_os, ip_address,
                       host, uuid, tools_status.
    """
    try:
        si = _get_connection(target)
        return list_vms(si, limit=limit, sort_by=sort_by, power_state=power_state, fields=fields)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-monitor doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_esxi_hosts(
    target: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """[READ] List ESXi hosts with CPU cores, memory, version, VM count, and uptime.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of hosts to return (None = all).
    """
    try:
        si = _get_connection(target)
        results = list_hosts(si)
        if limit is not None:
            results = results[:limit]
        return results
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-monitor doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_all_datastores(
    target: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """[READ] List datastores with capacity, free space, type, and VM count.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of datastores to return (None = all).
    """
    try:
        si = _get_connection(target)
        results = list_datastores(si)
        if limit is not None:
            results = results[:limit]
        return results
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-monitor doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_all_clusters(
    target: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """[READ] List clusters with host count, DRS/HA status, and resource totals.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of clusters to return (None = all).
    """
    try:
        si = _get_connection(target)
        results = list_clusters(si)
        if limit is not None:
            results = results[:limit]
        return results
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-monitor doctor' to verify connectivity and credentials."}


# ---------------------------------------------------------------------------
# Health tools (read-only)
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_alarms(
    target: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """[READ] Get active/triggered alarms across the VMware inventory.

    Each alarm includes suggested_actions with ready-to-use hints pointing to
    the correct companion skill and tool for remediation.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of alarms to return (None = all). Use when many alarms are active.
    """
    try:
        si = _get_connection(target)
        results = get_active_alarms(si)
        if limit is not None:
            results = results[:limit]
        return results
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-monitor doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_events(
    hours: int = 24,
    severity: str = "warning",
    target: str | None = None,
) -> list[dict]:
    """[READ] Get recent vCenter/ESXi events filtered by severity.

    Args:
        hours: How many hours back to query (default 24).
        severity: Minimum severity level: "critical", "warning", or "info".
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    try:
        si = _get_connection(target)
        return get_recent_events(si, hours=hours, severity=severity)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-monitor doctor' to verify connectivity and credentials."}


# ---------------------------------------------------------------------------
# VM info tool (read-only)
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def vm_info(vm_name: str, target: str | None = None) -> dict:
    """[READ] Get detailed information about a specific VM (CPU, memory, disks, NICs, snapshots).

    Args:
        vm_name: Exact name of the virtual machine.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    try:
        si = _get_connection(target)
        return get_vm_info(si, vm_name)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-monitor doctor' to verify connectivity and credentials."}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
