---
name: vmware-monitor
description: >
  VMware vCenter/ESXi read-only monitoring skill. Code-level enforced safety —
  no destructive operations exist in this codebase. Query inventory, check
  health/alarms/events, view VM info and snapshots, scan logs.
installer:
  kind: uv
  package: vmware-monitor
metadata: {"openclaw":{"requires":{"env":["VMWARE_MONITOR_CONFIG"],"bins":["vmware-monitor"],"config":["~/.vmware-monitor/config.yaml"]},"primaryEnv":"VMWARE_MONITOR_CONFIG","homepage":"https://github.com/zw008/VMware-Monitor","emoji":"📊","os":["macos","linux"]}}
---

# VMware Monitor (Read-Only)

Safe, read-only VMware vCenter and ESXi monitoring skill — 8 tools, zero destructive code. Query inventory, health, alarms, and events without any risk of accidental changes.

## What This Skill Does

| Tool | What it returns |
|------|----------------|
| `list_virtual_machines` | All VMs — power state, CPU, memory, IP, guest OS |
| `list_esxi_hosts` | Hosts — CPU, memory, version, uptime, VM count |
| `list_all_datastores` | Datastores — capacity, free space, usage %, type |
| `list_all_clusters` | Clusters — host count, HA/DRS status |
| `get_alarms` | Active alarms — severity, entity, timestamp |
| `get_events` | Event log — filter by time range and severity |
| `vm_info` | Single VM detail — disks, NICs, snapshots, tools |

> **Code-level safety**: Independent repository — no destructive functions exist in the codebase. Cannot power off, delete, create, or modify anything.

## Quick Install

```bash
uv tool install vmware-monitor
vmware-monitor doctor
```

## When to Use This Skill

- Query VM, host, datastore, cluster, and network inventory
- Check health status, active alarms, hardware sensors, and event logs
- View VM details and existing snapshot lists (read-only)
- Run scheduled log scanning with webhook notifications (Slack, Discord)
- **You need zero-risk monitoring** — no accidental power-off, delete, or reconfigure possible

## Related Skills — Skill Routing

> Need to do more? Use the right skill:

| User Intent | Recommended Skill | Install |
|-------------|------------------|---------|
| Read-only monitoring ← | **vmware-monitor** (this skill) | — |
| Datastore usage, iSCSI config, vSAN health | **vmware-storage** | `uv tool install vmware-storage` |
| Power on/off, create/delete VM, deploy OVA | **vmware-aiops** | `uv tool install vmware-aiops` |
| Run commands inside VM, upload files | **vmware-aiops** | `uv tool install vmware-aiops` |
| Tanzu Namespace, TKC cluster lifecycle | **vmware-vks** | `uv tool install vmware-vks` |

## Quick Install

All install methods fetch from the same source: [github.com/zw008/VMware-Monitor](https://github.com/zw008/VMware-Monitor) (MIT licensed). We recommend reviewing the source code before installing.

```bash
# Via Skills.sh (fetches from GitHub)
npx skills add zw008/VMware-Monitor

# Via ClawHub (fetches from ClawHub registry snapshot of GitHub)
clawhub install vmware-monitor

# Via PyPI (recommended for version pinning)
uv tool install vmware-monitor==1.2.3
```

### Claude Code

```
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

## Usage Mode

Choose the best mode based on your AI tool:

| Platform | Recommended Mode | Why |
|----------|-----------------|-----|
| Claude Code, Cursor | **MCP** | Structured tool calls, no interactive confirmation needed, seamless experience |
| Aider, Codex, Gemini CLI, Continue | **CLI** | Lightweight, low context overhead, universal compatibility |
| Ollama + local models | **CLI** | Minimal context usage, works with any model size |

### Calling Priority

- **MCP-native tools** (Claude Code, Cursor): MCP first, CLI fallback
- **All other tools**: CLI first (MCP not needed)

> **Tip**: If your AI tool supports MCP, check whether `vmware-monitor` MCP server is loaded (`/mcp` in Claude Code). If not, configure it first — MCP provides the best hands-free experience.

### CLI Examples

```bash
# Activate venv first
source /path/to/VMware-Monitor/.venv/bin/activate

# Inventory
vmware-monitor inventory vms --target home-esxi
vmware-monitor inventory hosts --target home-esxi

# Health
vmware-monitor health alarms --target home-esxi
vmware-monitor health events --hours 24 --severity warning --target home-esxi

# VM info (read-only)
vmware-monitor vm info my-vm --target home-esxi
```

### MCP Mode (Optional)

For Claude Code / Cursor users who prefer structured tool calls, add to `~/.claude/settings.json`:

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

MCP exposes 7 read-only tools: `list_virtual_machines`, `list_esxi_hosts`, `list_all_datastores`, `list_all_clusters`, `get_alarms`, `get_events`, `vm_info`. All accept optional `target` parameter.

`list_virtual_machines` supports `limit`, `sort_by`, `power_state`, `fields` for compact context in large inventories.

## Architecture

```
User (Natural Language)
  ↓
AI Tool (Claude Code / Aider / Gemini / Codex / Cursor / Trae / Kimi)
  ↓
  ├─ CLI mode (default): vmware-monitor CLI ──→ pyVmomi ──→ vSphere API
  │
  └─ MCP mode (optional): MCP Server (stdio) ──→ pyVmomi ──→ vSphere API
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

### MCP Server — Local Agent Compatibility

The MCP server works with any MCP-compatible agent via stdio transport. All 8 tools are **read-only**. Config templates in `examples/mcp-configs/`:

| Agent | Local Models | Config Template |
|-------|:----------:|-----------------|
| Goose (Block) | ✅ Ollama, LM Studio | `goose.json` |
| LocalCowork (Liquid AI) | ✅ Fully offline | `localcowork.json` |
| mcp-agent (LastMile AI) | ✅ Ollama, vLLM | `mcp-agent.yaml` |
| VS Code Copilot | — | `vscode-copilot.json` |
| Cursor | — | `cursor.json` |
| Continue | ✅ Ollama | `continue.yaml` |
| Claude Code | — | `claude-code.json` |

```bash
# Example: Aider + Ollama (fully local, no cloud API)
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

## CLI Reference

```bash
# Diagnostics
vmware-monitor doctor [--skip-auth]

# MCP Config Generator
vmware-monitor mcp-config generate --agent <goose|cursor|claude-code|continue|vscode-copilot|localcowork|mcp-agent>
vmware-monitor mcp-config list

# Inventory
vmware-monitor inventory vms [--target <name>] [--limit <n>] [--sort-by name|cpu|memory_mb|power_state] [--power-state poweredOn|poweredOff]
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
# 1. Install from PyPI (source: github.com/zw008/VMware-Monitor)
uv tool install vmware-monitor

# 2. Verify installation source
vmware-monitor --version  # confirms installed version

# 3. Configure
mkdir -p ~/.vmware-monitor
vmware-monitor init  # generates config.yaml and .env templates
chmod 600 ~/.vmware-monitor/.env
# Edit ~/.vmware-monitor/config.yaml and .env with your target details
```

### What Gets Installed

The `vmware-monitor` package installs a read-only Python CLI binary and its dependencies (pyVmomi, Click, Rich, APScheduler, python-dotenv). No background services, daemons, or system-level changes are made during installation. The scheduled scanner (`daemon start`) only runs when explicitly started by the user.

### Development Install

```bash
git clone https://github.com/zw008/VMware-Monitor.git
cd VMware-Monitor
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Security

- **Read-Only by Design**: This is an independent repository with zero destructive code paths. No power off, delete, create, reconfigure, or migrate functions exist in the codebase.
- **Source Code**: Fully open source at [github.com/zw008/VMware-Monitor](https://github.com/zw008/VMware-Monitor) (MIT). The `uv` installer fetches the `vmware-monitor` package from PyPI, which is built from this GitHub repository. We recommend reviewing the source code and commit history before deploying in production.
- **TLS Verification**: Enabled by default. The `disableSslCertValidation` option exists solely for ESXi hosts using self-signed certificates in isolated lab/home environments. In production, always use CA-signed certificates with full TLS verification.
- **Credentials & Config**: This skill requires the following secrets, all stored in `~/.vmware-monitor/.env` (`chmod 600`, loaded via `python-dotenv`):
  - `VSPHERE_USER` — vCenter/ESXi service account username (read-only account recommended)
  - `VSPHERE_PASSWORD` — service account password
  - (Optional) Webhook URLs for Slack/Discord notifications

  The config file `~/.vmware-monitor/config.yaml` stores only target hostnames, ports, and a reference to the `.env` file — it does **not** contain passwords or tokens. The env var `VMWARE_MONITOR_CONFIG` points to this YAML file.
- **Webhook Data Scope**: Webhook notifications are **disabled by default**. When enabled, they send monitoring summaries (alarm counts, event types, host status) to **user-configured URLs only** (Slack, Discord, or any HTTP endpoint you control). No data is sent to third-party services. Webhook payloads contain no credentials, IPs, or personally identifiable information — only aggregated alert metadata.
- **Prompt Injection Protection**: All vSphere-sourced content (event messages, host logs) is truncated, stripped of control characters, and wrapped in boundary markers (`[VSPHERE_EVENT]`/`[VSPHERE_HOST_LOG]`) before output to prevent prompt injection when consumed by LLM agents.

## License

MIT
