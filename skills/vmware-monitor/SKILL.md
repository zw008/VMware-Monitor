---
name: vmware-monitor
description: >
  VMware vCenter/ESXi read-only monitoring skill. Code-level enforced safety —
  zero destructive operations in the codebase. Query inventory (VMs, hosts,
  datastores, clusters), check health/alarms/events, view VM details and snapshots.
  Use when user asks to "list VMs", "check alarms", "show host status",
  "get VM info", "what events happened", "monitor vSphere", or needs
  read-only VMware/vSphere/ESXi information. For VM operations use vmware-aiops,
  for storage use vmware-storage, for Kubernetes use vmware-vks.
installer:
  kind: uv
  package: vmware-monitor
allowed-tools:
  - Bash
metadata: {"openclaw":{"requires":{"env":["VMWARE_MONITOR_CONFIG"],"bins":["vmware-monitor"],"config":["~/.vmware-monitor/config.yaml"]},"primaryEnv":"VMWARE_MONITOR_CONFIG","homepage":"https://github.com/zw008/VMware-Monitor","emoji":"📊","os":["macos","linux"]}}
---

# VMware Monitor (Read-Only)

Read-only VMware vCenter/ESXi monitoring — 8 MCP tools, zero destructive code.

> **Code-level safety**: This skill contains NO power, create, delete, snapshot, or modify operations. Not disabled — they don't exist in the codebase.
> **Companion skills**: [vmware-aiops](https://github.com/zw008/VMware-AIops) (VM lifecycle), [vmware-storage](https://github.com/zw008/VMware-Storage) (iSCSI/vSAN), [vmware-vks](https://github.com/zw008/VMware-VKS) (Tanzu Kubernetes), [vmware-nsx](https://github.com/zw008/VMware-NSX) (NSX networking), [vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security) (DFW/firewall), [vmware-aria](https://github.com/zw008/VMware-Aria) (metrics/alerts/capacity).

## What This Skill Does

| Category | Capabilities |
|----------|-------------|
| **Inventory** | List VMs, ESXi hosts, datastores, clusters |
| **Health** | Active alarms, recent events (filter by severity/time) |
| **VM Details** | CPU, memory, disks, NICs, snapshots, guest OS, IP |
| **Scanning** | Scheduled alarm/log scanning with Slack/Discord webhooks |

## Quick Install

```bash
uv tool install vmware-monitor
vmware-monitor doctor
```

## When to Use This Skill

- List or search VMs, hosts, datastores, clusters
- Check active alarms or recent events
- Get detailed info about a specific VM
- Set up scheduled monitoring with webhook alerts
- Any read-only VMware query where safety is paramount

**Use companion skills for**:
- Power on/off, deploy, clone, migrate --> `vmware-aiops`
- iSCSI, vSAN, datastore management --> `vmware-storage`
- Tanzu Kubernetes clusters --> `vmware-vks`

## Related Skills — Skill Routing

| User Intent | Recommended Skill |
|-------------|------------------|
| Read-only vSphere monitoring, zero risk | **vmware-monitor** ← this skill |
| Storage: iSCSI, vSAN, datastores | **vmware-storage** |
| VM lifecycle, deployment, guest ops | **vmware-aiops** |
| Tanzu Kubernetes (vSphere 8.x+) | **vmware-vks** |
| NSX networking: segments, gateways, NAT | **vmware-nsx** |
| NSX security: DFW rules, security groups | **vmware-nsx-security** |
| Aria Ops: metrics, alerts, capacity planning | **vmware-aria** |

## Common Workflows

### Daily Health Check
1. Check alarms --> `vmware-monitor health alarms --target prod-vcenter`
2. Review recent events --> `vmware-monitor health events --hours 24 --severity warning`
3. List hosts --> `vmware-monitor inventory hosts` --> check connection state and memory usage

### Investigate a Specific VM
1. Find the VM --> `vmware-monitor inventory vms --power-state poweredOff`
2. Get details --> `vmware-monitor vm info problem-vm`
3. Check related events --> `vmware-monitor health events --hours 48`

### Set Up Continuous Monitoring
1. Configure webhook in `~/.vmware-monitor/config.yaml`
2. Start daemon --> `vmware-monitor daemon start`
3. Daemon scans every 15 min, sends alerts to Slack/Discord

## MCP Tools (8)

| Tool | Description |
|------|------------|
| `list_virtual_machines` | List VMs with filtering (power state, sort, limit) |
| `list_esxi_hosts` | ESXi hosts with CPU, memory, version, uptime |
| `list_all_datastores` | Datastores with capacity, free space, type |
| `list_all_clusters` | Clusters with host count, DRS/HA status |
| `get_alarms` | All active/triggered alarms |
| `get_events` | Recent events filtered by severity and time |
| `vm_info` | Detailed VM info (CPU, memory, disks, NICs, snapshots) |

All tools are **read-only**. No tool can modify, create, or delete any resource.

## CLI Quick Reference

```bash
vmware-monitor inventory vms [--target <t>] [--limit 20] [--power-state poweredOn]
vmware-monitor inventory hosts [--target <t>]
vmware-monitor inventory datastores [--target <t>]
vmware-monitor inventory clusters [--target <t>]
vmware-monitor health alarms [--target <t>]
vmware-monitor health events [--hours 24] [--severity warning]
vmware-monitor vm info <vm-name> [--target <t>]
vmware-monitor scan now [--target <t>]
vmware-monitor daemon start|stop|status
vmware-monitor doctor [--skip-auth]
```

> Full CLI reference: see `references/cli-reference.md`

## Troubleshooting

### Alarms returns empty but vCenter shows alarms
The `get_alarms` tool queries triggered alarms at the root folder level. Some alarms are entity-specific — try checking events instead: `get_events --hours 1 --severity info`.

### "Connection refused" error
1. Run `vmware-monitor doctor` to diagnose
2. Verify target hostname/IP and port (443) in config.yaml
3. For self-signed certs: set `disableSslCertValidation: true`

### Events returns too many results
Use severity filter: `--severity warning` (default) filters out info-level events. Use `--hours 4` to narrow time range.

### VM info shows "guest_os: unknown"
VMware Tools not installed or not running in the guest. Install/start VMware Tools for guest OS detection, IP address, and guest family info.

### Doctor passes but commands fail with timeout
vCenter may be under heavy load. Try targeting a specific ESXi host directly instead of vCenter, or increase connection timeout in config.yaml.

## Setup

```bash
uv tool install vmware-monitor
mkdir -p ~/.vmware-monitor
vmware-monitor init
chmod 600 ~/.vmware-monitor/.env  # if using webhooks
```

> Full setup guide, security details, and AI platform compatibility: see `references/setup-guide.md`

## License

MIT — [github.com/zw008/VMware-Monitor](https://github.com/zw008/VMware-Monitor)
