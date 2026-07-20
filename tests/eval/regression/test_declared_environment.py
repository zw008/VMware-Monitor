"""The environment resolver is registered, and reads are never gated by it.

Regression source: vmware-policy scopes rules by environment ("irreversible
work in production needs a second person"), but ``env`` used to be derived from
the *target's name*. Nobody names a vCenter target the literal string
``production`` — they name it ``prod-vcenter`` — so every environment-scoped
rule was configured and inert. The environment is now an explicit declaration
in config.yaml::

    targets:
      - name: prod-vcenter
        host: vcenter.corp.local
        environment: production   # <- declares which rules apply

This skill has zero write tools, so the requirement gates nothing it exposes.
That is exactly why the registration needs pinning here: there is no denial to
notice if it silently goes missing. An unregistered resolver reads every target
as undeclared — the same silence this whole change exists to eliminate — and
the operator cannot fix it by editing config. The sister repos (aiops, storage)
pin the enforcement half against their own write tools.

The other half is a guarantee: read-only inspection must keep working untouched
under every setting of the requirement, including the enforcing one the next
major release ships. A monitoring skill that stops answering because a target
is unlabelled would be the worst possible outcome of a safety control.
"""

import pytest
from vmware_policy.budget import reset_budget
from vmware_policy.environment import resolve_environment, set_environment_resolver
from vmware_policy.policy import reset_policy_engine

from vmware_monitor.config import AppConfig, TargetConfig

import vmware_monitor.mcp_server.server as server


@pytest.fixture(autouse=True)
def baseline(tmp_path, monkeypatch):
    """Point harness state at a tmp dir; no rules.yaml means the shipped baseline.

    That baseline is currently in its warn-only migration setting, so this is
    what an operator who has written no rules of their own gets today.
    """
    monkeypatch.setenv("OPS_HOME", str(tmp_path))
    monkeypatch.delenv("VMWARE_AUDIT_APPROVED_BY", raising=False)
    reset_policy_engine()
    reset_budget()
    yield
    # Restore the registration the server made at import, not None — leaving it
    # cleared would hand the rest of the session the unwired state these tests
    # exist to forbid.
    set_environment_resolver(server._environment_for)
    reset_policy_engine()
    reset_budget()


@pytest.fixture
def enforcing(tmp_path):
    """The same requirement switched on, as the next major release ships it."""
    (tmp_path / "rules.yaml").write_text("require_declared_environment: true\n")
    reset_policy_engine()


def _declare(monkeypatch, environment: str) -> None:
    """Register the real server resolver over a config declaring ``environment``."""
    config = AppConfig(
        targets=(
            TargetConfig(
                name="prod-vcenter",
                host="vcenter.example.com",
                config_username="administrator@vsphere.local",
                environment=environment,
            ),
        )
    )
    # Patch the mtime-cached loader the registered resolver calls, so the
    # resolver under test is the one the server actually installed — not a
    # stand-in.
    monkeypatch.setattr(server, "_cached_config", lambda: config)
    set_environment_resolver(server._environment_for)


@pytest.fixture
def stub_vcenter(monkeypatch):
    """Neutralise the vSphere calls; policy runs before the body either way."""
    monkeypatch.setattr(server, "_get_connection", lambda target=None: object())
    monkeypatch.setattr(
        server, "list_vms", lambda si, **kwargs: {"total": 1, "vms": [{"name": "web-01"}]}
    )


# ---------------------------------------------------------------------------
# The resolver is registered at all
# ---------------------------------------------------------------------------


def test_server_registers_an_environment_resolver(monkeypatch):
    """The silent-failure mode this change exists to remove.

    This skill exposes no write tool, so nothing here would fail visibly if the
    registration were dropped — it would simply report every target as
    undeclared forever. Assert it directly.
    """
    _declare(monkeypatch, "lab")
    assert resolve_environment("prod-vcenter") == "lab"


def test_declared_production_reaches_the_policy_layer(monkeypatch):
    """The declaration, not the target's name, is what policy sees."""
    _declare(monkeypatch, "production")
    assert resolve_environment("prod-vcenter") == "production"


def test_undeclared_target_resolves_to_empty(monkeypatch):
    _declare(monkeypatch, "")
    assert resolve_environment("prod-vcenter") == ""


def test_unknown_target_resolves_to_empty(monkeypatch):
    _declare(monkeypatch, "lab")
    assert resolve_environment("some-other-vcenter") == ""


def test_omitted_target_falls_back_to_the_default_target(monkeypatch):
    """Tools take ``target`` as optional; the default target's label must apply."""
    _declare(monkeypatch, "lab")
    assert resolve_environment("") == "lab"


# ---------------------------------------------------------------------------
# Reads are never gated, under any setting of the requirement
# ---------------------------------------------------------------------------


def test_read_against_undeclared_target_works(monkeypatch, stub_vcenter):
    """Inspection must keep working with no config change at all."""
    _declare(monkeypatch, "")
    assert server.list_virtual_machines(target="prod-vcenter")["total"] == 1


def test_read_against_undeclared_target_works_when_enforcing(
    monkeypatch, enforcing, stub_vcenter
):
    """The enforcing release must not turn a monitoring skill off."""
    _declare(monkeypatch, "")
    assert server.list_virtual_machines(target="prod-vcenter")["total"] == 1


def test_read_against_declared_target_works_when_enforcing(
    monkeypatch, enforcing, stub_vcenter
):
    _declare(monkeypatch, "lab")
    assert server.list_virtual_machines(target="prod-vcenter")["total"] == 1


def test_read_with_no_resolver_registered_still_works(stub_vcenter, enforcing):
    """Fail-closed applies to writes only — an unwired skill still reports."""
    set_environment_resolver(None)
    assert server.list_virtual_machines(target="prod-vcenter")["total"] == 1
