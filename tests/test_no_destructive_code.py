"""Tests to verify zero destructive code paths exist in vmware_monitor package.

This is the most critical test — it ensures code-level safety by verifying
that no destructive operations exist anywhere in the codebase.
"""

import subprocess

import pytest

# Patterns that indicate actual destructive code (function definitions and API calls)
DESTRUCTIVE_PATTERNS = [
    "def power_on",
    "def power_off",
    "def reset_vm",
    "def suspend_vm",
    "def delete_vm",
    "def create_vm",
    "def reconfigure_vm",
    "def clone_vm",
    "def migrate_vm",
    "def create_snapshot",
    "def revert_to_snapshot",
    "def delete_snapshot",
    "PowerOn()",
    "PowerOff()",
    "Destroy_Task()",
    "CreateVM_Task(",
    "ReconfigVM_Task(",
    "RevertToSnapshot_Task(",
    "RemoveSnapshot_Task(",
    "CreateSnapshot_Task(",
    "ShutdownGuest()",
    "vm.Reset()",
    "vm.Suspend()",
    "vm.Relocate(",
    "vm.Clone(",
    "ResetVM_Task(",
    "SuspendVM_Task(",
    "CreateSnapshotEx_Task(",
    "MigrateVM_Task(",
    "RelocateVM_Task(",
    "_double_confirm",
    "_validate_vm_params",
    "_show_state_preview",
]


@pytest.mark.unit
def test_no_destructive_code_in_vmware_monitor() -> None:
    """Verify no destructive function definitions or API calls in vmware_monitor/."""
    for pattern in DESTRUCTIVE_PATTERNS:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", pattern, "vmware_monitor/"],
            capture_output=True,
            text=True,
            cwd="/Users/zw/testany/VMware-Monitor",
        )
        assert result.stdout == "", (
            f"Destructive pattern '{pattern}' found in vmware_monitor/:\n{result.stdout}"
        )


@pytest.mark.unit
def test_no_destructive_code_in_mcp_server() -> None:
    """Verify no destructive function definitions or API calls in mcp_server/."""
    for pattern in DESTRUCTIVE_PATTERNS:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", pattern, "mcp_server/"],
            capture_output=True,
            text=True,
            cwd="/Users/zw/testany/VMware-Monitor",
        )
        assert result.stdout == "", (
            f"Destructive pattern '{pattern}' found in mcp_server/:\n{result.stdout}"
        )
