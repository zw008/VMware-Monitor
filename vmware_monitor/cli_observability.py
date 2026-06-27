"""Observability CLI commands: performance, capacity, infra health, activity.

Read-only command groups added on top of the original inventory/health set:

    perf       hosts | vms           real-time PerfManager utilisation
    capacity   datastores | pools    over-commit + resource-pool usage
    infra      certs | licenses | ntp certificate expiry, licensing, NTP config
    snapshots  aging                 inventory-wide snapshot sprawl
    activity   tasks | sessions      in-flight tasks, active sessions

All commands are strictly read-only — no power, create, delete, snapshot
mutation, clone, or migrate exists here or anywhere in vmware-monitor.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from vmware_monitor.cli_base import (
    ConfigOption,
    TargetOption,
    audit,
    cli_errors,
    console,
    get_connection,
)

perf_app = typer.Typer(help="Real-time performance counters (read-only).")
capacity_app = typer.Typer(help="Capacity analytics: over-commit, resource pools (read-only).")
infra_app = typer.Typer(help="Infra health: certificates, licenses, NTP (read-only).")
snapshots_app = typer.Typer(help="Inventory-wide snapshot aging/sprawl (read-only).")
activity_app = typer.Typer(help="Live activity: tasks and sessions (read-only).")

LimitOption = Annotated[int | None, typer.Option("--limit", "-n", help="Max rows to show")]


def _pct_style(value: float, warn: float = 70, crit: float = 85) -> str:
    return "red" if value > crit else "yellow" if value > warn else "green"


# ─── perf ──────────────────────────────────────────────────────────────────


@perf_app.command("hosts")
@cli_errors
def perf_hosts(
    host: Annotated[str | None, typer.Option("--host", help="Single host by exact name")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = None,
) -> None:
    """Real-time CPU/memory/disk/network per ESXi host."""
    from vmware_monitor.ops.performance import get_host_performance

    si, _, tgt = get_connection(target, config)
    rows = get_host_performance(si, host_name=host, limit=limit)
    audit.log_query(target=tgt, resource="host_performance", query_type="get_host_performance")
    if not rows:
        console.print("[yellow]No connected host exposed real-time metrics.[/]")
        return
    table = Table(title="Host Performance (real-time, ~20s interval)")
    table.add_column("Host", style="cyan")
    table.add_column("CPU %", justify="right")
    table.add_column("Mem %", justify="right")
    table.add_column("Mem (MB)", justify="right")
    table.add_column("Disk KB/s", justify="right")
    table.add_column("Net KB/s", justify="right")
    for r in rows:
        cpu = r.get("cpu_usage_pct", 0)
        mem = r.get("mem_usage_pct", 0)
        table.add_row(
            r["host"],
            f"[{_pct_style(cpu)}]{cpu}[/]",
            f"[{_pct_style(mem)}]{mem}[/]",
            str(r.get("mem_consumed_mb", "-")),
            str(r.get("disk_kbps", "-")),
            str(r.get("net_kbps", "-")),
        )
    console.print(table)


@perf_app.command("vms")
@cli_errors
def perf_vms(
    vm: Annotated[str | None, typer.Option("--vm", help="Single VM by exact name")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = 25,
) -> None:
    """Real-time CPU/memory/disk/network per powered-on VM (top 25 by default)."""
    from vmware_monitor.ops.performance import get_vm_performance

    si, _, tgt = get_connection(target, config)
    rows = get_vm_performance(si, vm_name=vm, limit=limit)
    audit.log_query(target=tgt, resource="vm_performance", query_type="get_vm_performance")
    if not rows:
        console.print("[yellow]No powered-on VM exposed real-time metrics.[/]")
        return
    table = Table(title="VM Performance (real-time, ~20s interval)")
    table.add_column("VM", style="cyan")
    table.add_column("CPU %", justify="right")
    table.add_column("Mem %", justify="right")
    table.add_column("Mem (MB)", justify="right")
    table.add_column("Disk R/W KB/s", justify="right")
    table.add_column("Net KB/s", justify="right")
    for r in rows:
        cpu = r.get("cpu_usage_pct", 0)
        mem = r.get("mem_usage_pct", 0)
        rw = f"{r.get('disk_read_kbps', '-')}/{r.get('disk_write_kbps', '-')}"
        table.add_row(
            r["name"],
            f"[{_pct_style(cpu)}]{cpu}[/]",
            f"[{_pct_style(mem)}]{mem}[/]",
            str(r.get("mem_consumed_mb", "-")),
            rw,
            str(r.get("net_kbps", "-")),
        )
    console.print(table)


# ─── capacity ──────────────────────────────────────────────────────────────


@capacity_app.command("datastores")
@cli_errors
def capacity_datastores(
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = None,
) -> None:
    """Datastore capacity with thin-provisioning over-commit."""
    from vmware_monitor.ops.capacity import get_datastore_capacity

    si, _, tgt = get_connection(target, config)
    rows = get_datastore_capacity(si, limit=limit)
    audit.log_query(target=tgt, resource="datastore_capacity", query_type="get_datastore_capacity")
    table = Table(title="Datastore Capacity & Over-commit")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Capacity GB", justify="right")
    table.add_column("Used %", justify="right")
    table.add_column("Provisioned GB", justify="right")
    table.add_column("Over-commit %", justify="right")
    for r in rows:
        oc = r["overcommit_pct"]
        oc_style = "red" if oc > 100 else "yellow" if oc > 80 else "green"
        table.add_row(
            r["name"],
            r["type"],
            f"{r['capacity_gb']}",
            f"[{_pct_style(r['used_pct'])}]{r['used_pct']}[/]",
            f"{r['provisioned_gb']}",
            f"[{oc_style}]{oc}[/]",
        )
    console.print(table)


@capacity_app.command("pools")
@cli_errors
def capacity_pools(
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = None,
) -> None:
    """Resource-pool reservation, limit, and current usage."""
    from vmware_monitor.ops.capacity import get_resource_pool_usage

    si, _, tgt = get_connection(target, config)
    rows = get_resource_pool_usage(si, limit=limit)
    audit.log_query(target=tgt, resource="resource_pools", query_type="get_resource_pool_usage")
    if not rows:
        console.print("[yellow]No resource pools found.[/]")
        return
    table = Table(title="Resource Pool Usage")
    table.add_column("Pool", style="cyan")
    table.add_column("CPU rsv/lim MHz", justify="right")
    table.add_column("CPU used MHz", justify="right")
    table.add_column("Mem rsv/lim MB", justify="right")
    table.add_column("Mem used MB", justify="right")
    for r in rows:
        cpu_rl = f"{r['cpu_reservation_mhz']}/{r['cpu_limit_mhz']}"
        mem_rl = f"{r['mem_reservation_mb']}/{r['mem_limit_mb']}"
        table.add_row(r["name"], cpu_rl, str(r["cpu_usage_mhz"]), mem_rl, str(r["mem_usage_mb"]))
    console.print(table)


# ─── infra ─────────────────────────────────────────────────────────────────


@infra_app.command("certs")
@cli_errors
def infra_certs(
    warn_days: Annotated[int, typer.Option("--warn-days", help="Flag certs within N days")] = 30,
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = None,
) -> None:
    """ESXi host management certificate expiry."""
    from vmware_monitor.ops.infra_health import get_certificate_status

    si, _, tgt = get_connection(target, config)
    rows = get_certificate_status(si, warn_days=warn_days, limit=limit)
    audit.log_query(target=tgt, resource="certificates", query_type="get_certificate_status")
    table = Table(title=f"ESXi Certificates (warn < {warn_days}d)")
    table.add_column("Host", style="cyan")
    table.add_column("Expires")
    table.add_column("Days Left", justify="right")
    for r in rows:
        days = r["days_until_expiry"]
        style = "red" if r["expiring"] else "green"
        table.add_row(r["host"], r["not_after"], f"[{style}]{days if days is not None else '?'}[/]")
    console.print(table)


@infra_app.command("licenses")
@cli_errors
def infra_licenses(target: TargetOption = None, config: ConfigOption = None) -> None:
    """vCenter/ESXi license inventory with usage and expiry."""
    from vmware_monitor.ops.infra_health import get_license_status

    si, _, tgt = get_connection(target, config)
    rows = get_license_status(si)
    audit.log_query(target=tgt, resource="licenses", query_type="get_license_status")
    if not rows:
        console.print("[yellow]No licenses returned.[/]")
        return
    table = Table(title="Licenses")
    table.add_column("Name", style="cyan")
    table.add_column("Used/Total", justify="right")
    table.add_column("Expiration")
    for r in rows:
        total = "∞" if r["unlimited"] else str(r["total"])
        table.add_row(r["name"], f"{r['used']}/{total}", r["expiration"])
    console.print(table)


@infra_app.command("ntp")
@cli_errors
def infra_ntp(
    host: Annotated[str | None, typer.Option("--host", help="Single host by exact name")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Per-host NTP configuration health (config + ntpd state; not live offset)."""
    from vmware_monitor.ops.infra_health import get_ntp_status

    si, _, tgt = get_connection(target, config)
    rows = get_ntp_status(si, host_name=host)
    audit.log_query(target=tgt, resource="ntp", query_type="get_ntp_status")
    table = Table(title="NTP Configuration (live offset not exposed by SOAP API)")
    table.add_column("Host", style="cyan")
    table.add_column("Servers")
    table.add_column("ntpd")
    table.add_column("Policy")
    table.add_column("Healthy")
    for r in rows:
        servers = ", ".join(r["ntp_servers"]) or "[red]none[/]"
        run = "[green]running[/]" if r["ntpd_running"] else "[red]stopped[/]"
        healthy = "[green]yes[/]" if r["healthy"] else "[red]no[/]"
        table.add_row(r["host"], servers, run, r["ntpd_policy"], healthy)
    console.print(table)


# ─── snapshots ─────────────────────────────────────────────────────────────


@snapshots_app.command("aging")
@cli_errors
def snapshots_aging(
    threshold: Annotated[int, typer.Option("--threshold", help="Age (days) to flag as old")] = 30,
    only_old: Annotated[bool, typer.Option("--only-old", help="Show only old snapshots")] = False,
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = None,
) -> None:
    """Inventory-wide snapshot aging and sprawl."""
    from vmware_monitor.ops.snapshots import list_snapshot_aging

    si, _, tgt = get_connection(target, config)
    result = list_snapshot_aging(si, age_threshold_days=threshold, only_old=only_old, limit=limit)
    audit.log_query(target=tgt, resource="snapshot_aging", query_type="list_snapshot_aging")
    console.print(
        f"[bold]{result['total_snapshots']}[/] snapshots on "
        f"[bold]{result['vms_with_snapshots']}[/] VMs; "
        f"[red]{result['old_snapshots']}[/] older than {result['threshold_days']}d."
    )
    if not result["snapshots"]:
        console.print("[green]No snapshots match.[/]")
        return
    table = Table(title="Snapshot Aging (oldest first)")
    table.add_column("VM", style="cyan")
    table.add_column("Snapshot")
    table.add_column("Age (days)", justify="right")
    table.add_column("Est. Size MB", justify="right")
    for s in result["snapshots"]:
        age = s["age_days"]
        style = "red" if s["is_old"] else "white"
        size = s.get("est_size_mb", 0) or "-"
        table.add_row(
            s["vm_name"],
            s["snapshot_name"],
            f"[{style}]{age if age is not None else '?'}[/]",
            str(size),
        )
    console.print(table)
    if result["hint"]:
        console.print(f"[yellow]ℹ {result['hint']}[/yellow]")


# ─── activity ──────────────────────────────────────────────────────────────


@activity_app.command("tasks")
@cli_errors
def activity_tasks(
    all_recent: Annotated[
        bool, typer.Option("--all-recent/--active-only", help="Include completed")
    ] = True,
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = None,
) -> None:
    """In-flight (and recently completed) vCenter tasks."""
    from vmware_monitor.ops.activity import get_active_tasks

    si, _, tgt = get_connection(target, config)
    rows = get_active_tasks(si, include_recent=all_recent, limit=limit)
    audit.log_query(target=tgt, resource="tasks", query_type="get_active_tasks")
    if not rows:
        console.print("[green]No tasks.[/]")
        return
    table = Table(title="Tasks")
    table.add_column("Task", style="cyan")
    table.add_column("Entity")
    table.add_column("State")
    table.add_column("Progress", justify="right")
    table.add_column("User")
    for r in rows:
        state_style = "yellow" if r["active"] else ("red" if r["error"] else "green")
        table.add_row(
            r["name"],
            r["entity"],
            f"[{state_style}]{r['state']}[/]",
            f"{r['progress_pct']}%",
            r["user"],
        )
    console.print(table)


@activity_app.command("sessions")
@cli_errors
def activity_sessions(
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: LimitOption = None,
) -> None:
    """Currently authenticated vCenter/ESXi sessions."""
    from vmware_monitor.ops.activity import get_active_sessions

    si, _, tgt = get_connection(target, config)
    rows = get_active_sessions(si, limit=limit)
    audit.log_query(target=tgt, resource="sessions", query_type="get_active_sessions")
    if rows and rows[0].get("user_name") == "N/A" and "note" in rows[0]:
        console.print(f"[yellow]{rows[0]['note']}[/]")
        return
    table = Table(title="Active Sessions")
    table.add_column("User", style="cyan")
    table.add_column("Full Name")
    table.add_column("Last Active")
    table.add_column("IP")
    for r in rows:
        marker = " [green](this)[/]" if r.get("current") else ""
        table.add_row(r["user_name"] + marker, r["full_name"], r["last_active"], r["ip_address"])
    console.print(table)


def register(app: typer.Typer) -> None:
    """Attach all observability sub-apps to the root CLI."""
    app.add_typer(perf_app, name="perf")
    app.add_typer(capacity_app, name="capacity")
    app.add_typer(infra_app, name="infra")
    app.add_typer(snapshots_app, name="snapshots")
    app.add_typer(activity_app, name="activity")
