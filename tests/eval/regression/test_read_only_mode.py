"""Read-only mode must remove write tools from the real FastMCP registry.

Regression source: VMware-AIops issue #31 (juanpf-ha). An operator driving the
family with a local Llama 3.3 70B had to hand-write the prompt instruction
"work exclusively in read-only mode and never modify alerts, definitions,
reports or configuration", because read-only was only ever a documented
intent. A weak model can ignore a prompt; it cannot call a tool that is not in
list_tools().

vmware_policy/tests/test_readonly.py pins the gate's *semantics* against a
stand-in registry. This file pins the other half: that the real FastMCP API the
gate reaches for still behaves as assumed, and that this skill's actual tool
inventory splits the way its docs claim.

For vmware-monitor that inventory claim is the strong one — the skill is
non-destructive by design (代码级零破坏性), so *every* tool is marked ``[READ]``
and the gate must remove nothing. The gate is wired up regardless, for
interface consistency with the rest of the family and so the zero stays
provable against the live registry rather than merely documented.
"""

import asyncio
import importlib
import sys

import pytest

#: This skill has no write tools by design. Kept as an explicit empty set so a
#: future write tool that slips in makes the intent-vs-inventory gap loud.
WRITE_TOOLS: set[str] = set()


def _load_server(monkeypatch, read_only: str | None):
    """Import vmware_monitor.mcp_server.server fresh under the given read-only env."""
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.delenv("VMWARE_MONITOR_READ_ONLY", raising=False)
    if read_only is not None:
        monkeypatch.setenv("VMWARE_READ_ONLY", read_only)

    for name in [m for m in sys.modules if m.startswith("vmware_monitor.mcp_server")]:
        del sys.modules[name]
    return importlib.import_module("vmware_monitor.mcp_server.server")


def _tool_names(server) -> set[str]:
    return {t.name for t in asyncio.run(server.mcp.list_tools())}


@pytest.fixture(autouse=True)
def _restore_modules():
    """Restore the original module objects, do not just purge them.

    Deleting the entries would leave sibling test files importing a *fresh*
    mcp_server while their own monkeypatches still point at the old module
    object — the patches silently stop applying. Saving and re-inserting keeps
    module identity stable across this file's reimports.
    """
    saved = {n: m for n, m in sys.modules.items() if n.startswith("vmware_monitor.mcp_server")}
    yield
    for name in [n for n in sys.modules if n.startswith("vmware_monitor.mcp_server")]:
        del sys.modules[name]
    sys.modules.update(saved)


def test_gate_is_live_not_a_no_op(monkeypatch):
    """Prove the gate is actually wired into this server.

    Every other assertion in this file ("withheld == []", "all tools survive")
    is satisfied just as well by a repo where the gate was never called at all.
    This registers a probe write tool and shows the real call site removes it —
    which is what makes the empty-withheld-list assertions mean anything.
    """
    from vmware_policy import apply_read_only_gate

    server = _load_server(monkeypatch, "true")

    @server.mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True})
    def _probe_write_tool(a: str) -> str:
        """[WRITE] Probe tool — must not survive the gate."""
        return a

    assert "_probe_write_tool" in _tool_names(server)
    removed = apply_read_only_gate(server.mcp, "vmware-monitor")
    assert removed == ["_probe_write_tool"]
    assert "_probe_write_tool" not in _tool_names(server)


def test_default_mode_withholds_nothing(monkeypatch):
    """Baseline: without the switch the gate is inert."""
    server = _load_server(monkeypatch, None)
    assert server.WITHHELD_WRITE_TOOLS == []
    assert _tool_names(server)


def test_skill_has_no_write_tools(monkeypatch):
    """The non-destructive-by-design claim, checked against the live registry."""
    server = _load_server(monkeypatch, None)
    marked_write = {
        t.name
        for t in asyncio.run(server.mcp.list_tools())
        if not (t.description or "").lstrip().startswith("[READ]")
    }
    assert marked_write == WRITE_TOOLS, f"unexpected write tools: {marked_write}"


def test_read_only_removes_nothing(monkeypatch):
    """Nothing to withhold — and the gate must say so rather than guess."""
    server = _load_server(monkeypatch, "true")
    assert server.WITHHELD_WRITE_TOOLS == []


def test_read_only_keeps_every_tool(monkeypatch):
    """The gate must not be a blunt instrument — the full inventory survives."""
    baseline = _tool_names(_load_server(monkeypatch, None))
    gated = _tool_names(_load_server(monkeypatch, "true"))
    assert gated == baseline, f"tools lost in read-only mode: {baseline - gated}"


def test_every_surviving_tool_is_marked_read(monkeypatch):
    """End-to-end contract against the live registry."""
    server = _load_server(monkeypatch, "true")
    for tool in asyncio.run(server.mcp.list_tools()):
        assert (tool.description or "").lstrip().startswith("[READ]"), tool.name


def test_skill_env_var_also_works(monkeypatch):
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.setenv("VMWARE_MONITOR_READ_ONLY", "true")
    for name in [m for m in sys.modules if m.startswith("vmware_monitor.mcp_server")]:
        del sys.modules[name]
    server = importlib.import_module("vmware_monitor.mcp_server.server")
    assert server.WITHHELD_WRITE_TOOLS == []
    assert _tool_names(server)


def test_fastmcp_registry_api_still_present(monkeypatch):
    """The gate reaches into _tool_manager.list_tools(); pin that it exists.

    If an mcp upgrade moves this, we want a red test here rather than a gate
    that silently stops removing anything.
    """
    server = _load_server(monkeypatch, None)
    assert callable(getattr(server.mcp, "remove_tool", None))
    assert callable(getattr(server.mcp._tool_manager, "list_tools", None))
    assert server.mcp._tool_manager.list_tools()
