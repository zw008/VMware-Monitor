"""CLI entry point for VMware Monitor (read-only).

This CLI contains ONLY read-only commands. No destructive operations exist:
- No power-on/off, reset, suspend
- No create, delete, reconfigure VM
- No snapshot-create, snapshot-revert, snapshot-delete
- No clone, migrate
- No _double_confirm, _show_state_preview, _validate_vm_params
"""

from __future__ import annotations

import signal
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vmware_monitor.config import CONFIG_DIR

app = typer.Typer(
    name="vmware-monitor",
    help="VMware vCenter/ESXi read-only monitoring. No destructive operations.",
    no_args_is_help=True,
)
console = Console()

# Sub-commands (read-only only)
inventory_app = typer.Typer(help="Query vCenter/ESXi inventory (read-only).")
health_app = typer.Typer(help="Health checks: alarms, events, sensors, services (read-only).")
vm_app = typer.Typer(help="VM info and snapshot list (read-only).")
scan_app = typer.Typer(help="Log and alarm scanning (read-only).")
daemon_app = typer.Typer(help="Scanner daemon management.")

app.add_typer(inventory_app, name="inventory")
app.add_typer(health_app, name="health")
app.add_typer(vm_app, name="vm")
app.add_typer(scan_app, name="scan")
app.add_typer(daemon_app, name="daemon")

TargetOption = Annotated[
    str | None, typer.Option("--target", "-t", help="Target name from config")
]
ConfigOption = Annotated[
    Path | None, typer.Option("--config", "-c", help="Config file path")
]


def _get_connection(target: str | None, config_path: Path | None = None):
    """Helper to get a pyVmomi connection."""
    from vmware_monitor.config import load_config
    from vmware_monitor.connection import ConnectionManager

    cfg = load_config(config_path)
    mgr = ConnectionManager(cfg)
    return mgr.connect(target), cfg


# ─── Inventory ────────────────────────────────────────────────────────────────


@inventory_app.command("vms")
def inventory_vms(target: TargetOption = None, config: ConfigOption = None) -> None:
    """List all virtual machines."""
    from vmware_monitor.ops.inventory import list_vms

    si, _ = _get_connection(target, config)
    vms = list_vms(si)
    table = Table(title="Virtual Machines")
    table.add_column("Name", style="cyan")
    table.add_column("Power")
    table.add_column("CPUs", justify="right")
    table.add_column("Memory (MB)", justify="right")
    table.add_column("Guest OS")
    table.add_column("IP Address")
    for vm in vms:
        power_style = "green" if vm["power_state"] == "poweredOn" else "red"
        table.add_row(
            vm["name"],
            f"[{power_style}]{vm['power_state']}[/]",
            str(vm["cpu"]),
            str(vm["memory_mb"]),
            vm["guest_os"],
            vm["ip_address"] or "-",
        )
    console.print(table)


@inventory_app.command("hosts")
def inventory_hosts(target: TargetOption = None, config: ConfigOption = None) -> None:
    """List all ESXi hosts."""
    from vmware_monitor.ops.inventory import list_hosts

    si, _ = _get_connection(target, config)
    hosts = list_hosts(si)
    table = Table(title="ESXi Hosts")
    table.add_column("Name", style="cyan")
    table.add_column("State")
    table.add_column("CPU Cores", justify="right")
    table.add_column("Memory (GB)", justify="right")
    table.add_column("VMs", justify="right")
    for h in hosts:
        state_style = "green" if h["connection_state"] == "connected" else "red"
        table.add_row(
            h["name"],
            f"[{state_style}]{h['connection_state']}[/]",
            str(h["cpu_cores"]),
            str(h["memory_gb"]),
            str(h["vm_count"]),
        )
    console.print(table)


@inventory_app.command("datastores")
def inventory_datastores(
    target: TargetOption = None, config: ConfigOption = None
) -> None:
    """List all datastores."""
    from vmware_monitor.ops.inventory import list_datastores

    si, _ = _get_connection(target, config)
    stores = list_datastores(si)
    table = Table(title="Datastores")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Free (GB)", justify="right")
    table.add_column("Total (GB)", justify="right")
    table.add_column("Usage %", justify="right")
    for ds in stores:
        pct = ((ds["total_gb"] - ds["free_gb"]) / ds["total_gb"] * 100) if ds["total_gb"] else 0
        pct_style = "red" if pct > 85 else "yellow" if pct > 70 else "green"
        table.add_row(
            ds["name"],
            ds["type"],
            f"{ds['free_gb']:.1f}",
            f"{ds['total_gb']:.1f}",
            f"[{pct_style}]{pct:.1f}%[/]",
        )
    console.print(table)


@inventory_app.command("clusters")
def inventory_clusters(
    target: TargetOption = None, config: ConfigOption = None
) -> None:
    """List all clusters."""
    from vmware_monitor.ops.inventory import list_clusters

    si, _ = _get_connection(target, config)
    clusters = list_clusters(si)
    table = Table(title="Clusters")
    table.add_column("Name", style="cyan")
    table.add_column("Hosts", justify="right")
    table.add_column("DRS")
    table.add_column("HA")
    for c in clusters:
        table.add_row(
            c["name"],
            str(c["host_count"]),
            "[green]ON[/]" if c["drs_enabled"] else "[red]OFF[/]",
            "[green]ON[/]" if c["ha_enabled"] else "[red]OFF[/]",
        )
    console.print(table)


# ─── Health ───────────────────────────────────────────────────────────────────


@health_app.command("alarms")
def health_alarms(target: TargetOption = None, config: ConfigOption = None) -> None:
    """Show active alarms."""
    from vmware_monitor.ops.health import get_active_alarms

    si, _ = _get_connection(target, config)
    alarms = get_active_alarms(si)
    if not alarms:
        console.print("[green]No active alarms.[/]")
        return
    table = Table(title="Active Alarms")
    table.add_column("Severity")
    table.add_column("Alarm", style="cyan")
    table.add_column("Entity")
    table.add_column("Time")
    for a in alarms:
        sev_style = {"red": "red", "yellow": "yellow"}.get(a["severity"], "white")
        table.add_row(
            f"[{sev_style}]{a['severity']}[/]",
            a["alarm_name"],
            a["entity_name"],
            a["time"],
        )
    console.print(table)


@health_app.command("events")
def health_events(
    hours: Annotated[int, typer.Option(help="Lookback hours")] = 24,
    severity: Annotated[str, typer.Option(help="Min severity: info/warning/error")] = "warning",
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show recent events."""
    from vmware_monitor.ops.health import get_recent_events

    si, _ = _get_connection(target, config)
    events = get_recent_events(si, hours=hours, severity=severity)
    if not events:
        console.print(f"[green]No events above '{severity}' in the last {hours}h.[/]")
        return
    table = Table(title=f"Events (last {hours}h, >= {severity})")
    table.add_column("Time")
    table.add_column("Type", style="cyan")
    table.add_column("Message")
    for e in events:
        table.add_row(e["time"], e["event_type"], e["message"][:120])
    console.print(table)


# ─── VM (read-only: info and snapshot-list only) ─────────────────────────────


@vm_app.command("info")
def vm_info(
    name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show detailed info for a VM (read-only)."""
    from vmware_monitor.ops.vm_info import get_vm_info

    si, _ = _get_connection(target, config)
    info = get_vm_info(si, name)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@vm_app.command("snapshot-list")
def vm_snapshot_list(
    vm_name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List VM snapshots (read-only)."""
    from vmware_monitor.ops.vm_info import list_snapshots

    si, _ = _get_connection(target, config)
    snaps = list_snapshots(si, vm_name)
    if not snaps:
        console.print("[yellow]No snapshots found.[/]")
        return
    for s in snaps:
        prefix = "  " * s["level"]
        console.print(f"{prefix}[cyan]{s['name']}[/] ({s['created']}) - {s['description']}")


# ─── Scan ─────────────────────────────────────────────────────────────────────


@scan_app.command("now")
def scan_now(target: TargetOption = None, config: ConfigOption = None) -> None:
    """Run a one-time scan of alarms and events."""
    from vmware_monitor.scanner.alarm_scanner import scan_alarms
    from vmware_monitor.scanner.log_scanner import scan_logs

    si, cfg = _get_connection(target, config)
    console.print("[bold]Running scan...[/]")
    alarm_results = scan_alarms(si)
    log_results = scan_logs(si, cfg.scanner)
    total = len(alarm_results) + len(log_results)
    if total == 0:
        console.print("[green]All clear. No issues found.[/]")
    else:
        console.print(f"[yellow]Found {total} issue(s).[/]")
        for r in alarm_results + log_results:
            sev_style = {"critical": "red", "warning": "yellow"}.get(
                r["severity"], "white"
            )
            console.print(
                f"  [{sev_style}][{r['severity'].upper()}][/] {r['message']}"
            )


# ─── Daemon ───────────────────────────────────────────────────────────────────


@daemon_app.command("start")
def daemon_start(config: ConfigOption = None) -> None:
    """Start the scanner daemon."""
    from vmware_monitor.scanner.scheduler import start_scheduler

    console.print("[bold]Starting scanner daemon...[/]")
    start_scheduler(config)


@daemon_app.command("status")
def daemon_status() -> None:
    """Check scanner daemon status."""
    pid_file = CONFIG_DIR / "daemon.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        console.print(f"[green]Daemon running (PID: {pid})[/]")
    else:
        console.print("[yellow]Daemon not running.[/]")


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Stop the scanner daemon."""
    import os as _os

    pid_file = CONFIG_DIR / "daemon.pid"
    if not pid_file.exists():
        console.print("[yellow]Daemon not running.[/]")
        return

    pid = int(pid_file.read_text().strip())
    try:
        _os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Daemon (PID: {pid}) stopped.[/]")
    except ProcessLookupError:
        console.print(f"[yellow]Daemon process (PID: {pid}) not found. Cleaning up.[/]")
    except OSError as e:
        console.print(f"[red]Failed to stop daemon: {e}[/]")
        return
    pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    app()
