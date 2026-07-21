"""Regression — the v1.8.0 envelope renamed ``vms`` to ``items`` in silence.

Source: the v1.8.6 audit of the v1.8.0 envelope conversion.

v1.8.0 wrapped every ``[READ]`` list tool in the family envelope. For the 51
tools that had returned a bare ``list[dict]`` this broke loudly: ``result[0]``
raises ``TypeError``/``KeyError`` on a dict, so the caller finds out on the
first run.

``list_vms`` was not one of those 51. It already returned a keyed dict --
``{total, mode, vms, hint}`` -- so the conversion did not change the *type* of
the payload, only the name of the key holding the rows. A pre-v1.8.0 caller
written as::

    for vm in result.get("vms", []):

kept running and silently saw zero VMs. In a monitoring tool an empty VM list
does not read as a failure; it reads as "there are no VMs". That is the exact
silent-wrong shape the envelope was introduced to prevent, so it is pinned
here rather than left to the release notes.

The fix is a compatibility alias, not a revert: ``items`` remains the primary
key, ``vms`` points at the *same list object*, and it goes away in 2.0. These
tests fail if the alias is dropped before then -- verified by mutation, not
assumed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pyVmomi import vim

from vmware_monitor.ops import inventory

ENVELOPE_KEYS = ("items", "returned", "limit", "total", "truncated", "hint")


def _list_vms(monkeypatch: pytest.MonkeyPatch, n: int, **kwargs) -> dict:
    """Run ``list_vms`` against a fake inventory holding exactly ``n`` VMs.

    ``list_vms`` calls ``_collect`` for hosts, three folder-tree passes, and
    then VMs, so the stub dispatches on the requested type instead of replaying
    one row set into all five calls.
    """
    rows = [(object(), {"name": f"vm-{i:03d}"}) for i in range(n)]
    monkeypatch.setattr(
        inventory,
        "_collect",
        lambda si, obj_type, paths: rows if obj_type[0] is vim.VirtualMachine else [],
    )
    return inventory.list_vms(SimpleNamespace(RetrieveContent=lambda: None), **kwargs)


# ---------------------------------------------------------------------------
# The bug, stated as the caller experienced it
# ---------------------------------------------------------------------------


def test_pre_1_8_0_caller_still_sees_the_vms(monkeypatch: pytest.MonkeyPatch) -> None:
    """``result.get("vms", [])`` must not answer "no VMs" when there are three.

    This is the regression verbatim. The default in ``.get`` is what made the
    break silent, so the assertion is written with the default in place.
    """
    result = _list_vms(monkeypatch, 3)
    assert len(result.get("vms", [])) == 3


def test_vms_is_the_same_object_as_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identity, not equality — a copy would let the two drift apart.

    Two lists that are merely equal today can diverge the moment anything
    post-processes one of them, which would turn one silent break into two.
    """
    result = _list_vms(monkeypatch, 3)
    assert result["vms"] is result["items"]


def test_alias_tracks_items_through_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves the identity above is real rather than incidentally equal."""
    result = _list_vms(monkeypatch, 2)
    result["items"].append({"name": "vm-late"})
    assert result["vms"][-1] == {"name": "vm-late"}
    assert len(result["vms"]) == 3


# ---------------------------------------------------------------------------
# The alias is additive — the envelope stays the primary shape
# ---------------------------------------------------------------------------


def test_envelope_remains_intact(monkeypatch: pytest.MonkeyPatch) -> None:
    """The alias is a compatibility shim, not a revert to the old shape."""
    result = _list_vms(monkeypatch, 3)
    assert set(ENVELOPE_KEYS) <= set(result)
    assert result["returned"] == 3
    assert result["total"] == 3
    assert result["truncated"] is False
    assert result["mode"] == "full"


def test_empty_inventory_is_an_explicit_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A genuinely empty result and a dropped key must stay distinguishable.

    Before the alias both read as ``[]`` through ``.get("vms", [])``. Now the
    key is present and empty, so "no VMs" is a statement rather than an
    artefact of a missing key.
    """
    result = _list_vms(monkeypatch, 0)
    assert "vms" in result
    assert result["vms"] == []
    assert result["returned"] == 0


def test_alias_survives_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A limited page aliases the page, not the pre-limit row set."""
    result = _list_vms(monkeypatch, 10, limit=4)
    assert result["truncated"] is True
    assert len(result["vms"]) == 4
    assert result["vms"] is result["items"]


def test_alias_survives_auto_compact(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-compact rebuilds the row list; the alias must follow the rebuild.

    Over the 50-VM threshold ``list_vms`` replaces every row with a trimmed
    copy. An alias captured before that step would point at the discarded
    full-field rows -- equal in length, wrong in content.
    """
    result = _list_vms(monkeypatch, 60)
    assert result["mode"] == "compact"
    assert result["vms"] is result["items"]
    assert len(result["vms"]) == 60
