"""The only repo-specific facts in this capability suite.

Every ``test_*.py`` file in this directory is byte-identical across the family
repos; they differ only through this module. Keeping the difference in one small
file is what makes a rubric change portable — edit the eval once, copy it, and
the scores stay comparable between skills.
"""

from __future__ import annotations

#: Import path of the Python package under test.
PACKAGE = "vmware_monitor"

#: Module holding the FastMCP ``mcp`` instance.
SERVER_MODULE = "vmware_monitor.mcp_server.server"

#: CLI entry point name, used when scoring whether an error names something
#: concrete for the operator to run.
CLI_NAME = "vmware-monitor"

#: Companion skills this one legitimately routes to. A required entity name that
#: this surface cannot produce is not a dead end *if* the description says which
#: sibling skill produces it — that is a documented hand-off rather than a gap.
COMPANION_SKILLS = (
    "vmware-aiops",
    "vmware-monitor",
    "vmware-storage",
    "vmware-vks",
    "vmware-nsx",
    "vmware-nsx-security",
    "vmware-aria",
    "vmware-avi",
    "vmware-harden",
    "vmware-pilot",
)
