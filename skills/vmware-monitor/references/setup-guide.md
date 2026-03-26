# Setup Guide

## Install

All install methods fetch from the same source: [github.com/zw008/VMware-Monitor](https://github.com/zw008/VMware-Monitor) (MIT licensed). We recommend reviewing the source code before installing.

```bash
# Via PyPI (recommended for version pinning)
uv tool install vmware-monitor

# Via Skills.sh (fetches from GitHub)
npx skills add zw008/VMware-Monitor

# Via ClawHub (fetches from ClawHub registry snapshot of GitHub)
clawhub install vmware-monitor
```

### Claude Code

```
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

## What Gets Installed

The `vmware-monitor` package installs a read-only Python CLI binary and its dependencies (pyVmomi, Click, Rich, APScheduler, python-dotenv). No background services, daemons, or system-level changes are made during installation. The scheduled scanner (`daemon start`) only runs when explicitly started by the user.

## Configuration

```bash
# 1. Install
uv tool install vmware-monitor

# 2. Verify
vmware-monitor --version

# 3. Configure
mkdir -p ~/.vmware-monitor
vmware-monitor init  # generates config.yaml and .env templates
chmod 600 ~/.vmware-monitor/.env
# Edit ~/.vmware-monitor/config.yaml and .env with your target details
```

## Development Install

```bash
git clone https://github.com/zw008/VMware-Monitor.git
cd VMware-Monitor
uv venv && source .venv/bin/activate
uv pip install -e .
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

## MCP Mode Configuration

For Claude Code / Cursor users who prefer structured tool calls, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vmware-monitor": {
      "command": "uvx",
      "args": ["--from", "vmware-monitor", "vmware-monitor-mcp"],
      "env": {
        "VMWARE_MONITOR_CONFIG": "~/.vmware-monitor/config.yaml"
      }
    }
  }
}
```

MCP exposes 7 read-only tools: `list_virtual_machines`, `list_esxi_hosts`, `list_all_datastores`, `list_all_clusters`, `get_alarms`, `get_events`, `vm_info`. All accept optional `target` parameter.

`list_virtual_machines` supports `limit`, `sort_by`, `power_state`, `fields` for compact context in large inventories.

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

## Supported AI Platforms

| Platform | Status | Config File |
|----------|--------|-------------|
| Claude Code | Native Skill | `plugins/.../SKILL.md` |
| Gemini CLI | Extension | `gemini-extension/GEMINI.md` |
| OpenAI Codex CLI | Skill + AGENTS.md | `codex-skill/AGENTS.md` |
| Aider | Conventions | `codex-skill/AGENTS.md` |
| Continue CLI | Rules | `codex-skill/AGENTS.md` |
| Trae IDE | Rules | `trae-rules/project_rules.md` |
| Kimi Code CLI | Skill | `kimi-skill/SKILL.md` |
| MCP Server | MCP Protocol | `mcp_server/` |
| Python CLI | Standalone | N/A |

### MCP Server — Local Agent Compatibility

The MCP server works with any MCP-compatible agent via stdio transport. All 8 tools are **read-only**. Config templates in `examples/mcp-configs/`:

| Agent | Local Models | Config Template |
|-------|:----------:|-----------------|
| Goose (Block) | Ollama, LM Studio | `goose.json` |
| LocalCowork (Liquid AI) | Fully offline | `localcowork.json` |
| mcp-agent (LastMile AI) | Ollama, vLLM | `mcp-agent.yaml` |
| VS Code Copilot | — | `vscode-copilot.json` |
| Cursor | — | `cursor.json` |
| Continue | Ollama | `continue.yaml` |
| Claude Code | — | `claude-code.json` |

```bash
# Example: Aider + Ollama (fully local, no cloud API)
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

## First Interaction: Environment Selection

When the user starts a conversation, **always ask first**:

1. **Which environment** do they want to monitor? (vCenter Server or standalone ESXi host)
2. **Which target** from their config? (e.g., `prod-vcenter`, `lab-esxi`)
3. If no config exists yet, guide them through creating `~/.vmware-monitor/config.yaml`
