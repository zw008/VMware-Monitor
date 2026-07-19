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
cp config.example.yaml ~/.vmware-monitor/config.yaml
cp .env.example ~/.vmware-monitor/.env
chmod 600 ~/.vmware-monitor/.env
# Edit ~/.vmware-monitor/config.yaml and .env with your target details
```

### Declare `environment:` on each target

```yaml
targets:
  - name: prod-vcenter
    host: vcenter-prod.example.com
    environment: production   # production | staging | lab | <your own label>
```

Policy scopes its rules by environment rather than by the target's name. This
skill has zero write tools, so no monitor command is ever refused or delayed
by this — reads are never gated under any setting. It matters for the write
skills (`vmware-aiops`, `vmware-storage`, `vmware-nsx`) pointed at the same
vCenter: an undeclared target matches no rule, which today logs a warning on
every write and in the next major release refuses it. Keeping the label
consistent across the family's config files is what makes that upgrade a no-op.

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
      "command": "vmware-monitor",
      "args": ["mcp"],
      "env": {
        "VMWARE_MONITOR_CONFIG": "~/.vmware-monitor/config.yaml"
      }
    }
  }
}
```

> v1.5.15+ recommends the single-command form `vmware-monitor mcp`. Pre-1.5.15 used
> `uvx --from vmware-monitor vmware-monitor-mcp`, which still works but re-resolves from
> PyPI on each launch and breaks behind corporate TLS proxies. The legacy
> `vmware-monitor-mcp` entry point is also kept for backward compatibility.

MCP exposes 27 read-only tools:

| Group | Tools |
|---|---|
| Inventory | `list_virtual_machines`, `list_esxi_hosts`, `list_all_datastores`, `list_all_clusters`, `list_all_networks`, `resource_pool_usage` |
| Health & triage | `get_alarms`, `get_events`, `cluster_health_summary`, `cross_vcenter_attention` |
| VM detail | `vm_info`, `vm_list_snapshots`, `vm_performance`, `snapshot_aging` |
| Host detail | `host_performance`, `host_log_scan`, `get_host_sensors`, `get_host_services`, `ntp_status` |
| Platform state | `certificate_status`, `license_status`, `active_sessions`, `active_tasks`, `datastore_capacity` |
| Investigation bundles | `vm_investigation_bundle`, `host_investigation_bundle`, `datastore_investigation_bundle` |

All accept an optional `target` parameter except `cross_vcenter_attention`, which
sweeps every configured target by design.

List-style tools take `limit` (default 50) to keep large inventories from flooding
context; `list_virtual_machines` additionally supports `sort_by`, `power_state`,
`fields`, and `folder_filter`.

### Password obfuscation at rest

On first load, any plaintext `*_PASSWORD` value in `.env` is automatically
rewritten to a grep-safe `b64:<encoded>` form and decoded transparently at
runtime, so a casual `grep` of the file no longer reveals the password. Values
are read and written through python-dotenv's own parser, so the stored secret
never drifts from what you configured (quotes, inline comments, and trailing
whitespace are handled correctly).

> **This is obfuscation, not encryption.** Anyone who can read the file can
> still decode it. For real secrecy at rest, do not store the password in `.env`
> at all — inject it from a secret manager (HashiCorp Vault, CyberArk, AWS
> Secrets Manager, or a Kubernetes Secret) into the `*_PASSWORD` environment
> variable at process start. The code reads the env var either way.

## Security

> **Disclaimer**: This is a community-maintained open-source project and is **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom Inc.** "VMware" and "vSphere" are trademarks of Broadcom.

- **Read-Only by Design**: This is an independent repository with zero destructive code paths. No power off, delete, create, reconfigure, or migrate functions exist in the codebase.
- **Source Code**: Fully open source at [github.com/zw008/VMware-Monitor](https://github.com/zw008/VMware-Monitor) (MIT). The `uv` installer fetches the `vmware-monitor` package from PyPI, which is built from this GitHub repository. We recommend reviewing the source code and commit history before deploying in production.
- **TLS Verification**: Enabled by default. The `disableSslCertValidation` option exists solely for ESXi hosts using self-signed certificates in isolated lab/home environments. In production, always use CA-signed certificates with full TLS verification.
- **Credentials & Config**: This skill requires the following secrets, all stored in `~/.vmware-monitor/.env` (`chmod 600`, loaded via `python-dotenv`):
  - `VMWARE_<TARGET>_PASSWORD` — per-target password where `<TARGET>` is the uppercased target name from `config.yaml` (hyphens become underscores). Example: target named `vcenter-prod` uses `VMWARE_VCENTER_PROD_PASSWORD`.
  - (Optional) Webhook URLs for Slack/Discord notifications

  The config file `~/.vmware-monitor/config.yaml` stores only target hostnames, ports, and usernames — it does **not** contain passwords or tokens. The env var `VMWARE_MONITOR_CONFIG` points to this YAML file.
- **Webhook Data Scope**: Webhook notifications are **disabled by default**. When enabled, they send monitoring summaries (alarm counts, event types, host status) to **user-configured URLs only** (Slack, Discord, or any HTTP endpoint you control). No data is sent to third-party services. Webhook payloads contain no credentials, IPs, or personally identifiable information — only aggregated alert metadata.
- **Prompt Injection Protection**: All vSphere-sourced content (event messages, host logs) is truncated, stripped of control characters, and wrapped in boundary markers (`[VSPHERE_EVENT]`/`[VSPHERE_HOST_LOG]`) before output to prevent prompt injection when consumed by LLM agents.

### Read-only mode

All 27 tools in this skill are reads, so the family read-only gate has nothing to remove here. It is wired up anyway, for two reasons: the interface is identical across the family, and it turns "zero write tools" from a claim in this document into something checked at start-up. **Off by default.**

Three ways to enable it, highest precedence first:

| Precedence | Setting | Scope |
|:-:|---|---|
| 1 | `VMWARE_MONITOR_READ_ONLY=true` | This skill only |
| 2 | `VMWARE_READ_ONLY=true` | **Every installed VMware skill** — one setting puts the whole estate in audit posture |
| 3 | `read_only: true` in `~/.vmware-monitor/config.yaml` | This skill only |
| 4 | *(unset)* | Off |

The env vars come first so a deployment can be locked down from the MCP client's `env` block without editing any config file. Setting it here changes nothing observable about this skill — its value is that the *same* variable withholds the write tools of vmware-aiops, vmware-storage, vmware-vks and the rest, so an estate-wide audit posture is one setting rather than one per skill.

**Fail-closed.** If read-only mode is requested but cannot be *proven* — the tool registry cannot be enumerated, or a removal does not take effect — the server refuses to start. One case does *not* abort: an unrecognised value (`VMWARE_READ_ONLY=ture`) resolves to **on** with a warning, so a typo locks a deployment down instead of leaving it open.

**Verifying it took**:

```bash
vmware-monitor doctor      # reports ON/off, and which of the four sources decided it
```

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

The MCP server works with any MCP-compatible agent via stdio transport. All 27 tools are **read-only**. Config templates in `examples/mcp-configs/`:

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
