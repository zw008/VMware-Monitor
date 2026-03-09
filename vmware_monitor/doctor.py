"""vmware-monitor doctor — environment and connectivity diagnostics."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.table import Table

from vmware_monitor.config import CONFIG_DIR, CONFIG_FILE, ENV_FILE

console = Console()

_PASS = "[green]✓[/]"
_FAIL = "[red]✗[/]"
_INFO = "[cyan]i[/]"


def _check(label: str, fn: Callable[[], tuple[bool, str]]) -> tuple[bool, str, str]:
    try:
        ok, msg = fn()
        return ok, label, msg
    except Exception as e:
        return False, label, f"Error: {e}"


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_config_file() -> tuple[bool, str]:
    if CONFIG_FILE.exists():
        return True, f"Config found: {CONFIG_FILE}"
    return False, f"Config not found: {CONFIG_FILE}  →  Run: vmware-monitor init"


def _check_env_file() -> tuple[bool, str]:
    if not ENV_FILE.exists():
        return False, f".env not found: {ENV_FILE}  →  Run: vmware-monitor init"
    mode = ENV_FILE.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return False, f".env permissions too open ({oct(stat.S_IMODE(mode))})  →  Run: chmod 600 {ENV_FILE}"
    return True, f".env found with correct permissions (600): {ENV_FILE}"


def _check_targets() -> tuple[bool, str]:
    if not CONFIG_FILE.exists():
        return False, "Config file missing — skipping target check"
    import yaml
    with open(CONFIG_FILE) as f:
        raw = yaml.safe_load(f) or {}
    targets = raw.get("targets", [])
    if not targets:
        return False, "No targets configured in config.yaml"
    names = [t.get("name", "?") for t in targets]
    return True, f"{len(targets)} target(s) configured: {', '.join(names)}"


def _check_connectivity() -> tuple[bool, str]:
    import socket
    if not CONFIG_FILE.exists():
        return False, "Config file missing — skipping connectivity check"
    import yaml
    with open(CONFIG_FILE) as f:
        raw = yaml.safe_load(f) or {}
    targets = raw.get("targets", [])
    if not targets:
        return False, "No targets to check"

    results = []
    all_ok = True
    for t in targets:
        host = t.get("host", "")
        port = t.get("port", 443)
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            results.append(f"{host}:{port} ✓")
        except OSError as e:
            results.append(f"{host}:{port} ✗ ({e})")
            all_ok = False
    return all_ok, "  ".join(results)


def _check_auth() -> tuple[bool, str]:
    if not CONFIG_FILE.exists():
        return False, "Config file missing — skipping auth check"
    try:
        from vmware_monitor.config import load_config
        from vmware_monitor.connection import ConnectionManager
        config = load_config()
        if not config.targets:
            return False, "No targets configured"
        conn_mgr = ConnectionManager(config)
        target = config.default_target
        conn_mgr.connect(target.name)
        conn_mgr.disconnect_all()
        return True, f"Authentication OK for target '{target.name}'"
    except KeyError as e:
        return False, f"Missing password env var: {e}"
    except Exception as e:
        return False, f"Auth failed: {e}"


def _check_daemon() -> tuple[bool, str]:
    pid_file = CONFIG_DIR / "daemon.pid"
    if not pid_file.exists():
        return True, "Daemon not running (optional — needed for scheduled scanning)"
    pid = pid_file.read_text().strip()
    try:
        import os as _os
        _os.kill(int(pid), 0)
        return True, f"Daemon running (PID: {pid})"
    except ProcessLookupError:
        return False, f"Daemon PID file exists but process {pid} not found (stale PID?)"
    except OSError:
        return True, f"Daemon running (PID: {pid})"


def _check_mcp_server() -> tuple[bool, str]:
    try:
        import importlib
        importlib.import_module("mcp_server.server")
        return True, "MCP server module loads OK"
    except ImportError as e:
        return False, f"MCP server import failed: {e}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_CHECKS: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
    ("Config file", _check_config_file),
    (".env file", _check_env_file),
    ("Targets configured", _check_targets),
    ("Network connectivity", _check_connectivity),
    ("vSphere authentication", _check_auth),
    ("Scanner daemon", _check_daemon),
    ("MCP server", _check_mcp_server),
]


def run_doctor(skip_auth: bool = False) -> int:
    """Run all checks and print results. Returns exit code (0 = all pass)."""
    console.print("\n[bold]vmware-monitor doctor[/]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("", width=3)
    table.add_column("Check", style="bold", min_width=25)
    table.add_column("Result")

    failures = 0
    for label, fn in _CHECKS:
        if skip_auth and label == "vSphere authentication":
            table.add_row(_INFO, label, "[dim]skipped (--skip-auth)[/]")
            continue
        ok, lbl, msg = _check(label, fn)
        icon = _PASS if ok else _FAIL
        if not ok:
            failures += 1
        table.add_row(icon, lbl, msg)

    console.print(table)

    if failures == 0:
        console.print("\n[green bold]✓ All checks passed.[/]\n")
    else:
        console.print(f"\n[red bold]✗ {failures} check(s) failed.[/]\n")

    return 0 if failures == 0 else 1
