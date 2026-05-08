"""Tests for the folder_path helper in vmware_monitor.ops.inventory."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pyVmomi import vim

from vmware_monitor.ops.inventory import folder_path


def _mock_entity(name: str, parent=None, spec=vim.Folder):
    """Build a MagicMock that ``isinstance`` will treat as ``spec``."""
    m = MagicMock(spec=spec)
    m.name = name
    m.parent = parent
    return m


def test_folder_path_root_vmfolder_returns_slash():
    """A VM sitting directly in the dc-level vmFolder yields '/'."""
    dc = _mock_entity("UAA Datacenter", spec=vim.Datacenter)
    vmfolder = _mock_entity("vm", parent=dc, spec=vim.Folder)
    vm = _mock_entity("anc-orphan", parent=vmfolder, spec=vim.VirtualMachine)

    assert folder_path(vm) == "/"


def test_folder_path_one_level():
    """One folder under the vmFolder."""
    dc = _mock_entity("UAA Datacenter", spec=vim.Datacenter)
    vmfolder = _mock_entity("vm", parent=dc, spec=vim.Folder)
    colo = _mock_entity("Colocation", parent=vmfolder, spec=vim.Folder)
    vm = _mock_entity("anc-iser-app01", parent=colo, spec=vim.VirtualMachine)

    assert folder_path(vm) == "/Colocation"


def test_folder_path_nested_subfolders():
    """Two-level nesting under the vmFolder."""
    dc = _mock_entity("UAA Datacenter", spec=vim.Datacenter)
    vmfolder = _mock_entity("vm", parent=dc, spec=vim.Folder)
    colo = _mock_entity("Colocation", parent=vmfolder, spec=vim.Folder)
    iser = _mock_entity("Colo - ISER", parent=colo, spec=vim.Folder)
    vm = _mock_entity("anc-iser-app01", parent=iser, spec=vim.VirtualMachine)

    assert folder_path(vm) == "/Colocation/Colo - ISER"


def test_folder_path_ignores_datacenter_name():
    """Datacenter name is never part of the path."""
    dc = _mock_entity("Some Other DC", spec=vim.Datacenter)
    vmfolder = _mock_entity("vm", parent=dc, spec=vim.Folder)
    colo = _mock_entity("Colocation", parent=vmfolder, spec=vim.Folder)
    vm = _mock_entity("anc-iser-app01", parent=colo, spec=vim.VirtualMachine)

    result = folder_path(vm)
    assert "Some Other DC" not in result
    assert result == "/Colocation"


def test_folder_path_no_parent_chain():
    """A VM with no parent at all returns '/'."""
    vm = SimpleNamespace(parent=None)

    assert folder_path(vm) == "/"
