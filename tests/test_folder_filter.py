"""Tests for the ``folder_filter`` parameter on :func:`list_vms`.

Covers the case-insensitive substring match against folder_path added in
v1.5.21 (community PR #11) and now exposed via CLI ``--folder-filter`` flag
in v1.5.29.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vmware_monitor.ops.inventory import list_vms


def _fake_vm(name: str, folder_path: str, power: str = "poweredOn") -> dict:
    """Build the property dict ``list_vms`` sees from PropertyCollector.

    The pre-baked folder path is carried on the ``parent`` property; the patched
    ``_resolve_folder_path`` returns it verbatim, so these tests exercise the
    folder_filter logic without a real inventory tree.
    """
    return {
        "name": name,
        "runtime.powerState": power,
        "config.hardware.numCPU": 2,
        "config.hardware.memoryMB": 4096,
        "config.guestFullName": "Other Linux (64-bit)",
        "guest.ipAddress": None,
        "parent": folder_path,
    }


@pytest.fixture
def fake_vms() -> list[dict]:
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
    """Feed fake VM property dicts through the batched-collection seam.

    ``_collect`` returns the VM props (empty for the host lookup); ``_folder_map``
    is neutralized and ``_resolve_folder_path`` reads the pre-baked path off the
    ``parent`` property.
    """
    from pyVmomi import vim

    def _collect(si, obj_type, paths):
        if obj_type[0] is vim.VirtualMachine:
            return [(MagicMock(), props) for props in fake_vms]
        return []

    with (
        patch("vmware_monitor.ops.inventory._collect", side_effect=_collect),
        patch("vmware_monitor.ops.inventory._folder_map", return_value={}),
        patch(
            "vmware_monitor.ops.inventory._resolve_folder_path",
            side_effect=lambda parent, fmap: parent,
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
    names = sorted(v["name"] for v in result["items"])
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
    assert result["items"][0]["name"] == "dr-replica-01"


def test_folder_filter_no_match_returns_empty(patched_helpers):
    """Filter that matches nothing returns total=0, items=[]."""
    result = list_vms(si=MagicMock(), folder_filter="DoesNotExist")
    assert result["total"] == 0
    assert result["items"] == []


def test_folder_filter_combines_with_power_state(patched_helpers, fake_vms):
    """folder_filter AND power_state both apply (intersection)."""
    # flip one prod VM to off so we have 1 powered-off Production VM
    fake_vms[1]["runtime.powerState"] = "poweredOff"
    result = list_vms(
        si=MagicMock(),
        folder_filter="Production",
        power_state="poweredOff",
    )
    assert result["total"] == 1
    assert result["items"][0]["name"] == "db-prod-01"


def test_cli_inventory_vms_help_includes_folder_filter():
    """Smoke test: ``inventory vms --help`` must mention ``--folder-filter``."""
    from typer.testing import CliRunner

    from vmware_monitor.cli import app

    result = CliRunner().invoke(app, ["inventory", "vms", "--help"])
    assert result.exit_code == 0, result.output
    assert "--folder-filter" in result.output
