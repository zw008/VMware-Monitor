"""Tests for issue #16 — previously-orphan read-only health/inventory functions.

`get_host_hardware_status`, `get_host_services`, and `list_networks` were
implemented (and `get_host_hardware_status` even bug-fixed in v1.5.32) but had
no CLI/MCP/scanner caller, while help text advertised "sensors, services". They
are now wired up as `health sensors`, `health services`, `inventory networks`
CLI commands and the MCP tools `get_host_sensors`, `get_host_services`,
`list_all_networks`. All are read-only.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vmware_monitor.cli import app

runner = CliRunner()


# ── CLI --help smoke (commands are registered + reachable) ──────────────────


def test_cli_health_lists_sensors_and_services() -> None:
    result = runner.invoke(app, ["health", "--help"])
    assert result.exit_code == 0, result.output
    assert "sensors" in result.output
    assert "services" in result.output


def test_cli_inventory_lists_networks() -> None:
    result = runner.invoke(app, ["inventory", "--help"])
    assert result.exit_code == 0, result.output
    assert "networks" in result.output


def test_cli_health_services_help_includes_host_filter() -> None:
    result = runner.invoke(app, ["health", "services", "--help"])
    assert result.exit_code == 0, result.output
    assert "--host" in result.output


# ── ops behaviour (mirrors the MagicMock style in test_monitor_specific) ────


def test_get_host_services_filters_by_host_name() -> None:
    from unittest.mock import patch

    from vmware_monitor.ops.health import get_host_services

    def _svc_info(svc_key: str) -> MagicMock:
        svc = MagicMock()
        svc.key = svc_key
        svc.label = svc_key.upper()
        svc.running = True
        svc.policy = "on"
        info = MagicMock()
        info.service = [svc]
        return info

    # get_host_services now batches in two passes: pass 1 collects the
    # serviceSystem ref per host, pass 2 (_collect_objects) batches serviceInfo
    # for all refs. Both are patched here.
    ss1, ss2 = MagicMock(name="ss-esxi-1"), MagicMock(name="ss-esxi-2")
    collected = [
        (MagicMock(), {"name": "esxi-1", "configManager.serviceSystem": ss1}),
        (MagicMock(), {"name": "esxi-2", "configManager.serviceSystem": ss2}),
    ]
    boundary = [
        (ss1, {"serviceInfo": _svc_info("TSM-SSH")}),
        (ss2, {"serviceInfo": _svc_info("ntpd")}),
    ]
    with (
        patch("vmware_monitor.ops.health._collect", return_value=collected),
        patch("vmware_monitor.ops.health._collect_objects", return_value=boundary),
    ):
        rows = get_host_services(MagicMock(), host_name="esxi-2")["items"]
    assert [r["host"] for r in rows] == ["esxi-2"]
    assert rows[0]["service"] == "ntpd"
    assert rows[0]["running"] is True


def test_list_networks_returns_name_and_vm_count() -> None:
    from unittest.mock import patch

    from vmware_monitor.ops.inventory import list_networks

    props = {
        "name": "VM Network",
        "vm": [MagicMock(), MagicMock()],
        "summary.accessible": True,
    }
    with patch(
        "vmware_monitor.ops.inventory._collect",
        return_value=[(MagicMock(), props)],
    ):
        rows = list_networks(MagicMock())["items"]
    assert rows == [{"name": "VM Network", "vm_count": 2, "accessible": True}]


# ── MCP registration + read-only annotations ───────────────────────────────


def test_new_mcp_tools_registered_and_read_only() -> None:
    from vmware_monitor.mcp_server.server import mcp

    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for name in ("get_host_sensors", "get_host_services", "list_all_networks"):
        assert name in tools, f"{name} not registered"
        assert tools[name].annotations.readOnlyHint is True, name
        assert tools[name].annotations.destructiveHint is False, name


def test_mcp_get_host_services_does_not_recurse(monkeypatch) -> None:
    """The MCP tool shares a name with the ops function; the import is aliased
    so the tool delegates to ops instead of calling itself."""
    import vmware_monitor.mcp_server.server as srv

    sentinel = [{"host": "esxi-1", "service": "ntpd", "running": True}]
    monkeypatch.setattr(srv, "_get_connection", lambda target=None: MagicMock())
    monkeypatch.setattr(srv, "_ops_get_host_services", lambda si, host_name=None: sentinel)

    assert srv.get_host_services(host_name="esxi-1") == sentinel
