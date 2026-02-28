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

> **Code-level safety**: This is an independent repository. No destructive code paths exist — no power off, delete, create, reconfigure, snapshot-create/revert/delete, clone, or migrate functions are present in the codebase. Safety is enforced at the code level, not just by prompt constraints.
>
> For VM lifecycle operations, use the separate [VMware-AIops](https://github.com/zw008/VMware-AIops) repository.

## Quick Install

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, Kimi, and 30+ AI agents:

```bash
npx skills add zw008/VMware-Monitor
```

### Claude Code

```
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

## When to Use This Skill

- Query VM, host, datastore, cluster, and network inventory
- Check health status, active alarms, hardware sensors, and event logs
- View VM details and list existing snapshots (read-only)
- Run scheduled scanning with webhook notifications (Slack, Discord)

## When NOT to Use This Skill

- Power on/off, reset, suspend VMs → use **vmware-aiops** (separate repo)
- Create, delete, reconfigure VMs → use **vmware-aiops**
- Create, revert, delete snapshots → use **vmware-aiops**
- Clone or migrate VMs → use **vmware-aiops**

## Capabilities (Read-Only)

### 1. Inventory

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| List VMs | ✅ | ✅ | Name, power state, CPU, memory, guest OS, IP |
| List Hosts | ✅ | ⚠️ Self only | CPU cores, memory, ESXi version, VM count, uptime |
| List Datastores | ✅ | ✅ | Capacity, free/used, type (VMFS/NFS), usage % |
| List Clusters | ✅ | ❌ | Host count, DRS/HA status |
| List Networks | ✅ | ✅ | Network name, associated VM count |

### 2. Health & Monitoring

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| Active Alarms | ✅ | ✅ | Severity, alarm name, entity, timestamp |
| Event/Log Query | ✅ | ✅ | Filter by time range, severity; 50+ event types |
| Hardware Sensors | ✅ | ✅ | Temperature, voltage, fan status |
| Host Services | ✅ | ✅ | hostd, vpxa running/stopped status |

**Monitored Event Types:**

| Category | Events |
|----------|--------|
| VM Failures | `VmFailedToPowerOnEvent`, `VmDiskFailedEvent`, `VmFailoverFailed` |
| Host Issues | `HostConnectionLostEvent`, `HostShutdownEvent`, `HostIpChangedEvent` |
| Storage | `DatastoreCapacityIncreasedEvent`, SCSI high latency |
| HA/DRS | `DasHostFailedEvent`, `DrsVmMigratedEvent`, `DrsSoftRuleViolationEvent` |
| Auth | `UserLoginSessionEvent`, `BadUsernameSessionEvent` |

### 3. VM Info & Snapshot List (Read-Only)

| Feature | Details |
|---------|---------|
| VM Info | Name, power state, guest OS, CPU, memory, IP, VMware Tools, disks |
| Snapshot List | List existing snapshots with name and creation time (no create/revert/delete) |

### 4. Scheduled Scanning & Notifications

| Feature | Details |
|---------|---------|
| Daemon | APScheduler-based, configurable interval (default 15 min) |
| Multi-target Scan | Sequentially scan all configured vCenter/ESXi targets |
| Scan Content | Alarms + Events + Host logs (hostd, vmkernel, vpxd) |
| Log Analysis | Regex pattern matching: error, fail, critical, panic, timeout |
| Webhook | Slack, Discord, or any HTTP endpoint |

## Version Compatibility

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | ✅ Full | pyVmomi 8.0.3+ |
| 7.0 / 7.0U1-U3 | ✅ Full | All read-only APIs supported |
| 6.7 | ✅ Compatible | Backward-compatible, tested |
| 6.5 | ✅ Compatible | Backward-compatible, tested |

## Query Audit Trail

All queries are logged to `~/.vmware-monitor/audit.log` (JSONL) for compliance, providing a complete record of what was accessed and when.

## CLI Reference (Read-Only Only)

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
vmware-monitor daemon start
vmware-monitor daemon stop
vmware-monitor daemon status
```

> **Commands NOT available in this repository:** `vm power-on/off`, `vm create/delete/reconfigure`, `vm snapshot-create/revert/delete`, `vm clone/migrate`. These do not exist in the codebase. Use [VMware-AIops](https://github.com/zw008/VMware-AIops) for these.

## Setup

```bash
# 1. Clone & install
git clone https://github.com/zw008/VMware-Monitor.git
cd VMware-Monitor
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Configure
mkdir -p ~/.vmware-monitor
cp config.example.yaml ~/.vmware-monitor/config.yaml
cp .env.example ~/.vmware-monitor/.env
chmod 600 ~/.vmware-monitor/.env
# Edit config.yaml and .env with your target details
```

## MCP Server (Read-Only)

```bash
# Run directly
python -m mcp_server

# Or via the installed entry point
vmware-monitor-mcp

# With a custom config path
VMWARE_MONITOR_CONFIG=/path/to/config.yaml python -m mcp_server
```

**Claude Desktop config** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "vmware-monitor": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "VMWARE_MONITOR_CONFIG": "/path/to/config.yaml"
      }
    }
  }
}
```

## License

MIT
