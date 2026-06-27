"""Shared CLI plumbing for VMware Monitor (read-only).

Extracted from cli.py so the growing command set can live in focused modules
(cli.py, cli_observability.py) while sharing one error decorator, connection
helper, audit logger, and option types. Keeps every CLI module under the
800-line family limit.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Annotated, Any, Callable

import typer
from rich.console import Console

from vmware_monitor.notify.audit import AuditLogger

console = Console()
audit = AuditLogger()

TargetOption = Annotated[str | None, typer.Option("--target", "-t", help="Target name from config")]
ConfigOption = Annotated[Path | None, typer.Option("--config", "-c", help="Config file path")]


def fail(message: str) -> None:
    """Print one red teaching line and exit 1 (no traceback)."""
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(1)


def cli_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Translate known failures into one red teaching line + exit 1.

    Without this, config/auth/network problems surface as raw tracebacks.
    Catches: FileNotFoundError, KeyError, OSError (incl. socket errors and
    ConnectionError), VMNotFoundError, and vim/vmodl API faults.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from pyVmomi import vmodl

        from vmware_monitor.ops.vm_info import VMNotFoundError

        try:
            return fn(*args, **kwargs)
        except typer.Exit:
            raise
        except VMNotFoundError as e:
            fail(f"{e}. Run 'vmware-monitor inventory vms' to see available VMs.")
        except FileNotFoundError as e:
            fail(
                f"Config file missing: {e}. Run: vmware-monitor init "
                "(or: mkdir -p ~/.vmware-monitor && cp config.example.yaml "
                "~/.vmware-monitor/config.yaml)"
            )
        except KeyError as e:
            fail(
                f"Missing config key or password env var: {e}. "
                "Check ~/.vmware-monitor/config.yaml and ~/.vmware-monitor/.env."
            )
        except vmodl.MethodFault as e:
            fail(
                f"vSphere API fault: {getattr(e, 'msg', None) or type(e).__name__}. "
                "Run 'vmware-monitor doctor' to verify connectivity and credentials."
            )
        except (ConnectionError, OSError) as e:
            fail(
                f"Connection failed: {e}. "
                "Run 'vmware-monitor doctor' to verify connectivity and credentials."
            )

    return wrapper


def get_connection(target: str | None, config_path: Path | None = None):
    """Helper to get a pyVmomi connection.  Returns (si, cfg, target_name)."""
    from vmware_monitor.config import load_config
    from vmware_monitor.connection import ConnectionManager

    cfg = load_config(config_path)
    mgr = ConnectionManager(cfg)
    target_name = target or cfg.default_target.name
    return mgr.connect(target), cfg, target_name
