"""A teaching message the agent never sees is not a teaching message.

``_safe_error`` reduces unrecognised exceptions to ``"<Class>: operation
failed."`` so raw vSphere text cannot leak. Its allowlist held only the builtin
validation errors, so all three exceptions this skill defines for its own domain
— ``VMNotFoundError``, ``HostNotFoundError``, ``DatastoreNotFoundError`` — had
their messages replaced by their class names on the way to the agent.

Those three cover the most common failure this skill has: a name that does not
resolve. They exist precisely to say which listing tool produces a valid name,
and that sentence was being thrown away at the last step. The CLI printed it in
full and the error-quality eval read it at the raise site, so nothing measured
what actually arrived.

``OSError`` was the same defect one layer earlier, and survived the first fix:
``config.py`` raises exactly one — the missing-password error, this family's
most common *first-run* failure — and its whole remedy is the ``.env`` path and
env var name it carries. An agent hitting an unconfigured target received
``OSError: operation failed.`` and had nothing to act on.
"""

from __future__ import annotations

import pytest

from vmware_monitor.mcp_server.server import _safe_error
from vmware_monitor.ops.investigate_datastore import DatastoreNotFoundError
from vmware_monitor.ops.investigate_host import HostNotFoundError
from vmware_monitor.ops.vm_info import VMNotFoundError

TEACHING = "VM 'web-99' not found. Run list_virtual_machines and copy an exact name."

ENV_KEY = "VMWARE_VCENTER_PROD_PASSWORD"
MISSING_PASSWORD = (
    f"Password not found. Add it to ~/.vmware-monitor/.env (chmod 600) "
    f"or set the environment variable: {ENV_KEY}"
)


def test_missing_password_keeps_the_env_var_name():
    """The single OSError config.py raises — and the whole point of it is the name."""
    out = _safe_error(OSError(MISSING_PASSWORD), "list_virtual_machines")
    assert ENV_KEY in out
    assert "operation failed" not in out


@pytest.mark.parametrize(
    "exc_type", [VMNotFoundError, HostNotFoundError, DatastoreNotFoundError]
)
def test_domain_exceptions_keep_their_message(exc_type):
    assert _safe_error(exc_type(TEACHING), "vm_info") == TEACHING


@pytest.mark.parametrize("exc_type", [ValueError, FileNotFoundError, KeyError, PermissionError])
def test_validation_errors_still_pass_through(exc_type):
    assert "web-99" in _safe_error(exc_type(TEACHING), "t")


def test_dropped_connection_surfaces_its_hint():
    assert "retry" in _safe_error(ConnectionError("Connection lost — retry the operation."), "t")


def test_unplanned_exceptions_are_still_reduced():
    """The redaction this allowlist exists for has to keep working."""
    out = _safe_error(RuntimeError("https://admin:hunter2@vc.internal/api/task-42"), "t")
    assert out == "RuntimeError: operation failed."
    assert "hunter2" not in out


def test_message_is_still_truncated():
    assert len(_safe_error(VMNotFoundError("x" * 900), "t")) <= 300
