# CLI Reference

Full command reference for `vmware-monitor`.

## Diagnostics

```bash
vmware-monitor doctor [--skip-auth]
```

Checks config file, connectivity, authentication, and pyVmomi version. Use `--skip-auth` to test config parsing without connecting.

## MCP Config Generator

```bash
vmware-monitor mcp-config generate --agent <goose|cursor|claude-code|continue|vscode-copilot|localcowork|mcp-agent>
vmware-monitor mcp-config list
```

Generates MCP configuration files for supported agents. `list` shows all available agent templates.

## Inventory

```bash
vmware-monitor inventory vms [--target <name>] [--limit <n>] [--sort-by name|cpu|memory_mb|power_state] [--power-state poweredOn|poweredOff]
vmware-monitor inventory hosts [--target <name>]
vmware-monitor inventory datastores [--target <name>]
vmware-monitor inventory clusters [--target <name>]
```

- `--target`: Named target from `config.yaml` (default: first target)
- `--limit`: Max VMs to return (default: unlimited)
- `--sort-by`: Sort field for VM listing
- `--power-state`: Filter VMs by power state

## Health

```bash
vmware-monitor health alarms [--target <name>]
vmware-monitor health events [--hours 24] [--severity warning] [--target <name>]
```

- `--hours`: Time range for event query (default: 24)
- `--severity`: Minimum severity filter — `info`, `warning`, `error`, `critical` (default: `warning`)

## VM Info (Read-Only)

```bash
vmware-monitor vm info <vm-name> [--target <name>]
vmware-monitor vm snapshot-list <vm-name> [--target <name>]
```

Returns detailed VM information: CPU, memory, disks, NICs, guest OS, IP, VMware Tools status, and snapshots.

`snapshot-list` lists existing snapshots with name and creation time. No create, revert, or delete operations exist.

## Scanning & Daemon

```bash
vmware-monitor scan now [--target <name>]
vmware-monitor daemon start
vmware-monitor daemon stop
vmware-monitor daemon status
```

- `scan now`: Run a one-time scan of alarms, events, and host logs
- `daemon start`: Start APScheduler-based background scanner (default: every 15 min)
- `daemon stop`: Stop the background scanner
- `daemon status`: Check if the daemon is running

## Init

```bash
vmware-monitor init
```

Generates `config.yaml` and `.env` templates in `~/.vmware-monitor/`.

## Architecture

```
User (Natural Language)
  |
AI Tool (Claude Code / Aider / Gemini / Codex / Cursor / Trae / Kimi)
  |
  +-- CLI mode (default): vmware-monitor CLI --> pyVmomi --> vSphere API
  |
  +-- MCP mode (optional): MCP Server (stdio) --> pyVmomi --> vSphere API
  |
vCenter Server --> ESXi Clusters --> VMs
    or
ESXi Standalone --> VMs
```
