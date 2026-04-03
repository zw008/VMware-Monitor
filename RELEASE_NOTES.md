# Release Notes

## v1.4.5 — 2026-04-03

- **Security**: bump pygments 2.19.2 → 2.20.0 (fix ReDoS CVE in GUID matching regex)
- **Infrastructure**: add uv.lock for reproducible builds and Dependabot security tracking

---

## v1.4.0 — 2026-03-29

### Architecture: Unified Audit & Policy

- **vmware-policy integration**: All MCP tools now wrapped with `@vmware_tool` decorator
- **Unified audit logging**: Operations logged to `~/.vmware/audit.db` (SQLite WAL), replacing per-skill JSON Lines logs
- **Policy enforcement**: `check_allowed()` with rules.yaml, maintenance windows, risk-level gating
- **Sanitize consolidation**: Replaced local `_sanitize()` with shared `vmware_policy.sanitize()`
- **Risk classification**: Each tool tagged with risk_level (low/medium/high) for confirmation gating
- **Agent detection**: Audit logs identify calling agent (Claude/Codex/local)
- **New family members**: vmware-policy (audit/policy infrastructure) + vmware-pilot (workflow orchestration)

---

## v1.3.1 — 2026-03-27

### Family expansion: NSX, NSX-Security, Aria

- Added vmware-nsx, vmware-nsx-security, vmware-aria to companion skills routing table
- README updated with complete 7-skill family table
- vmware-aiops is now the family entry point (`vmware-aiops hub status`)

---

## v1.3.0 — 2026-03-26

### Docs / Skill optimization

- SKILL.md restructured with progressive disclosure (3-level loading)
- Created `references/` directory: cli-reference.md, capabilities.md, setup-guide.md
- Added trigger phrases to YAML description for better skill auto-loading
- Added Common Workflows section (Daily Health Check, Investigate VM, Continuous Monitoring)
- Added Troubleshooting section (5 common issues)
- README.md and README-CN.md updated with Companion Skills, Workflows, Troubleshooting

---

## v1.2.3 (2026-03-22)

### Docs / SKILL.md restructure

- Reorder SKILL.md: tool table and Quick Install first, routing table last — improves Skills.sh/ClawHub page readability.

---

## v1.2.1 (2026-03-22)

### Skill Routing / Skill 智能路由推荐

- SKILL.md 新增 **Related Skills — Skill Routing** 路由表：遇到存储相关请求推荐 vmware-storage，遇到 VM 操作需求推荐 vmware-aiops。
- Added **Related Skills** routing table to SKILL.md: recommends vmware-storage for storage tasks, vmware-aiops for VM lifecycle operations.

---

## v1.2.0 (2026-03-21)

### mcp-config install — Auto-write Agent Config / 自动写入 Agent 配置

- **`vmware-monitor mcp-config install --agent <name>`** — Directly writes MCP server config into the target agent's config file.
  直接将 MCP server 配置写入目标 Agent 的配置文件，无需手动编辑 JSON/YAML。
  - Supports: claude-code, cursor, goose, continue, vscode, localcowork, mcp-agent / 支持 7 种 Agent
  - JSON merge (non-destructive) + auto-backup on conflict / JSON 合并（非破坏性）+ 冲突时自动备份

### Docker One-Command Launch / Docker 一键启动

- **Dockerfile + docker-compose.yml** — Run MCP server without installing Python or venv.
  无需安装 Python 或 venv，一条命令启动 MCP Server。
  ```bash
  docker compose up -d
  ```

### Cursor Integration Guide / Cursor 集成文档

- **`docs/integrations/cursor.md`** — Full guide for using vmware-monitor as a read-only Cursor MCP server.
  完整的 Cursor 集成指南，包含自动安装、手动配置、8 个只读工具说明和排障指南。

**PyPI**: `uv tool install vmware-monitor==1.2.0`

---

## v1.1.0 (2026-03-21)

> **Version unification release / 版本统一发布**
> All platforms (PyPI, GitHub Release, MCP Registry, Skills.sh, ClawHub, Smithery) now share the same version number starting from v1.1.0.
> 所有平台从 v1.1.0 起统一版本号。

### Doctor & MCP Config Generator / 诊断与配置生成

- `vmware-monitor doctor` — 8-check environment diagnostic / 8 项环境诊断
- `vmware-monitor mcp-config generate --agent <name>` — Generate config for 7 local AI agents / 为 7 种本地 AI Agent 生成配置

### Inventory Enhancements / 资源清单增强

- `list_vms` with limit/sort_by/power_state/fields filtering / 支持过滤、排序、字段选择
- Auto-tiered response for large inventories (>50 VMs) / 大规模环境自动精简返回

### Security Hardening / 安全加固

- Prompt injection protection with boundary markers / Prompt 注入防护（边界标记）
- Bandit security scan: 0 issues / Bandit 安全扫描零问题

### Platform & Integration / 平台与集成

- MCP Registry, Skills.sh, ClawHub, Smithery, Glama, mcp.so, Cline Marketplace published
- Local agent config templates for 7 agents (Claude Code, Cursor, Goose, LocalCowork, mcp-agent, Continue, VS Code Copilot)
- Ollama end-to-end setup guide

**PyPI**: `uv tool install vmware-monitor==1.1.0`

---

## v0.1.2 (2026-03-05)

### Usage Mode Optimization

- **Platform-aware calling priority**: Claude Code and Cursor users get MCP-first experience (structured tool calls, no interactive confirmation needed). Aider, Codex, Gemini CLI, and local models (Ollama) default to CLI mode for lower context overhead and universal compatibility.

- **Install order update**: Skills.sh (`npx skills add`) is now the primary install method; ClawHub as secondary option.

- **MCP load tip**: Added tip for MCP-native tools to check MCP server status (`/mcp`) before use.

**Files updated**: `skills/vmware-monitor/SKILL.md`, `plugins/.../SKILL.md`, `README.md`, `README-CN.md`

---

## v0.1.1 (2026-03-03)

### Security Hardening: Prompt Injection Protection

- **Boundary markers**: All vSphere-sourced content (event messages, host logs) is now wrapped in explicit boundary markers (`[VSPHERE_EVENT]...[/VSPHERE_EVENT]`, `[VSPHERE_HOST_LOG]...[/VSPHERE_HOST_LOG]`) so downstream LLM agents can distinguish trusted output from untrusted vSphere data.

- **Comprehensive control character sanitization**: Replaced simple null-byte removal with regex-based stripping of all C0/C1 control characters (except `\n` and `\t`). Prevents prompt injection via embedded control sequences in vSphere event messages.

- **MCP server documentation**: Added comprehensive module docstring to `mcp_server/server.py` with security considerations (all-read-only tool classification, credential handling, transport security) to resolve Socket "Obfuscated File" audit flag.

- **Security section in SKILL.md**: Added explicit Security section covering read-only design, TLS verification, credential handling, webhook data scope, prompt injection protection, and code review guidance.

- **README safety table updates**: Added Prompt Injection Protection and Webhook Data Scope rows to safety features table in both English and Chinese READMEs.

**Files updated**: `vmware_monitor/scanner/log_scanner.py`, `mcp_server/server.py`, `skills/vmware-monitor/SKILL.md`, `plugins/.../SKILL.md`, `README.md`, `README-CN.md`

---

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
- **Credential security**: `.env` with `chmod 600`, config-based connections, zero password exposure

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
