# VMware Monitor

English | [中文](README-CN.md)

**Read-only** VMware vCenter/ESXi monitoring tool. Code-level enforced safety — no destructive operations exist in this codebase.

> **Why a separate repository?** VMware Monitor is fully independent from [VMware-AIops](https://github.com/zw008/VMware-AIops). Safety is enforced at the **code level**: no power off, delete, create, reconfigure, snapshot-create/revert/delete, clone, or migrate functions exist in this codebase. Not just prompt constraints — zero destructive code paths.

[![Skills.sh](https://img.shields.io/badge/Skills.sh-Install-blue)](https://skills.sh/zw008/VMware-Monitor)
[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-Monitor)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### Quick Install (Recommended)

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, and 30+ AI agents:

```bash
npx skills add zw008/VMware-Monitor
```

### Claude Code

```bash
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

---

## Capabilities (Read-Only)

### Architecture

```
User (Natural Language)
  ↓
AI CLI Tool (Claude Code / Gemini / Codex / Aider / Continue / Trae / Kimi)
  ↓ Reads SKILL.md / AGENTS.md / rules
  ↓
vmware-monitor CLI (read-only)
  ↓ pyVmomi (vSphere SOAP API)
  ↓
vCenter Server ──→ ESXi Clusters ──→ VMs
    or
ESXi Standalone ──→ VMs
```

### Version Compatibility

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | ✅ Full | pyVmomi 8.0.3+ |
| 7.0 / 7.0U1-U3 | ✅ Full | All read-only APIs supported |
| 6.7 | ✅ Compatible | Backward-compatible, tested |
| 6.5 | ✅ Compatible | Backward-compatible, tested |

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
| Structured Log | JSONL output to `~/.vmware-monitor/scan.log` |
| Webhook | Slack, Discord, or any HTTP endpoint |
| Daemon Management | `daemon start/stop/status`, PID file, graceful shutdown |

### 5. Safety Features

| Feature | Details |
|---------|---------|
| **Code-Level Isolation** | Independent repository — zero destructive functions in codebase |
| **Audit Trail** | All queries logged to `~/.vmware-monitor/audit.log` (JSONL) |
| **Password Protection** | `.env` file loading with permission check (warn if not 600) |
| **SSL Self-signed Support** | `disableSslCertValidation` for ESXi 8.0 self-signed certs |

### What's NOT Included (By Design)

These operations **do not exist** in this repository:

- ❌ Power on/off, reset, suspend VMs
- ❌ Create, delete, reconfigure VMs
- ❌ Create, revert, delete snapshots
- ❌ Clone or migrate VMs
- ❌ `_double_confirm`, `_show_state_preview`, `_validate_vm_params`

For these operations, use the full [VMware-AIops](https://github.com/zw008/VMware-AIops) repository.

---

## Supported AI Platforms

| Platform | Status | Config File | AI Model |
|----------|--------|-------------|----------|
| **Claude Code** | ✅ Native Skill | `skill/SKILL.md` | Anthropic Claude |
| **Gemini CLI** | ✅ AGENTS.md | `codex-skill/AGENTS.md` | Google Gemini |
| **OpenAI Codex CLI** | ✅ AGENTS.md | `codex-skill/AGENTS.md` | OpenAI GPT |
| **Aider** | ✅ Conventions | `codex-skill/AGENTS.md` | Any (cloud + local) |
| **Continue CLI** | ✅ Rules | `codex-skill/AGENTS.md` | Any (cloud + local) |
| **Trae IDE** | ✅ Rules | `codex-skill/AGENTS.md` | Claude/DeepSeek/GPT-4o |
| **Kimi Code CLI** | ✅ Skill | `codex-skill/AGENTS.md` | Moonshot Kimi |
| **MCP Server** | ✅ MCP Protocol | `mcp_server/` | Any MCP client |
| **Python CLI** | ✅ Standalone | N/A | N/A |

---

## Installation

### Step 1: Clone & Install

```bash
git clone https://github.com/zw008/VMware-Monitor.git
cd VMware-Monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 2: Configure

```bash
mkdir -p ~/.vmware-monitor
cp config.example.yaml ~/.vmware-monitor/config.yaml
# Edit config.yaml with your vCenter/ESXi targets
```

Set passwords via `.env` file (recommended):
```bash
cp .env.example ~/.vmware-monitor/.env
chmod 600 ~/.vmware-monitor/.env
# Edit and fill in your passwords
```

> **Security note**: Prefer `.env` file over command-line `export` to avoid passwords appearing in shell history.

Password environment variable naming convention:
```
VMWARE_{TARGET_NAME_UPPER}_PASSWORD
# Replace hyphens with underscores, UPPERCASE
# Example: target "home-esxi" → VMWARE_HOME_ESXI_PASSWORD
```

### Step 3: Connect Your AI Tool

#### Claude Code (Recommended)

```bash
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

#### Codex / Aider / Continue / Trae / Kimi

```bash
# Copy AGENTS.md to your project
cp codex-skill/AGENTS.md ./AGENTS.md

# Aider
aider --conventions codex-skill/AGENTS.md

# Local model
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

#### MCP Server

```bash
python -m mcp_server
# Or: vmware-monitor-mcp
# Or: VMWARE_MONITOR_CONFIG=/path/to/config.yaml python -m mcp_server
```

**Claude Desktop** (`claude_desktop_config.json`):
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

**Smithery**:
```bash
npx -y @smithery/cli install @zw008/VMware-Monitor --client claude
```

#### Standalone CLI (no AI)

```bash
source .venv/bin/activate
vmware-monitor inventory vms --target home-esxi
vmware-monitor health alarms --target home-esxi
```

---

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

---

## Configuration

See `config.example.yaml` for all options.

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| targets | name | — | Friendly name |
| targets | host | — | vCenter/ESXi hostname or IP |
| targets | type | vcenter | `vcenter` or `esxi` |
| targets | port | 443 | Connection port |
| targets | verify_ssl | false | SSL certificate verification |
| scanner | interval_minutes | 15 | Scan frequency |
| scanner | severity_threshold | warning | Min severity: critical/warning/info |
| scanner | lookback_hours | 1 | How far back to scan |
| notify | log_file | ~/.vmware-monitor/scan.log | JSONL log output |
| notify | webhook_url | — | Webhook endpoint (Slack, Discord, etc.) |

---

## Project Structure

```
VMware-Monitor/
├── vmware_monitor/                # Python backend (read-only only)
│   ├── config.py                  # YAML + .env config
│   ├── connection.py              # Multi-target pyVmomi
│   ├── cli.py                     # Typer CLI (read-only commands only)
│   ├── ops/
│   │   ├── inventory.py           # VMs, hosts, datastores, clusters
│   │   ├── health.py              # Alarms, events, sensors
│   │   └── vm_info.py             # VM info, snapshot list (read-only)
│   ├── scanner/                   # Log scanning daemon
│   └── notify/                    # Notifications (JSONL + webhook)
├── mcp_server/                    # MCP server (read-only tools only)
│   └── server.py
├── skill/SKILL.md                 # Claude Code skill
├── skills/vmware-monitor/         # Skills.sh index
├── plugins/vmware-monitor/        # Claude Code plugin
├── .claude-plugin/                # Marketplace manifest
├── codex-skill/AGENTS.md          # Codex / Aider / Continue
├── config.example.yaml
└── pyproject.toml
```

## Related Projects

| Repository | Description |
|------------|-------------|
| [VMware-Monitor](https://github.com/zw008/VMware-Monitor) (this repo) | Read-only monitoring — code-level safety |
| [VMware-AIops](https://github.com/zw008/VMware-AIops) | Full operations — monitoring + VM lifecycle |

## Troubleshooting & Contributing

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome!

## License

MIT
