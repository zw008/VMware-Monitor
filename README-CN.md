# VMware Monitor

[English](README.md) | 中文

**只读** VMware vCenter/ESXi 监控工具。代码级安全保障 — 代码库中不存在任何破坏性操作。

> **为什么独立仓库？** VMware Monitor 完全独立于 [VMware-AIops](https://github.com/zw008/VMware-AIops)。安全性在**代码级别**保障：代码库中不存在关机、删除、创建、调整配置、快照创建/恢复/删除、克隆、迁移等函数。不仅仅是提示词约束 — 而是零破坏性代码路径。

[![ClawHub](https://img.shields.io/badge/ClawHub-vmware--monitor-orange)](https://clawhub.ai/skills/vmware-monitor)
[![Skills.sh](https://img.shields.io/badge/Skills.sh-Install-blue)](https://skills.sh/zw008/VMware-Monitor)
[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-Monitor)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### 快速安装（推荐）

支持 Claude Code、Cursor、Codex、Gemini CLI、Trae 等 30+ AI 工具：

```bash
# 通过 Skills.sh 安装
npx skills add zw008/VMware-Monitor

# 通过 ClawHub 安装
clawhub install vmware-monitor
```

### PyPI 安装（无需访问 GitHub）

```bash
# 通过 uv 安装（推荐）
uv tool install vmware-monitor

# 或通过 pip 安装
pip install vmware-monitor

# 国内镜像加速
pip install vmware-monitor -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Claude Code 快速安装

```bash
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

---

## 功能总览（只读）

### 架构

```
用户 (自然语言)
  ↓
AI CLI 工具 (Claude Code / Gemini / Codex / Aider / Continue / Trae / Kimi)
  ↓ 读取 SKILL.md / AGENTS.md / rules 指令
  ↓
vmware-monitor CLI（只读）
  ↓ pyVmomi (vSphere SOAP API)
  ↓
vCenter Server ──→ ESXi 集群 ──→ VM
    或
ESXi 独立主机 ──→ VM
```

### 版本兼容性

| vSphere 版本 | 支持状态 | 说明 |
|-------------|---------|------|
| 8.0 / 8.0U1-U3 | ✅ 完全支持 | pyVmomi 8.0.3+ |
| 7.0 / 7.0U1-U3 | ✅ 完全支持 | 所有只读 API 正常工作 |
| 6.7 | ✅ 兼容 | 向后兼容，已测试 |
| 6.5 | ✅ 兼容 | 向后兼容，已测试 |

### 1. 资源清单

| 功能 | vCenter | ESXi | 说明 |
|------|:-------:|:----:|------|
| 列出虚拟机 | ✅ | ✅ | 名称、电源状态、CPU、内存、操作系统、IP |
| 列出主机 | ✅ | ⚠️ 仅自身 | CPU 核数、内存、版本、VM 数、在线时间 |
| 列出数据存储 | ✅ | ✅ | 容量、已用/可用、类型、使用率 |
| 列出集群 | ✅ | ❌ | 主机数、DRS/HA 状态 |
| 列出网络 | ✅ | ✅ | 网络名、关联 VM 数 |

### 2. 健康监控

| 功能 | vCenter | ESXi | 说明 |
|------|:-------:|:----:|------|
| 活跃告警 | ✅ | ✅ | 严重级别、告警名、实体、时间 |
| 事件日志查询 | ✅ | ✅ | 按时间、严重级别过滤，识别 50+ 事件类型 |
| 硬件传感器 | ✅ | ✅ | 温度、电压、风扇状态 |
| 主机服务状态 | ✅ | ✅ | 服务运行/停止状态 |

### 3. VM 信息与快照列表（只读）

| 功能 | 说明 |
|------|------|
| VM 详情 | 名称、电源状态、操作系统、CPU、内存、IP、VMware Tools、磁盘、网卡 |
| 快照列表 | 列出已有快照名称和创建时间（无创建/恢复/删除） |

### 4. 定时扫描与通知

| 功能 | 说明 |
|------|------|
| 守护进程 | 基于 APScheduler，可配置间隔（默认 15 分钟） |
| 多目标扫描 | 依次扫描所有配置的 vCenter/ESXi 目标 |
| 日志分析 | 正则匹配：error, fail, critical, panic, timeout, corrupt |
| 结构化日志 | JSONL 输出到 `~/.vmware-monitor/scan.log` |
| Webhook 通知 | 支持 Slack、Discord 或任意 HTTP 端点 |

### 5. 安全特性

| 功能 | 说明 |
|------|------|
| **代码级隔离** | 独立仓库 — 代码中零破坏性函数 |
| **审计日志** | 所有查询记录到 `~/.vmware-monitor/audit.log`（JSONL） |
| **密码保护** | 通过 `.env` 加载密码并检查文件权限（warn if not 600） |
| **配置文件内容** | `config.yaml` 仅存储主机名、端口和 `.env` 引用路径，**不含密码或 Token** |
| **SSL 自签名** | 仅用于 ESXi 自签名证书的隔离实验环境；生产环境应使用 CA 签名证书 |
| **Prompt 注入防护** | vSphere 事件消息和主机日志在输出前进行截断、控制字符清理和边界标记（`[VSPHERE_EVENT]`/`[VSPHERE_HOST_LOG]`）包裹 |
| **Webhook 数据范围** | **默认禁用**。启用后仅向用户自配置的 URL 发送告警摘要，payload 不含凭据、IP 或 PII |
| **生产环境推荐** | AI Agent 可能误解上下文并执行非预期的破坏性操作 — 已有真实案例表明 AI 驱动工具删除了生产数据库和整个环境。VMware-Monitor 消除此风险：代码中不存在任何破坏性代码路径。仅在开发/实验环境使用 [VMware-AIops](https://github.com/zw008/VMware-AIops) |

### 不包含的操作（设计如此）

以下操作在本仓库中**不存在**：

- ❌ 开关机、重置、挂起
- ❌ 创建、删除、调整配置
- ❌ 创建/恢复/删除快照
- ❌ 克隆、迁移

需要这些操作请使用 [VMware-AIops](https://github.com/zw008/VMware-AIops)。

---

## 支持的 AI 平台

| 平台 | 状态 | 配置文件 | AI 模型 |
|------|------|---------|---------|
| **Claude Code** | ✅ 原生技能 | `skills/vmware-monitor/SKILL.md` | Anthropic Claude |
| **Gemini CLI** | ✅ Extension | `gemini-extension/GEMINI.md` | Google Gemini |
| **Codex CLI** | ✅ Skill + AGENTS.md | `codex-skill/AGENTS.md` | OpenAI GPT |
| **Aider** | ✅ 约定文件 | `codex-skill/AGENTS.md` | 任意（云端 + 本地） |
| **Continue CLI** | ✅ 规则文件 | `codex-skill/AGENTS.md` | 任意（云端 + 本地） |
| **Trae IDE** | ✅ Rules | `trae-rules/project_rules.md` | Claude/DeepSeek/GPT-4o |
| **Kimi Code CLI** | ✅ Skill | `kimi-skill/SKILL.md` | Moonshot Kimi |
| **MCP Server** | ✅ MCP 协议 | `mcp_server/` | 任意 MCP 客户端 |
| **Python CLI** | ✅ 独立运行 | N/A | N/A |

### MCP Server 集成（本地 Agent）

vmware-monitor MCP Server 可接入**任何 MCP 兼容的 Agent 或工具**。配置模板见 [`examples/mcp-configs/`](examples/mcp-configs/)。所有 8 个工具均为**只读** — 代码级安全保障。

| Agent / 工具 | 本地模型支持 | 配置模板 |
|-------------|:----------:|---------|
| **[Goose](https://github.com/block/goose)** | ✅ Ollama, LM Studio | [`goose.json`](examples/mcp-configs/goose.json) |
| **[LocalCowork](https://github.com/Liquid4All/localcowork)** | ✅ 完全离线 | [`localcowork.json`](examples/mcp-configs/localcowork.json) |
| **[mcp-agent](https://github.com/lastmile-ai/mcp-agent)** | ✅ Ollama, vLLM | [`mcp-agent.yaml`](examples/mcp-configs/mcp-agent.yaml) |
| **VS Code Copilot** | — | [`.vscode/mcp.json`](examples/mcp-configs/vscode-copilot.json) |
| **Cursor** | — | [`cursor.json`](examples/mcp-configs/cursor.json) |
| **Continue** | ✅ Ollama | [`continue.yaml`](examples/mcp-configs/continue.yaml) |
| **Claude Code** | — | [`claude-code.json`](examples/mcp-configs/claude-code.json) |

**完全本地运行**（无需云端 API）：

```bash
# Aider + Ollama + vmware-monitor（通过 AGENTS.md）
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

---

## 安装

### 第 1 步：安装

```bash
git clone https://github.com/zw008/VMware-Monitor.git
cd VMware-Monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 第 2 步：配置

```bash
mkdir -p ~/.vmware-monitor
cp config.example.yaml ~/.vmware-monitor/config.yaml
# 编辑 config.yaml，填入你的 vCenter/ESXi 目标信息
```

通过 `.env` 文件设置密码（推荐）：

```bash
cp .env.example ~/.vmware-monitor/.env
chmod 600 ~/.vmware-monitor/.env
# 编辑并填入真实密码
```

> **安全提示**：推荐使用 `.env` 文件而非命令行 `export`，避免密码出现在 shell 历史记录中。

密码环境变量命名规则：`VMWARE_{目标名大写}_PASSWORD`

### 第 3 步：连接 AI 工具

#### Claude Code（推荐）

```bash
/plugin marketplace add zw008/VMware-Monitor
/plugin install vmware-monitor
/vmware-monitor:vmware-monitor
```

#### Codex / Aider / Continue

```bash
# 云端
aider --conventions codex-skill/AGENTS.md
# 本地 Ollama
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

#### MCP 服务器

```bash
python -m mcp_server
# 或: vmware-monitor-mcp
```

#### 独立 CLI（无需 AI）

```bash
source .venv/bin/activate
vmware-monitor inventory vms --target home-esxi
vmware-monitor health alarms --target home-esxi
```

---

## CLI 命令参考

```bash
# 环境诊断
vmware-monitor doctor                   # 检查环境、配置、连通性
vmware-monitor doctor --skip-auth       # 跳过 vSphere 认证检查（更快）

# MCP 配置生成
vmware-monitor mcp-config generate --agent goose        # 生成 Goose 配置
vmware-monitor mcp-config generate --agent claude-code  # 生成 Claude Code 配置
vmware-monitor mcp-config list                          # 列出所有支持的 Agent

# 资源清单
vmware-monitor inventory vms|hosts|datastores|clusters [--target <name>]
vmware-monitor inventory vms --limit 10 --sort-by memory_mb  # 按内存排序 Top 10
vmware-monitor inventory vms --power-state poweredOn         # 只显示开机 VM

# 健康检查
vmware-monitor health alarms [--target <name>]
vmware-monitor health events --hours 24 --severity warning [--target <name>]

# VM 信息（只读）
vmware-monitor vm info <vm-name>
vmware-monitor vm snapshot-list <vm-name>

# 扫描与守护进程
vmware-monitor scan now [--target <name>]
vmware-monitor daemon start|stop|status
```

---

## 项目结构

```
VMware-Monitor/
├── vmware_monitor/                # Python 后端（仅只读）
│   ├── config.py                  # 配置管理
│   ├── connection.py              # 多目标连接（pyVmomi）
│   ├── cli.py                     # CLI（仅只读命令）
│   ├── ops/                       # 查询操作
│   │   ├── inventory.py           # 资源清单
│   │   ├── health.py              # 健康检查
│   │   └── vm_info.py             # VM 信息、快照列表（只读）
│   ├── scanner/                   # 日志扫描守护进程
│   └── notify/                    # 通知（JSONL + Webhook）
├── mcp_server/                    # MCP 服务器（仅只读工具）
├── skills/vmware-monitor/         # Skills.sh 索引
├── plugins/vmware-monitor/        # Claude Code 插件
├── gemini-extension/              # Gemini CLI 扩展
├── codex-skill/                   # Codex / Aider / Continue
├── trae-rules/                    # Trae IDE 规则
├── kimi-skill/                    # Kimi Code CLI 技能
├── config.example.yaml
└── pyproject.toml
```

## 相关项目

| 仓库 | 说明 | 安装 |
|------|------|------|
| [VMware-Monitor](https://github.com/zw008/VMware-Monitor)（本仓库） | 只读监控 — 代码级安全 | `clawhub install vmware-monitor` |
| [VMware-AIops](https://github.com/zw008/VMware-AIops) | 完整运维 — 监控 + VM 生命周期 | `clawhub install vmware-aiops` |

## 问题反馈与贡献

如果遇到任何报错或问题，请将错误信息、日志或截图发送至 **zhouwei008@gmail.com**。欢迎贡献！

## 许可证

MIT
