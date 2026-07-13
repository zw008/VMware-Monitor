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

## Cluster Health Summary

```bash
vmware-monitor summary [--top <n>] [--cluster <substring>] [--no-vms] [--html] [--html-path <file>] [--target <name>]
```

- One aggregated read across all clusters. Leads with a ranked **top-N issues** focus list (the individual anomalies — disconnected hosts, triggered alarms, capacity/HA — worst first, each with a drill-down hint), then a per-cluster table: hosts connected/total, VM power rollup, live CPU/memory %, HA/DRS, alarm counts, and an opinionated `status` (ok/warn/critical) with `attention` reasons.
- `--top`: size of the focus list (default 10; `--top 5` tighter, `--top 0` hides it and shows only the table). The header shows "Top N (of TOTAL)" when truncated.
- `--cluster`: case-insensitive substring; show only matching clusters (also suppresses the standalone-hosts bucket).
- `--no-vms`: skip the VM rollup pass (faster on very large fleets when only host/alarm/capacity signals are needed).
- `--html`: write a self-contained, offline HTML snapshot (no external CSS/JS/fonts — nothing leaves the machine) to `~/vmware-health/cluster-health-<vc>-<YYYYMMDD-HHMMSS>.html`. The timestamped filename turns a folder of snapshots into a browsable point-in-time history. It is a snapshot, not a live page — re-run to refresh.
- `--html-path <file>`: write the HTML snapshot to an explicit path instead of the auto-timestamped default (implies `--html`).
- The rendered view is customizable — columns, thresholds, and layout live in [`health-summary-template.md`](health-summary-template.md). MCP tool: `cluster_health_summary`.

## Inventory

```bash
vmware-monitor inventory vms [--target <name>] [--limit <n>] [--sort-by name|cpu|memory_mb|power_state|folder_path] [--power-state poweredOn|poweredOff] [--folder-filter <pattern>]
vmware-monitor inventory hosts [--target <name>]
vmware-monitor inventory datastores [--target <name>]
vmware-monitor inventory clusters [--target <name>]
vmware-monitor inventory networks [--target <name>]
```

- `--target`: Named target from `config.yaml` (default: first target)
- `--limit`: Max VMs to return (default: unlimited)
- `--sort-by`: Sort field for VM listing — `name` | `cpu` | `memory_mb` | `power_state` | `folder_path`
- `--power-state`: Filter VMs by power state
- `--folder-filter`: Case-insensitive substring match against `folder_path` (e.g. `--folder-filter "Production"` returns VMs anywhere under a folder containing "production", including nested subfolders like `/Datacenters/Production/Web Tier`).

**Output fields** (CLI and MCP): each VM entry includes `folder_path` — the vCenter inventory folder path (e.g. `/Datacenters/Production/Web Tier`). Present in both compact and full modes.

## Health

```bash
vmware-monitor health alarms [--target <name>]
vmware-monitor health events [--hours 24] [--severity warning] [--target <name>]
vmware-monitor health sensors [--target <name>]
vmware-monitor health services [--host <esxi-name>] [--target <name>]
```

- `--hours`: Time range for event query (default: 24)
- `--severity`: Minimum severity filter — `info`, `warning`, `error`, `critical` (default: `warning`)
- `--host` (services only): Filter service status to a single host by exact name (default: all hosts)

## VM Info (Read-Only)

```bash
vmware-monitor vm info <vm-name> [--target <name>]
vmware-monitor vm snapshot-list <vm-name> [--target <name>]
```

Returns detailed VM information: CPU, memory, disks, NICs, guest OS, IP, VMware Tools status, and snapshots.

`snapshot-list` lists existing snapshots with name and creation time. No create, revert, or delete operations exist. The same data is exposed via the MCP tool `vm_list_snapshots`.

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

## Setup

```bash
mkdir -p ~/.vmware-monitor
cp config.example.yaml ~/.vmware-monitor/config.yaml
cp .env.example ~/.vmware-monitor/.env
chmod 600 ~/.vmware-monitor/.env
```

Copies the `config.yaml` and `.env` templates into `~/.vmware-monitor/`; then edit them with your target details.

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
