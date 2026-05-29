# Capabilities (Read-Only)

Detailed feature tables for `vmware-monitor`.

## Automation Level Reference

Each operation is classified by autonomy level per the Enterprise Harness Engineering framework. **vmware-monitor is L1/L2 only by design** — no write operations exist in the codebase, enforced at the test level.

| Level | Meaning | Agent autonomy | Examples in this skill |
|:-:|---|---|---|
| **L1** | Read-only, raw data | Always auto-run | `list_vms`, `list_hosts`, `list_alarms`, `list_events`, `list_datastores`, `list_clusters`, `host_status` |
| **L2** | Read + analysis / recommendation | Always auto-run | scheduled scan reports, log pattern matching (error/fail/critical/panic/timeout), alarm correlation, daemon-driven webhook digests |
| **L3** | Single write — user must approve | *N/A* | — *(use [vmware-aiops](https://github.com/zw008/VMware-AIops) for write operations)* |
| **L4** | Multi-step plan / apply workflow | *N/A* | — *(use [vmware-pilot](https://github.com/zw008/VMware-Pilot) for orchestration)* |
| **L5** | Auto-remediation from learned pattern | *N/A* | — *(remediation is out of scope by design)* |

**Notes**:
- All tools are safe for agents to call without confirmation — the skill is code-level read-only.
- Test file `test_no_destructive_operations.py` enforces this invariant on every commit.

## 1. Inventory

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| List VMs | Y | Y | Name, power state, CPU, memory, guest OS, IP, `folder_path` (vCenter inventory folder, e.g. `/Datacenters/Production/Web Tier`) |
| List Hosts | Y | Self only | CPU cores, memory, ESXi version, VM count, uptime |
| List Datastores | Y | Y | Capacity, free/used, type (VMFS/NFS), usage % |
| List Clusters | Y | N | Host count, DRS/HA status |
| List Networks | Y | Y | Network name, associated VM count |

### `list_vms` — input parameters

| Parameter | Type | Default | Behavior |
|-----------|------|---------|----------|
| `target` | str (optional) | default target | Named vCenter/ESXi target from `config.yaml` |
| `limit` | int (optional) | None (all) | Max VMs to return |
| `sort_by` | str | `name` | `name` \| `cpu` \| `memory_mb` \| `power_state` \| `folder_path` |
| `power_state` | str (optional) | None | `poweredOn` \| `poweredOff` \| `suspended` |
| `fields` | list[str] (optional) | auto | Subset of: `name`, `power_state`, `cpu`, `memory_mb`, `guest_os`, `ip_address`, `host`, `uuid`, `tools_status`, `folder_path` |
| `folder_filter` | str (optional) | None | **MCP-only.** Case-insensitive substring match against `folder_path`. Example: `folder_filter="Production"` returns VMs anywhere under any folder whose path contains "production" (including nested subfolders like `/Datacenters/Production/Web Tier`). |

### `list_vms` — response fields

Each VM dict in the `vms` array contains:

| Field | Description |
|-------|-------------|
| `name` | VM name |
| `power_state` | `poweredOn` / `poweredOff` / `suspended` |
| `cpu` | vCPU count |
| `memory_mb` | RAM in MB |
| `guest_os` | Guest OS full name (full mode only) |
| `ip_address` | Guest IP from VMware Tools (full mode only) |
| `host` | ESXi host name (full mode only) |
| `uuid` | VM UUID (full mode only) |
| `tools_status` | VMware Tools running status (full mode only) |
| `folder_path` | vCenter inventory folder path, e.g. `/Datacenters/Production/Web Tier`. Returned in both compact and full modes. |

## 2. Health & Monitoring

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| Active Alarms | Y | Y | Severity, alarm name, entity, timestamp |
| Event/Log Query | Y | Y | Filter by time range, severity; 50+ event types |
| Hardware Sensors | Y | Y | Temperature, voltage, fan status |
| Host Services | Y | Y | hostd, vpxa running/stopped status |

### Monitored Event Types

| Category | Events |
|----------|--------|
| VM Failures | `VmFailedToPowerOnEvent`, `VmDiskFailedEvent`, `VmFailoverFailed` |
| Host Issues | `HostConnectionLostEvent`, `HostShutdownEvent`, `HostIpChangedEvent` |
| Storage | `DatastoreCapacityIncreasedEvent`, SCSI high latency |
| HA/DRS | `DasHostFailedEvent`, `DrsVmMigratedEvent`, `DrsSoftRuleViolationEvent` |
| Auth | `UserLoginSessionEvent`, `BadUsernameSessionEvent` |

## 3. VM Info & Snapshot List

| Feature | Details |
|---------|---------|
| VM Info | Name, power state, guest OS, CPU, memory, IP, VMware Tools, disks, NICs, `folder_path` |
| Snapshot List | List existing snapshots with name and creation time (no create/revert/delete) |

## 4. Scheduled Scanning & Notifications

| Feature | Details |
|---------|---------|
| Daemon | APScheduler-based, configurable interval (default 15 min) |
| Multi-target Scan | Sequentially scan all configured vCenter/ESXi targets |
| Scan Content | Alarms + Events + Host logs (hostd, vmkernel, vpxd) |
| Log Analysis | Regex pattern matching: error, fail, critical, panic, timeout |
| Webhook | Slack, Discord, or any HTTP endpoint |

## Safety Features

| Feature | Details |
|---------|---------|
| Code-Level Isolation | Independent repository — zero destructive functions in codebase |
| Audit Trail | All queries logged to `~/.vmware/audit.db` (SQLite WAL, via vmware-policy) |
| Password Protection | `.env` file loading with permission check (warn if not 600) |
| SSL Self-signed Support | `disableSslCertValidation` — **only** for ESXi hosts with self-signed certificates in isolated lab/home environments. Production environments should use CA-signed certificates with full TLS verification enabled. |

## FORBIDDEN Operations — DO NOT EXIST IN CODEBASE

These operations **cannot** be performed with this skill — zero destructive code paths exist:

- `vm power-on/off`, `vm reset`, `vm suspend`
- `vm create/delete/reconfigure`
- `vm snapshot-create/revert/delete`
- `vm clone/migrate`

Direct users to **VMware-AIops** (`uv tool install vmware-aiops`) for these.

## Version Compatibility

| vSphere / VCF Version | Support | Notes |
|----------------|---------|-------|
| VCF 9.1 / vSphere 9.1 | ✅ Full | Released 2026-05-12. pyVmomi `<10.0` resolves and connects via SOAP. |
| VCF 9.0 / vSphere 9.0 | ✅ Full | pyVmomi 8.0.3+ connects against vSphere 9 SOAP API. |
| 8.0 / 8.0U1-U3 | Full | pyVmomi 8.0.3+ |
| 7.0 / 7.0U1-U3 | Full | All read-only APIs supported |
| 6.7 | Compatible | Backward-compatible, tested |
| 6.5 | Compatible | Backward-compatible, tested |

> pyVmomi auto-negotiates the API version during SOAP handshake — no manual configuration needed.
