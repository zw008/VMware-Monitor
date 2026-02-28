---
name: vmware-monitor
description: >
  VMware vCenter/ESXi read-only monitoring skill. Code-level enforced safety —
  no destructive operations exist in this codebase. Query inventory, check
  health/alarms/events, view VM info and snapshots, scan logs.
  Independently installable: npx skills add zw008/VMware-Monitor
---

# VMware Monitor (Read-Only)

Safe, read-only VMware vCenter and ESXi monitoring skill. Query your entire VMware infrastructure using natural language through any AI coding assistant — without risk of accidental modifications.

> **Code-level safety**: This is an independent repository. No destructive code paths exist — no power off, delete, create, reconfigure, snapshot-create/revert/delete, clone, or migrate functions are present in the codebase.

## Quick Install

```bash
npx skills add zw008/VMware-Monitor
```

## First Interaction: Environment Selection

When the user starts a conversation, **always ask first**:

1. **Which environment** do they want to monitor? (vCenter Server or standalone ESXi host)
2. **Which target** from their config? (e.g., `prod-vcenter`, `lab-esxi`)
3. If no config exists yet, guide them through creating `~/.vmware-monitor/config.yaml`

If the user mentions a specific target or host in their first message, skip the prompt and connect directly to that target.

## Connection Setup

```python
from vmware_monitor.connection import ConnectionManager

mgr = ConnectionManager.from_config()
si = mgr.connect("prod-vcenter")
```

Configuration at `~/.vmware-monitor/config.yaml`. Passwords via `~/.vmware-monitor/.env` (chmod 600).

## Available Operations (Read-Only ONLY)

### Inventory
```bash
vmware-monitor inventory vms [--target <name>]
vmware-monitor inventory hosts [--target <name>]
vmware-monitor inventory datastores [--target <name>]
vmware-monitor inventory clusters [--target <name>]
```

### Health
```bash
vmware-monitor health alarms [--target <name>]
vmware-monitor health events [--hours 24] [--severity warning]
```

### VM Info (read-only)
```bash
vmware-monitor vm info <vm-name>
vmware-monitor vm snapshot-list <vm-name>
```

### Scanning
```bash
vmware-monitor scan now [--target <name>]
vmware-monitor daemon start|stop|status
```

## FORBIDDEN Operations

The following operations **DO NOT EXIST** in this codebase:
- `vm power-on`, `vm power-off`, `vm reset`, `vm suspend`
- `vm create`, `vm delete`, `vm reconfigure`
- `vm snapshot-create`, `vm snapshot-revert`, `vm snapshot-delete`
- `vm clone`, `vm migrate`

If a user requests these, direct them to install **VMware-AIops**: `npx skills add zw008/VMware-AIops`

## Safety Rules

1. This skill is READ-ONLY. No state modifications are possible.
2. All queries are logged to `~/.vmware-monitor/audit.log` for compliance.
3. Passwords are loaded from `.env` file, never hardcoded.
4. Connection uses `ConnectionManager.from_config()` — SSL self-signed cert support included.

## License

MIT
