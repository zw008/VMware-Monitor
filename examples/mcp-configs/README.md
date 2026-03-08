# MCP Configuration Templates

Copy the relevant config snippet into your AI agent's MCP configuration file.

## Prerequisites

```bash
# Install vmware-monitor
uv tool install vmware-monitor
# or: pip install vmware-monitor

# Configure credentials
mkdir -p ~/.vmware-monitor
cp config.example.yaml ~/.vmware-monitor/config.yaml
cp .env.example ~/.vmware-monitor/.env
chmod 600 ~/.vmware-monitor/.env
# Edit config.yaml and .env with your vCenter/ESXi details
```

## Agent Configuration Files

| Agent | Config File | Template |
|-------|------------|----------|
| Claude Code | `~/.claude/settings.json` | [claude-code.json](claude-code.json) |
| Goose | `goose configure` or UI | [goose.json](goose.json) |
| LocalCowork | MCP config panel | [localcowork.json](localcowork.json) |
| mcp-agent | `mcp_agent.config.yaml` | [mcp-agent.yaml](mcp-agent.yaml) |
| VS Code Copilot | `.vscode/mcp.json` | [vscode-copilot.json](vscode-copilot.json) |
| Cursor | Cursor MCP settings | [cursor.json](cursor.json) |
| Continue | `~/.continue/config.yaml` | [continue.yaml](continue.yaml) |

## Using with Local Models (Ollama)

vmware-monitor works with any MCP-compatible agent. For fully local operation (no cloud API):

```bash
# Example: Aider + Ollama + vmware-monitor CLI
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b

# Example: Continue + Ollama + MCP Server
# Configure Continue with Ollama model + vmware-monitor MCP server
```

## Safety Note

All 8 MCP tools are **read-only**. No destructive operations exist in this codebase.
