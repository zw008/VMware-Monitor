"""Tests for the ``folder_filter`` parameter on :func:`list_vms`.

Covers the case-insensitive substring match against folder_path added in
v1.5.21 (community PR #11) and now exposed via CLI ``--folder-filter`` flag
in v1.5.29.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vmware_monitor.ops.inventory import list_vms


def _fake_vm(name: str, folder_path: str, power: str = "poweredOn") -> MagicMock:
    """Build a pyVmomi VM stub that ``list_vms`` enrichment can handle.

    We bypass the real folder-walking helper by patching ``folder_path``
    in the test; this VM only needs the attributes ``_enrich_vm`` reads.
    """
    vm = MagicMock()
    vm.name = name
    vm.runtime.powerState = power
    vm.config.hardware.numCPU = 2
    vm.config.hardware.memoryMB = 4096
    vm.config.guestFullName = "Other Linux (64-bit)"
    vm.guest.ipAddress = None
    # mark with folder_path on the mock so the patched helper can return it
    vm._fake_folder_path = folder_path
    return vm


@pytest.fixture
def fake_vms() -> list[MagicMock]:
    """Five VMs spread across a Production / Staging / DR folder tree."""
    return [
        _fake_vm("web-prod-01", "/Datacenters/Production/Web Tier"),
        _fake_vm("db-prod-01", "/Datacenters/Production/DB Tier"),
        _fake_vm("web-staging-01", "/Datacenters/Staging/Web Tier"),
        _fake_vm("orphan-01", "/"),
        _fake_vm("dr-replica-01", "/Datacenters/DR Site/Replicas"),
    ]


@pytest.fixture
def patched_helpers(fake_vms):
    """Patch _get_objects to return our fake VMs and folder_path to read the
    pre-baked path off each mock."""
    with (
        patch(
            "vmware_monitor.ops.inventory._get_objects",
            return_value=fake_vms,
        ),
        patch(
            "vmware_monitor.ops.inventory.folder_path",
            side_effect=lambda vm: vm._fake_folder_path,
        ),
    ):
        yield


def test_folder_filter_none_returns_all(patched_helpers):
    """No filter → all 5 VMs."""
    result = list_vms(si=MagicMock(), folder_filter=None)
    assert result["total"] == 5


def test_folder_filter_matches_prefix(patched_helpers):
    """Filter on 'Production' returns the 2 Production VMs."""
    result = list_vms(si=MagicMock(), folder_filter="Production")
    names = sorted(v["name"] for v in result["vms"])
    assert names == ["db-prod-01", "web-prod-01"]
    assert result["total"] == 2


def test_folder_filter_is_case_insensitive(patched_helpers):
    """Lowercase 'production' matches '/Datacenters/Production/...'."""
    result = list_vms(si=MagicMock(), folder_filter="production")
    assert result["total"] == 2


def test_folder_filter_substring_anywhere(patched_helpers):
    """Substring 'DR' matches '/Datacenters/DR Site/Replicas'."""
    result = list_vms(si=MagicMock(), folder_filter="DR Site")
    assert result["total"] == 1
    assert result["vms"][0]["name"] == "dr-replica-01"


def test_folder_filter_no_match_returns_empty(patched_helpers):
    """Filter that matches nothing returns total=0, vms=[]."""
    result = list_vms(si=MagicMock(), folder_filter="DoesNotExist")
    assert result["total"] == 0
    assert result["vms"] == []


def test_folder_filter_combines_with_power_state(patched_helpers, fake_vms):
    """folder_filter AND power_state both apply (intersection)."""
    # flip one prod VM to off so we have 1 powered-off Production VM
    fake_vms[1].runtime.powerState = "poweredOff"
    result = list_vms(
        si=MagicMock(),
        folder_filter="Production",
        power_state="poweredOff",
    )
    assert result["total"] == 1
    assert result["vms"][0]["name"] == "db-prod-01"


def test_cli_inventory_vms_help_includes_folder_filter():
    """Smoke test: ``inventory vms --help`` must mention ``--folder-filter``."""
    from typer.testing import CliRunner

    from vmware_monitor.cli import app

    result = CliRunner().invoke(app, ["inventory", "vms", "--help"])
    assert result.exit_code == 0, result.output
    assert "--folder-filter" in result.output
