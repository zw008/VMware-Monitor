<!-- mcp-name: io.github.zw008/vmware-monitor -->
# VMware Monitor

English | [中文](README-CN.md)

**Read-only** VMware vCenter/ESXi monitoring — 8 tools, code-level safety. No destructive operations exist in this codebase.

> **Why a separate repository?** VMware Monitor is fully independent from [VMware-AIops](https://github.com/zw008/VMware-AIops). Safety is enforced at the **code level**: no power off, delete, create, reconfigure, snapshot-create/revert/delete, clone, or migrate functions exist in this codebase. Not just prompt constraints — zero destructive code paths.

[![ClawHub](https://img.shields.io/badge/ClawHub-vmware--monitor-orange)](https://clawhub.ai/skills/vmware-monitor)
[![Skills.sh](https://img.shields.io/badge/Skills.sh-Install-blue)](https://skills.sh/zw008/VMware-Monitor)
[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-Monitor)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### Companion Skills

| Skill | Scope | Tools | Install |
|-------|-------|:-----:|---------|
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** | VM lifecycle, deployment, guest ops, clusters | 33 | `uv tool install vmware-aiops` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-vks](https://github.com/zw008/VMware-VKS)** | Tanzu Namespaces, TKC cluster lifecycle | 20 | `uv tool install vmware-vks` |

### Quick Install (Recommended)

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, and 30+ AI agents:

```bash
# Via Skills.sh
npx skills add zw008/VMware-Monitor

# Via ClawHub
clawhub install vmware-monitor
```

### PyPI Install (No GitHub Access Required)

```bash
# Install via uv (recommended)
uv tool install vmware-monitor

# Or via pip
pip install vmware-monitor

# China mainland mirror (faster)
pip install vmware-monitor -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Claude Code Plugin Install

```bash
# Add marketplace
/plugin marketplace add zw008/VMware-Monitor

# Install plugin
/plugin install vmware-monitor

# Use the skill
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
| **SSL Self-signed Support** | `disableSslCertValidation` — only for ESXi with self-signed certs in isolated labs; production should use CA-signed certificates |
| **Prompt Injection Protection** | vSphere event messages and host logs are truncated, sanitized, and wrapped in boundary markers |
| **Webhook Data Scope** | Sends monitoring summaries to user-configured URLs only — no third-party services by default |
| **Production Recommended** | AI agents can misinterpret context and execute unintended destructive operations — real-world incidents have shown AI-driven tools deleting production databases and entire environments. VMware-Monitor eliminates this risk: no destructive code paths exist. Use [VMware-AIops](https://github.com/zw008/VMware-AIops) only in dev/lab environments |

### What's NOT Included (By Design)

These operations **do not exist** in this repository:

- ❌ Power on/off, reset, suspend VMs
- ❌ Create, delete, reconfigure VMs
- ❌ Create, revert, delete snapshots
- ❌ Clone or migrate VMs
- ❌ `_double_confirm`, `_show_state_preview`, `_validate_vm_params`

For these operations, use the full [VMware-AIops](https://github.com/zw008/VMware-AIops) repository.

---

## Common Workflows

### Daily Health Check

1. Check alarms: `vmware-monitor health alarms --target prod-vcenter`
2. Review recent events: `vmware-monitor health events --hours 24 --severity warning`
3. List hosts: `vmware-monitor inventory hosts` — check connection state and memory usage

### Investigate a Specific VM

1. Find the VM: `vmware-monitor inventory vms --power-state poweredOff`
2. Get details: `vmware-monitor vm info problem-vm`
3. Check related events: `vmware-monitor health events --hours 48`

### Set Up Continuous Monitoring

1. Configure webhook in `~/.vmware-monitor/config.yaml`
2. Start daemon: `vmware-monitor daemon start`
3. Daemon scans every 15 min, sends alerts to Slack/Discord

---

## Troubleshooting

### Alarms returns empty but vCenter shows alarms

The `get_alarms` tool queries triggered alarms at the root folder level. Some alarms are entity-specific — try checking events instead: `vmware-monitor health events --hours 1 --severity info`.

### "Connection refused" error

1. Run `vmware-monitor doctor` to diagnose
2. Verify target hostname/IP and port (443) in `config.yaml`
3. For self-signed certs: set `disableSslCertValidation: true`

### Events returns too many results

Use severity filter: `--severity warning` (default) filters out info-level events. Use `--hours 4` to narrow the time range.

### VM info shows "guest_os: unknown"

VMware Tools not installed or not running in the guest. Install/start VMware Tools for guest OS detection, IP address, and guest family info.

### Doctor passes but commands fail with timeout

vCenter may be under heavy load. Try targeting a specific ESXi host directly instead of vCenter, or increase connection timeout in `config.yaml`.

---

## Supported AI Platforms

| Platform | Status | Config File | AI Model |
|----------|--------|-------------|----------|
| **Claude Code** | ✅ Native Skill | `skills/vmware-monitor/SKILL.md` | Anthropic Claude |
| **Gemini CLI** | ✅ Extension | `gemini-extension/GEMINI.md` | Google Gemini |
| **OpenAI Codex CLI** | ✅ Skill + AGENTS.md | `codex-skill/AGENTS.md` | OpenAI GPT |
| **Aider** | ✅ Conventions | `codex-skill/AGENTS.md` | Any (cloud + local) |
| **Continue CLI** | ✅ Rules | `codex-skill/AGENTS.md` | Any (cloud + local) |
| **Trae IDE** | ✅ Rules | `trae-rules/project_rules.md` | Claude/DeepSeek/GPT-4o |
| **Kimi Code CLI** | ✅ Skill | `kimi-skill/SKILL.md` | Moonshot Kimi |
| **MCP Server** | ✅ MCP Protocol | `mcp_server/` | Any MCP client |
| **Python CLI** | ✅ Standalone | N/A | N/A |

### Platform Comparison

| Feature | Claude Code | Gemini CLI | Codex CLI | Aider | Continue | Trae IDE | Kimi CLI |
|---------|-------------|------------|-----------|-------|----------|----------|----------|
| Cloud AI | Anthropic | Google | OpenAI | Any | Any | Multi | Moonshot |
| Local models | — | — | — | Ollama | Ollama | — | — |
| Skill system | SKILL.md | Extension | SKILL.md | — | Rules | Rules | SKILL.md |
| MCP support | Native | Native | Via Skills | Third-party | Native | — | — |
| Free tier | — | 60 req/min | — | Self-hosted | Self-hosted | — | — |

### MCP Server Integrations

The vmware-monitor MCP server works with **any MCP-compatible agent or tool**. Ready-to-use configuration templates are in [`examples/mcp-configs/`](examples/mcp-configs/). All 8 tools are **read-only** — code-level enforced safety.

| Agent / Tool | Local Model Support | Config Template | Integration Guide |
|-------------|:-------------------:|-----------------|-------------------|
| **[Goose](https://github.com/block/goose)** | ✅ Ollama, LM Studio | [`goose.json`](examples/mcp-configs/goose.json) | [Guide](docs/integrations/goose.md) |
| **[LocalCowork](https://github.com/Liquid4All/localcowork)** | ✅ Fully offline | [`localcowork.json`](examples/mcp-configs/localcowork.json) | [Guide](docs/integrations/localcowork.md) |
| **[mcp-agent](https://github.com/lastmile-ai/mcp-agent)** | ✅ Ollama, vLLM | [`mcp-agent.yaml`](examples/mcp-configs/mcp-agent.yaml) | [Guide](docs/integrations/mcp-agent.md) |
| **VS Code Copilot** | — | [`vscode-copilot.json`](examples/mcp-configs/vscode-copilot.json) | [Guide](docs/integrations/vscode-copilot.md) |
| **Cursor** | — | [`cursor.json`](examples/mcp-configs/cursor.json) | — |
| **Continue** | ✅ Ollama | [`continue.yaml`](examples/mcp-configs/continue.yaml) | [Guide](docs/integrations/continue.md) |
| **Claude Code** | — | [`claude-code.json`](examples/mcp-configs/claude-code.json) | — |

**Fully local operation** (no cloud API required):

```bash
# Aider + Ollama + vmware-monitor (via AGENTS.md)
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b

# Any MCP agent + local model + vmware-monitor MCP server
# See examples/mcp-configs/ for your agent's config format
```

---

## Installation

### Step 0: Prerequisites

```bash
# Python 3.10+ required
python3 --version

# Node.js 18+ required for Gemini CLI and Codex CLI
node --version
```

### Step 1: Clone & Install Python Backend

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

> **Security note**: Prefer `.env` file over command-line `export` to avoid passwords appearing in shell history. `config.yaml` stores only hostnames, ports, and a reference to the `.env` file — it does **not** contain passwords or tokens. All secrets are stored exclusively in `.env` (`chmod 600`). Webhook notifications are disabled by default; when enabled, payloads contain no credentials, IPs, or PII — only aggregated alert metadata sent to user-configured URLs only. We recommend using a least-privilege read-only vCenter service account.

Password environment variable naming convention:
```
VMWARE_{TARGET_NAME_UPPER}_PASSWORD
# Replace hyphens with underscores, UPPERCASE
# Example: target "home-esxi" → VMWARE_HOME_ESXI_PASSWORD
# Example: target "prod-vcenter" → VMWARE_PROD_VCENTER_PASSWORD
```

### Step 3: Connect Your AI Tool

Choose one (or more) of the following:

---

#### Option A: Claude Code (Marketplace)

**Method 1: Marketplace (recommended)**

In Claude Code, run:
```
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
```

Then use:
```
/vmware-monitor:vmware-monitor
> Show me all VMs on esxi-lab.example.com
```

**Method 2: Local install**

```bash
# Clone and symlink
git clone https://github.com/zw008/VMware-Monitor.git
ln -sf $(pwd)/VMware-Monitor ~/.claude/plugins/marketplaces/vmware-monitor

# Register marketplace
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/plugins/known_marketplaces.json'
d = json.loads(f.read_text()) if f.exists() else {}
d['vmware-monitor'] = {
    'source': {'source': 'github', 'repo': 'zw008/VMware-Monitor'},
    'installLocation': str(pathlib.Path.home() / '.claude/plugins/marketplaces/vmware-monitor')
}
f.write_text(json.dumps(d, indent=2))
"

# Enable plugin
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/settings.json'
d = json.loads(f.read_text()) if f.exists() else {}
d.setdefault('enabledPlugins', {})['vmware-monitor@vmware-monitor'] = True
f.write_text(json.dumps(d, indent=2))
"
```

Restart Claude Code, then:
```
/vmware-monitor:vmware-monitor
```

---

#### Option B: Gemini CLI

```bash
# Install Gemini CLI
npm install -g @google/gemini-cli

# Install the extension from the cloned repo
gemini extensions install ./gemini-extension

# Or install directly from GitHub
# gemini extensions install https://github.com/zw008/VMware-Monitor
```

Then start Gemini CLI:
```
gemini
> Show me all VMs on my ESXi host
```

---

#### Option C: OpenAI Codex CLI

```bash
# Install Codex CLI
npm i -g @openai/codex
# Or on macOS:
# brew install --cask codex

# Copy skill to Codex skills directory
mkdir -p ~/.codex/skills/vmware-monitor
cp codex-skill/SKILL.md ~/.codex/skills/vmware-monitor/SKILL.md

# Copy AGENTS.md to project root
cp codex-skill/AGENTS.md ./AGENTS.md
```

Then start Codex CLI:
```bash
codex --enable skills
> List all VMs on my ESXi
```

---

#### Option D: Aider (supports local models)

```bash
# Install Aider
pip install aider-chat

# Install Ollama for local models (optional)
# macOS:
brew install ollama
ollama pull qwen2.5-coder:32b

# Run with cloud API
aider --conventions codex-skill/AGENTS.md

# Or with local model via Ollama
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:32b
```

---

#### Option E: Continue CLI (supports local models)

```bash
# Install Continue CLI
npm i -g @continuedev/cli

# Copy rules file
mkdir -p .continue/rules
cp codex-skill/AGENTS.md .continue/rules/vmware-monitor.md
```

Configure `~/.continue/config.yaml` for local model:
```yaml
models:
  - name: local-coder
    provider: ollama
    model: qwen2.5-coder:32b
```

Then:
```bash
cn
> Check ESXi health and alarms
```

---

#### Option F: Trae IDE

Copy the rules file to your project's `.trae/rules/` directory:

```bash
mkdir -p .trae/rules
cp trae-rules/project_rules.md .trae/rules/project_rules.md
```

Trae IDE's Builder Mode reads `.trae/rules/` Markdown files at startup.

> **Note**: You can also install Claude Code extension in Trae IDE and use `.claude/skills/` format directly.

---

#### Option G: Kimi Code CLI

```bash
# Copy skill file to Kimi skills directory
mkdir -p ~/.kimi/skills/vmware-monitor
cp kimi-skill/SKILL.md ~/.kimi/skills/vmware-monitor/SKILL.md
```

---

#### Option H: MCP Server (Smithery / Glama / Claude Desktop)

The MCP server exposes VMware read-only monitoring as tools via the [Model Context Protocol](https://modelcontextprotocol.io). Works with any MCP-compatible client (Claude Desktop, Cursor, etc.).

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

**Install via Smithery**:
```bash
npx -y @smithery/cli install @zw008/VMware-Monitor --client claude
```

---

#### Option I: Standalone CLI (no AI)

```bash
# Already installed in Step 1
source .venv/bin/activate

vmware-monitor inventory vms --target home-esxi
vmware-monitor health alarms --target home-esxi
vmware-monitor vm info my-vm --target home-esxi
```

---

## Update / Upgrade

Already installed? Re-run the install command for your channel to get the latest version:

| Install Channel | Update Command |
|----------------|----------------|
| ClawHub | `clawhub install vmware-monitor` |
| Skills.sh | `npx skills add zw008/VMware-Monitor` |
| Claude Code Plugin | `/plugin marketplace add zw008/VMware-Monitor` |
| Git clone | `cd VMware-Monitor && git pull origin main && uv pip install -e .` |
| uv | `uv tool install vmware-monitor --force` |

Check your current version: `vmware-monitor --version`

---

## Chinese Cloud Models

For users in China who prefer domestic cloud APIs or have limited access to overseas services.

### DeepSeek

```bash
export DEEPSEEK_API_KEY="your-key"
aider --conventions codex-skill/AGENTS.md \
  --model deepseek/deepseek-coder
```

### Qwen (Alibaba Cloud)

```bash
export DASHSCOPE_API_KEY="your-key"
aider --conventions codex-skill/AGENTS.md \
  --model qwen/qwen-coder-plus
```

### Local Models (Aider + Ollama)

For fully offline operation — no cloud API, no internet, full privacy.

```bash
brew install ollama
ollama pull qwen2.5-coder:32b
ollama serve

aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:32b
```

---

## CLI Reference

```bash
# Diagnostics
vmware-monitor doctor                   # Check environment, config, connectivity
vmware-monitor doctor --skip-auth       # Skip vSphere auth check (faster)

# MCP Config Generator
vmware-monitor mcp-config generate --agent goose        # Generate config for Goose
vmware-monitor mcp-config generate --agent claude-code  # Generate config for Claude Code
vmware-monitor mcp-config list                          # List all supported agents

# Inventory
vmware-monitor inventory vms [--target <name>]
vmware-monitor inventory vms --limit 10 --sort-by memory_mb   # Top 10 VMs by memory
vmware-monitor inventory vms --power-state poweredOn           # Only powered-on VMs
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
├── .claude-plugin/                # Claude Code marketplace manifest
│   └── marketplace.json
├── plugins/                       # Claude Code plugin
│   └── vmware-monitor/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           └── vmware-monitor/
│               └── SKILL.md       # Read-only monitoring skill
├── skills/                        # Skills index (npx skills add)
│   └── vmware-monitor/
│       └── SKILL.md
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
├── gemini-extension/              # Gemini CLI extension
│   ├── gemini-extension.json
│   └── GEMINI.md
├── codex-skill/                   # Codex + Aider + Continue
│   ├── SKILL.md
│   └── AGENTS.md
├── trae-rules/                    # Trae IDE rules
│   └── project_rules.md
├── kimi-skill/                    # Kimi Code CLI skill
│   └── SKILL.md
├── mcp_server/                    # MCP server (read-only tools only)
│   └── server.py
├── .agents/skills/                # Agent orchestration
│   └── vmware-monitor/
│       └── AGENTS.md
├── smithery.yaml                  # Smithery marketplace config
├── RELEASE_NOTES.md
├── config.example.yaml
└── pyproject.toml
```

## Related Projects

| Skill | Scope | Tools | Install |
|-------|-------|:-----:|---------|
| **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** | Read-only monitoring, alarms, events | 8 | `uv tool install vmware-monitor` |
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** | VM lifecycle, deployment, guest ops, clusters | 33 | `uv tool install vmware-aiops` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-vks](https://github.com/zw008/VMware-VKS)** | Tanzu Namespaces, TKC cluster lifecycle | 20 | `uv tool install vmware-vks` |

---

## Troubleshooting & Contributing

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome!

## License

MIT
