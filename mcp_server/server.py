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


@mcp.tool()
def list_virtual_machines(
    target: str | None = None,
    limit: int | None = None,
    sort_by: str = "name",
    power_state: str | None = None,
    fields: list[str] | None = None,
) -> dict:
    """List virtual machines with optional filtering, sorting, and field selection.

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
    si = _get_connection(target)
    return list_vms(si, limit=limit, sort_by=sort_by, power_state=power_state, fields=fields)


@mcp.tool()
def list_esxi_hosts(target: str | None = None) -> list[dict]:
    """List all ESXi hosts with CPU cores, memory, version, VM count, and uptime.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_hosts(si)


@mcp.tool()
def list_all_datastores(target: str | None = None) -> list[dict]:
    """List all datastores with capacity, free space, type, and VM count.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_datastores(si)


@mcp.tool()
def list_all_clusters(target: str | None = None) -> list[dict]:
    """List all clusters with host count, DRS/HA status, and resource totals.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_clusters(si)


# ---------------------------------------------------------------------------
# Health tools (read-only)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_alarms(target: str | None = None) -> list[dict]:
    """Get all active/triggered alarms across the VMware inventory.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_active_alarms(si)


@mcp.tool()
def get_events(
    hours: int = 24,
    severity: str = "warning",
    target: str | None = None,
) -> list[dict]:
    """Get recent vCenter/ESXi events filtered by severity.

    Args:
        hours: How many hours back to query (default 24).
        severity: Minimum severity level: "critical", "warning", or "info".
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_recent_events(si, hours=hours, severity=severity)


# ---------------------------------------------------------------------------
# VM info tool (read-only)
# ---------------------------------------------------------------------------


@mcp.tool()
def vm_info(vm_name: str, target: str | None = None) -> dict:
    """Get detailed information about a specific VM (CPU, memory, disks, NICs, snapshots).

    Args:
        vm_name: Exact name of the virtual machine.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_vm_info(si, vm_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
