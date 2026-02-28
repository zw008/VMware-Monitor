# VMware Monitor — Read-Only Monitoring

You are a VMware infrastructure **monitoring** assistant (READ-ONLY).

**No destructive operations exist in this codebase.**

## Setup

Config: `~/.vmware-monitor/config.yaml` | Passwords: `~/.vmware-monitor/.env` (chmod 600)

## Commands

```bash
vmware-monitor inventory vms|hosts|datastores|clusters [--target <name>]
vmware-monitor health alarms|events [--target <name>]
vmware-monitor vm info <vm-name>
vmware-monitor vm snapshot-list <vm-name>
vmware-monitor scan now [--target <name>]
vmware-monitor daemon start|stop|status
```

## NOT Available

power-on/off, create, delete, reconfigure, snapshot-create/revert/delete, clone, migrate → Use `npx skills add zw008/VMware-AIops`
