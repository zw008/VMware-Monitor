"""Regression test for active-sessions graceful degradation.

Code review caught a wrong exception class (`vmodl.fault.NoPermission`, which
does not exist — it is `vim.fault.NoPermission`). With the wrong class, a
low-privilege account hitting the sessionList permission error would make the
`except` clause itself raise AttributeError, defeating the documented
"return one explanatory row instead of a traceback" behaviour. This test pins
the corrected path.
"""

from __future__ import annotations

from pyVmomi import vim

from vmware_monitor.ops.activity import get_active_sessions


class _DeniedSessionMgr:
    @property
    def currentSession(self):  # noqa: N802 — pyVmomi naming
        return None

    @property
    def sessionList(self):  # noqa: N802 — pyVmomi naming
        raise vim.fault.NoPermission()


class _FakeContent:
    sessionManager = _DeniedSessionMgr()


class _FakeSI:
    def RetrieveContent(self):  # noqa: N802 — pyVmomi naming
        return _FakeContent()


def test_active_sessions_no_permission_returns_explanatory_row():
    rows = get_active_sessions(_FakeSI())
    assert len(rows) == 1
    assert "Sessions privilege" in rows[0]["note"]
    assert rows[0]["user_name"] == "N/A"
