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

> **Code-level safety**: This is an independent repository (`zw008/VMware-Monitor`). No destructive code paths exist — no power off, delete, create, reconfigure, snapshot-create/revert/delete, clone, or migrate functions are present in the codebase. For full operations, use the separate [VMware-AIops](https://github.com/zw008/VMware-AIops) repo.

## Quick Install

```bash
npx skills add zw008/VMware-Monitor
```

## First Interaction: Environment Selection

When the user starts a conversation, **always ask first**:

1. **Which environment** do they want to monitor? (vCenter Server or standalone ESXi host)
2. **Which target** from their config? (e.g., `prod-vcenter`, `lab-esxi`)
3. If no config exists yet, guide them through creating `~/.vmware-monitor/config.yaml`

## Available Commands (Read-Only ONLY)

```bash
# Inventory
vmware-monitor inventory vms [--target <name>]
vmware-monitor inventory hosts [--target <name>]
vmware-monitor inventory datastores [--target <name>]
vmware-monitor inventory clusters [--target <name>]

# Health
vmware-monitor health alarms [--target <name>]
vmware-monitor health events [--hours 24] [--severity warning]

# VM Info (read-only)
vmware-monitor vm info <vm-name>
vmware-monitor vm snapshot-list <vm-name>

# Scanning & Daemon
vmware-monitor scan now [--target <name>]
vmware-monitor daemon start|stop|status
```

## FORBIDDEN Operations — DO NOT EXIST IN CODEBASE

- `vm power-on/off`, `vm create/delete/reconfigure`
- `vm snapshot-create/revert/delete`, `vm clone/migrate`

Direct users to **VMware-AIops** (`npx skills add zw008/VMware-AIops`) for these.

## Setup

```bash
git clone https://github.com/zw008/VMware-Monitor.git
cd VMware-Monitor
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

mkdir -p ~/.vmware-monitor
cp config.example.yaml ~/.vmware-monitor/config.yaml
cp .env.example ~/.vmware-monitor/.env
chmod 600 ~/.vmware-monitor/.env
```

## Safety

- READ-ONLY: No state modifications possible at code level
- Audit: All queries logged to `~/.vmware-monitor/audit.log`
- Credentials: `.env` file with `chmod 600`, never hardcoded

## License

MIT
