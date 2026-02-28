# Release Notes

## v0.1.0 (2026-02-28)

**Initial release — Read-only VMware monitoring with code-level safety.**

Extracted from [VMware-AIops](https://github.com/zw008/VMware-AIops) as an independent repository. Zero destructive code paths — no power, create, delete, reconfigure, snapshot mutate, clone, or migrate operations exist in the codebase.

### Features

- **Inventory**: List VMs, ESXi hosts, datastores, clusters
- **Health & Monitoring**: Active alarms, recent events (50+ event types), hardware sensors, host services
- **VM Info**: Detailed VM information and snapshot listing (read-only)
- **Scheduled Scanning**: APScheduler daemon with configurable intervals, alarm + event + host log scanning
- **Notifications**: JSONL structured logs, Slack/Discord webhook alerts
- **Audit Trail**: All queries logged to `~/.vmware-monitor/audit.log` (JSONL)
- **Multi-target**: Sequential scanning across all configured vCenter/ESXi targets
- **MCP Server**: 7 read-only tools via Model Context Protocol (FastMCP)
- **CLI**: `vmware-monitor` with inventory, health, vm, scan, daemon subcommands

### AI Platform Support

- Claude Code (native plugin + marketplace)
- OpenAI Codex CLI (AGENTS.md)
- Aider / Continue CLI (AGENTS.md)
- Gemini CLI (AGENTS.md)
- Trae IDE (AGENTS.md)
- Kimi Code CLI (AGENTS.md)
- MCP Server (Smithery / Claude Desktop / Cursor)

### Safety

- **Code-level isolation**: No destructive functions or pyVmomi write API calls in the codebase
- **Automated verification**: `test_no_destructive_code.py` checks 40+ destructive patterns
- **PR template**: Read-Only Verification checklist required for all pull requests
- **Credential security**: `.env` with `chmod 600`, `ConnectionManager.from_config()`, zero password exposure

### Configuration

- Independent config directory: `~/.vmware-monitor/`
- YAML-based multi-target configuration
- Environment variable passwords: `VMWARE_{TARGET_NAME}_PASSWORD`
- SSL self-signed certificate support

### Compatibility

| vSphere Version | Support |
|----------------|---------|
| 8.0 / 8.0U1-U3 | Full |
| 7.0 / 7.0U1-U3 | Full |
| 6.7 | Compatible |
| 6.5 | Compatible |

Requires Python >= 3.10, pyVmomi >= 8.0.3.0.
