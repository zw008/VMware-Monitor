# Capabilities (Read-Only)

Detailed feature tables for `vmware-monitor`.

## 1. Inventory

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| List VMs | Y | Y | Name, power state, CPU, memory, guest OS, IP |
| List Hosts | Y | Self only | CPU cores, memory, ESXi version, VM count, uptime |
| List Datastores | Y | Y | Capacity, free/used, type (VMFS/NFS), usage % |
| List Clusters | Y | N | Host count, DRS/HA status |
| List Networks | Y | Y | Network name, associated VM count |

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
| VM Info | Name, power state, guest OS, CPU, memory, IP, VMware Tools, disks, NICs |
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
| Audit Trail | All queries logged to `~/.vmware-monitor/audit.log` (JSONL) |
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

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | Full | pyVmomi 8.0.3+ |
| 7.0 / 7.0U1-U3 | Full | All read-only APIs supported |
| 6.7 | Compatible | Backward-compatible, tested |
| 6.5 | Compatible | Backward-compatible, tested |

> pyVmomi auto-negotiates the API version during SOAP handshake — no manual configuration needed.
