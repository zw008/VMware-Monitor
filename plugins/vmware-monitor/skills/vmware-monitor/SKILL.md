---
name: vmware-monitor
description: >
  VMware vCenter/ESXi read-only monitoring skill. Code-level enforced safety —
  no destructive operations exist in this codebase. Query inventory, check
  health/alarms/events, view VM info and snapshots, scan logs.
installer:
  kind: uv
  package: vmware-monitor
---

# VMware Monitor (Read-Only)

Safe, read-only VMware vCenter and ESXi monitoring skill. Query your entire VMware infrastructure using natural language through any AI coding assistant — without risk of accidental modifications.

> **Code-level safety**: This is an independent repository (`zw008/VMware-Monitor`). No destructive code paths exist — no power off, delete, create, reconfigure, snapshot-create/revert/delete, clone, or migrate functions are present in the codebase. For full operations, use the separate [VMware-AIops](https://github.com/zw008/VMware-AIops) repo. Install: `clawhub install vmware-aiops`

## When to Use This Skill

- Query VM, host, datastore, cluster, and network inventory
- Check health status, active alarms, hardware sensors, and event logs
- View VM details and existing snapshot lists (read-only)
- Run scheduled log scanning with webhook notifications (Slack, Discord)
- **You need zero-risk monitoring** — no accidental power-off, delete, or reconfigure possible

## Quick Install

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, Kimi, and 30+ AI agents:

```bash
# Via ClawHub (recommended)
clawhub install vmware-monitor

# Via Skills.sh
npx skills add zw008/VMware-Monitor
```

### Claude Code

```
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

## Usage Mode: MCP First, CLI Fallback

**Default: MCP mode** — vmware-monitor runs as an MCP Server registered in Claude Code. All monitoring queries go through MCP tool calls directly, no manual CLI needed.

**Fallback: CLI mode** — only when MCP connection fails (server crash, config error, etc.), switch to CLI commands via `vmware-monitor` in the terminal.

### MCP Tools (7 tools, all read-only)

| MCP Tool | Description | Equivalent CLI |
|----------|-------------|----------------|
| `list_virtual_machines` | List all VMs | `vmware-monitor inventory vms` |
| `list_esxi_hosts` | List ESXi hosts | `vmware-monitor inventory hosts` |
| `list_all_datastores` | List datastores | `vmware-monitor inventory datastores` |
| `list_all_clusters` | List clusters | `vmware-monitor inventory clusters` |
| `get_alarms` | Active alarms | `vmware-monitor health alarms` |
| `get_events` | Recent events | `vmware-monitor health events` |
| `vm_info` | VM details | `vmware-monitor vm info <name>` |

All tools accept optional `target` parameter (e.g., `"home-esxi"`, `"prod-vcenter"`).

### MCP Direct Calling Pattern (Default)

When this skill is activated, **always use direct Python import** to call MCP tools:

```python
# Set working directory and use the project venv
# cd /path/to/VMware-Monitor

from mcp_server.server import (
    list_virtual_machines,
    list_esxi_hosts,
    list_all_datastores,
    list_all_clusters,
    get_alarms,
    get_events,
    vm_info,
)

# Example: List all VMs
result = list_virtual_machines(target='home-esxi')

# Example: Get alarms
alarms = get_alarms(target='home-vcenter')

# Example: Get VM details
info = vm_info(vm_name='my-vm', target='home-esxi')

# Example: Get events (last 24h, warning+)
events = get_events(hours=24, severity='warning', target='home-esxi')
```

**Calling priority:**
1. ✅ Direct import from `mcp_server.server` (fastest, default)
2. ⚠️ CLI fallback: `vmware-monitor inventory vms` (when import fails)

### MCP Setup (Claude Code)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vmware-monitor": {
      "command": "/path/to/VMware-Monitor/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/VMware-Monitor",
      "env": {
        "VMWARE_MONITOR_CONFIG": "~/.vmware-monitor/config.yaml"
      }
    }
  }
}
```

### When to Fall Back to CLI

- MCP server fails to start or crashes mid-session
- Need daemon/scan features not exposed via MCP (`scan now`, `daemon start`)
- Debugging connection issues (CLI gives more verbose output)

```bash
# Activate venv and run CLI
source /path/to/VMware-Monitor/.venv/bin/activate
vmware-monitor inventory vms --target home-esxi
```

## Architecture

```
User (Natural Language)
  ↓
AI CLI Tool (Claude Code / Gemini / Codex / Aider / Continue / Trae / Kimi)
  ↓
  ├─ MCP mode (default): MCP Server (stdio) ──→ pyVmomi ──→ vSphere API
  │
  └─ CLI fallback: vmware-monitor CLI ──→ pyVmomi ──→ vSphere API
  ↓
vCenter Server ──→ ESXi Clusters ──→ VMs
    or
ESXi Standalone ──→ VMs
```

## First Interaction: Environment Selection

When the user starts a conversation, **always ask first**:

1. **Which environment** do they want to monitor? (vCenter Server or standalone ESXi host)
2. **Which target** from their config? (e.g., `prod-vcenter`, `lab-esxi`)
3. If no config exists yet, guide them through creating `~/.vmware-monitor/config.yaml`

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
| VM Info | Name, power state, guest OS, CPU, memory, IP, VMware Tools, disks, NICs |
| Snapshot List | List existing snapshots with name and creation time (no create/revert/delete) |

### 4. Scheduled Scanning & Notifications

| Feature | Details |
|---------|---------|
| Daemon | APScheduler-based, configurable interval (default 15 min) |
| Multi-target Scan | Sequentially scan all configured vCenter/ESXi targets |
| Scan Content | Alarms + Events + Host logs (hostd, vmkernel, vpxd) |
| Log Analysis | Regex pattern matching: error, fail, critical, panic, timeout |
| Webhook | Slack, Discord, or any HTTP endpoint |

## FORBIDDEN Operations — DO NOT EXIST IN CODEBASE

These operations **cannot** be performed with this skill — zero destructive code paths exist:

- ❌ `vm power-on/off`, `vm reset`, `vm suspend`
- ❌ `vm create/delete/reconfigure`
- ❌ `vm snapshot-create/revert/delete`
- ❌ `vm clone/migrate`

Direct users to **VMware-AIops** (`clawhub install vmware-aiops`) for these.

## Safety Features

| Feature | Details |
|---------|---------|
| Code-Level Isolation | Independent repository — zero destructive functions in codebase |
| Audit Trail | All queries logged to `~/.vmware-monitor/audit.log` (JSONL) |
| Password Protection | `.env` file loading with permission check (warn if not 600) |
| SSL Self-signed Support | `disableSslCertValidation` — **only** for ESXi hosts with self-signed certificates in isolated lab/home environments. Production environments should use CA-signed certificates with full TLS verification enabled. |

## Version Compatibility

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | ✅ Full | pyVmomi 8.0.3+ |
| 7.0 / 7.0U1-U3 | ✅ Full | All read-only APIs supported |
| 6.7 | ✅ Compatible | Backward-compatible, tested |
| 6.5 | ✅ Compatible | Backward-compatible, tested |

> pyVmomi auto-negotiates the API version during SOAP handshake — no manual configuration needed.

## Supported AI Platforms

| Platform | Status | Config File |
|----------|--------|-------------|
| Claude Code | ✅ Native Skill | `plugins/.../SKILL.md` |
| Gemini CLI | ✅ Extension | `gemini-extension/GEMINI.md` |
| OpenAI Codex CLI | ✅ Skill + AGENTS.md | `codex-skill/AGENTS.md` |
| Aider | ✅ Conventions | `codex-skill/AGENTS.md` |
| Continue CLI | ✅ Rules | `codex-skill/AGENTS.md` |
| Trae IDE | ✅ Rules | `trae-rules/project_rules.md` |
| Kimi Code CLI | ✅ Skill | `kimi-skill/SKILL.md` |
| MCP Server | ✅ MCP Protocol | `mcp_server/` |
| Python CLI | ✅ Standalone | N/A |

## CLI Reference

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

## Setup

```bash
# 1. Install via uv (recommended) or pip
uv tool install vmware-monitor
# Or: pip install vmware-monitor

# 2. Configure
mkdir -p ~/.vmware-monitor
vmware-monitor init  # generates config.yaml and .env templates
chmod 600 ~/.vmware-monitor/.env
# Edit ~/.vmware-monitor/config.yaml and .env with your target details
```

### Development Install

```bash
git clone https://github.com/zw008/VMware-Monitor.git
cd VMware-Monitor
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Security

- **Read-Only by Design**: This is an independent repository with zero destructive code paths. No power off, delete, create, reconfigure, or migrate functions exist in the codebase.
- **TLS Verification**: Enabled by default. The `disableSslCertValidation` option exists solely for ESXi hosts using self-signed certificates (common in home labs). In production, always use CA-signed certificates with full TLS verification.
- **Credentials**: Loaded exclusively from environment variables via `.env` file (`chmod 600`). Never passed in CLI arguments, config files, or MCP messages.
- **Webhook Data Scope**: Webhook notifications send monitoring summaries to **user-configured URLs only** (Slack, Discord, or any HTTP endpoint you control). No data is sent to third-party services by default.
- **Prompt Injection Protection**: All vSphere-sourced content (event messages, host logs) is truncated, stripped of control characters, and wrapped in boundary markers before output.
- **Code Review**: We recommend reviewing the source code and commit history before deploying in production. Run in an isolated environment for initial evaluation.

## License

MIT
