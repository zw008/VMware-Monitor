---
name: vmware-monitor
description: >
  VMware vCenter/ESXi read-only monitoring skill. Code-level enforced safety —
  no destructive operations exist in this codebase. Query inventory, check
  health/alarms/events, view VM info and snapshots, scan logs.
---

# VMware Monitor (Read-Only)

Safe, read-only VMware vCenter and ESXi monitoring skill.

> **Code-level safety**: Independent repository (`zw008/VMware-Monitor`). No destructive code paths exist.

## First Interaction

Ask which environment (vCenter/ESXi) and target to monitor. Guide config setup if needed.

## Commands (Read-Only ONLY)

```bash
vmware-monitor inventory vms|hosts|datastores|clusters [--target <name>]
vmware-monitor health alarms|events [--target <name>]
vmware-monitor vm info <vm-name>
vmware-monitor vm snapshot-list <vm-name>
vmware-monitor scan now [--target <name>]
vmware-monitor daemon start|stop|status
```

## NOT Available (do not exist in codebase)

- power-on/off, create, delete, reconfigure
- snapshot-create/revert/delete, clone, migrate

For these → `npx skills add zw008/VMware-AIops`

## Setup

```bash
git clone https://github.com/zw008/VMware-Monitor.git && cd VMware-Monitor
pip install -e .
mkdir -p ~/.vmware-monitor
cp config.example.yaml ~/.vmware-monitor/config.yaml
cp .env.example ~/.vmware-monitor/.env && chmod 600 ~/.vmware-monitor/.env
```
