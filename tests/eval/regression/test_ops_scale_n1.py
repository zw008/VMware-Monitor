"""Regression — batched PropertyCollector across the ops modules (issue #31 class).

The inventory list/find functions were fixed in ``test_inventory_scale_issue31``;
this file locks the *same* fix into the other inventory-sweeping ops:
``snapshots.list_snapshot_aging``, ``performance.get_vm_performance``, and
``health.get_host_hardware_status``.

Each used to walk a ContainerView and then touch pyVmomi *lazy* properties one
object at a time (``vm.snapshot`` / ``vm.layoutEx`` / ``vm.runtime.powerState``
/ ``host.runtime.healthSystemRuntime`` …) — one SOAP round-trip per property per
object, with ``limit`` applied only after the full collection, so it never
reduced the work. The fix routes every sweep through ``ops._collect._collect``
(a single ``RetrievePropertiesEx`` call, paged via continuation tokens).

The fake managed objects below raise on ANY attribute access, so if the code
ever regresses to touching ``vm.layoutEx`` / ``vm.runtime`` / ``host.runtime``
the test fails loudly rather than silently going slow.
"""

from __future__ import annotations

import types
from datetime import datetime, timedelta, timezone

from pyVmomi import vim

from vmware_monitor.ops import health, performance, snapshots

# --------------------------------------------------------------------------
# Shared fake harness (PropertyCollector + optional PerfManager)
# --------------------------------------------------------------------------

class _FakeStub:
    """Minimal SOAP stub so a real ContainerView moref can be Destroy()'d."""

    def InvokeMethod(self, mo, info, args):  # noqa: N802 - pyVmomi contract
        return None


class _NoLazyMO:
    """Fake managed object: any attribute read is a lazy round-trip = a bug."""

    def __init__(self, label: str) -> None:
        object.__setattr__(self, "_label", label)

    def __getattr__(self, name: str):  # pragma: no cover - only hit on regression
        raise AssertionError(
            f"lazy property access '{name}' on {object.__getattribute__(self, '_label')}"
            " — ops sweeps must use PropertyCollector, not per-object attributes"
        )

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other


class _Prop:
    def __init__(self, name, val) -> None:
        self.name = name
        self.val = val


class _ObjContent:
    def __init__(self, obj, props: dict) -> None:
        self.obj = obj
        self.propSet = [_Prop(k, v) for k, v in props.items()]


class _Batch:
    def __init__(self, objects, token=None) -> None:
        self.objects = objects
        self.token = token


class _FakePropertyCollector:
    """Returns canned ObjectContent keyed by the requested managed-object type."""

    def __init__(self, fixtures: dict, page_size: int = 1000) -> None:
        self._fixtures = fixtures
        self._page_size = page_size
        self._pending: dict[str, list] = {}
        self._counter = 0

    def _pages(self, rows):
        return [rows[i:i + self._page_size] for i in range(0, len(rows), self._page_size)] or [[]]

    def RetrievePropertiesEx(self, specs, options):  # noqa: N802
        obj_type = specs[0].propSet[0].type
        rows = self._fixtures.get(obj_type, [])
        pages = self._pages(rows)
        token = None
        if len(pages) > 1:
            self._counter += 1
            token = f"tok{self._counter}"
            self._pending[token] = pages[1:]
        return _Batch([_ObjContent(o, p) for o, p in pages[0]], token=token)

    def ContinueRetrievePropertiesEx(self, token):  # noqa: N802
        pages = self._pending.pop(token)
        next_token = None
        if len(pages) > 1:
            self._counter += 1
            next_token = f"tok{self._counter}"
            self._pending[next_token] = pages[1:]
        return _Batch([_ObjContent(o, p) for o, p in pages[0]], token=next_token)


class _FakeViewManager:
    def CreateContainerView(self, root, obj_type, recursive):  # noqa: N802
        return vim.view.ContainerView("cv-fake", _FakeStub())


class _FakeContent:
    def __init__(self, pc, perf_manager=None) -> None:
        self.viewManager = _FakeViewManager()
        self.propertyCollector = pc
        self.perfManager = perf_manager
        self.rootFolder = _NoLazyMO("rootFolder")


class _FakeSI:
    def __init__(self, fixtures: dict, perf_manager=None, page_size: int = 1000) -> None:
        self._content = _FakeContent(_FakePropertyCollector(fixtures, page_size), perf_manager)

    def RetrieveContent(self):  # noqa: N802
        return self._content


def _si(fixtures, perf_manager=None, page_size=1000):
    return _FakeSI(fixtures, perf_manager, page_size)


# --------------------------------------------------------------------------
# snapshots.list_snapshot_aging — name/snapshot/layoutEx all batched
# --------------------------------------------------------------------------

class _SnapTree:
    def __init__(self, name, created, children=None, description="") -> None:
        self.name = name
        self.description = description
        self.createTime = created
        self.childSnapshotList = children or []


class _SnapInfo:
    def __init__(self, roots) -> None:
        self.rootSnapshotList = roots


class _LayoutFile:
    def __init__(self, ftype, size) -> None:
        self.type = ftype
        self.size = size


class _Layout:
    def __init__(self, files) -> None:
        self.file = files


def test_list_snapshot_aging_batches_snapshot_and_layoutex():
    now = datetime.now(tz=timezone.utc)
    old = now - timedelta(days=45)
    layout = _Layout([
        _LayoutFile("snapshotData", 100 * 1024 * 1024),
        _LayoutFile("snapshotMemory", 50 * 1024 * 1024),
        _LayoutFile("diskDescriptor", 999 * 1024 * 1024),  # not snapshot — ignored
    ])
    fixtures = {
        vim.VirtualMachine: [
            (
                _NoLazyMO("vm:app-01"),
                {
                    "name": "app-01",
                    "snapshot": _SnapInfo([_SnapTree("snap-1", old)]),
                    "layoutEx": layout,
                },
            ),
            # VM without a snapshot: skipped, and its lazy attrs never touched.
            (_NoLazyMO("vm:no-snap"), {"name": "no-snap", "snapshot": None}),
        ]
    }
    result = snapshots.list_snapshot_aging(_si(fixtures))

    assert result["total_snapshots"] == 1
    assert result["vms_with_snapshots"] == 1
    assert result["old_snapshots"] == 1
    row = result["snapshots"][0]
    assert row["vm_name"] == "app-01"
    assert row["snapshot_name"] == "snap-1"
    assert row["is_old"] is True
    # layoutEx read from the batched prop, not lazily off the VM object.
    assert row["est_size_mb"] == 150.0


def test_list_snapshot_aging_only_old_filter():
    now = datetime.now(tz=timezone.utc)
    fixtures = {
        vim.VirtualMachine: [
            (
                _NoLazyMO("vm:mix"),
                {
                    "name": "mix",
                    "snapshot": _SnapInfo([
                        _SnapTree("recent", now - timedelta(days=2)),
                        _SnapTree("stale", now - timedelta(days=90)),
                    ]),
                    "layoutEx": None,
                },
            ),
        ]
    }
    result = snapshots.list_snapshot_aging(_si(fixtures), only_old=True)
    assert result["total_snapshots"] == 2       # total counts all before filter
    assert [r["snapshot_name"] for r in result["snapshots"]] == ["stale"]


# --------------------------------------------------------------------------
# performance.get_vm_performance — name/powerState batched, QueryPerf driven
# --------------------------------------------------------------------------

class _FakeCounter:
    def __init__(self, group, name, rollup, key) -> None:
        self.groupInfo = types.SimpleNamespace(key=group)
        self.nameInfo = types.SimpleNamespace(key=name)
        self.rollupType = rollup
        self.key = key


class _FakeMetric:
    def __init__(self, counter_id, values) -> None:
        self.id = types.SimpleNamespace(counterId=counter_id)
        self.value = values


class _FakePerfResult:
    def __init__(self, metrics) -> None:
        self.value = metrics


class _FakePerfManager:
    def __init__(self) -> None:
        self.perfCounter = [
            _FakeCounter("cpu", "usage", "average", 1),
            _FakeCounter("mem", "usage", "average", 2),
        ]

    def QueryPerfProviderSummary(self, entity):  # noqa: N802
        return types.SimpleNamespace(currentSupported=True, refreshRate=20)

    def QueryPerf(self, querySpec):  # noqa: N802, N803 - pyVmomi contract
        # cpu.usage.average (counterId 1): 5000 hundredths-of-% → 50.0%
        return [_FakePerfResult([_FakeMetric(1, [5000, 5000])])]


class _RaisingStub:
    """SOAP stub that raises on any invoked method — i.e. any lazy property read.

    ``vim.PerformanceManager.QuerySpec`` requires a real ManagedObject for its
    ``entity`` field, so the perf entities must be genuine vim proxies (not
    ``_NoLazyMO``). Constructing the QuerySpec only stores the reference; an
    actual lazy attribute access would go through ``InvokeMethod`` and blow up.
    """

    def InvokeMethod(self, mo, info, args):  # noqa: N802 - pyVmomi contract
        raise AssertionError(
            "lazy SOAP property access on a perf entity — get_vm_performance must"
            " read name/powerState from PropertyCollector, not the VM object"
        )


def _vm_proxy(moid: str) -> vim.VirtualMachine:
    return vim.VirtualMachine(moid, _RaisingStub())


def test_get_vm_performance_skips_powered_off_without_lazy_access():
    fixtures = {
        vim.VirtualMachine: [
            (_vm_proxy("vm-web-01"), {"name": "web-01", "runtime.powerState": "poweredOn"}),
            (_vm_proxy("vm-web-02"), {"name": "web-02", "runtime.powerState": "poweredOff"}),
        ]
    }
    rows = performance.get_vm_performance(_si(fixtures, perf_manager=_FakePerfManager()))
    assert len(rows) == 1                     # powered-off skipped via batched prop
    assert rows[0]["name"] == "web-01"
    assert rows[0]["cpu_usage_pct"] == 50.0


def test_get_vm_performance_name_filter():
    fixtures = {
        vim.VirtualMachine: [
            (_vm_proxy("vm-a"), {"name": "a", "runtime.powerState": "poweredOn"}),
            (_vm_proxy("vm-b"), {"name": "b", "runtime.powerState": "poweredOn"}),
        ]
    }
    rows = performance.get_vm_performance(
        _si(fixtures, perf_manager=_FakePerfManager()), vm_name="b"
    )
    assert [r["name"] for r in rows] == ["b"]


# --------------------------------------------------------------------------
# health.get_host_hardware_status — name/healthSystemRuntime batched
# --------------------------------------------------------------------------

class _Sensor:
    def __init__(self, name, stype, reading, unit, health_key) -> None:
        self.name = name
        self.sensorType = stype
        self.currentReading = reading
        self.baseUnits = unit
        self.healthState = types.SimpleNamespace(key=health_key)


class _SysHealth:
    def __init__(self, sensors) -> None:
        self.numericSensorInfo = sensors


class _RuntimeHealth:
    def __init__(self, system_health_info) -> None:
        self.systemHealthInfo = system_health_info


def test_get_host_hardware_status_batches_health_runtime():
    rh = _RuntimeHealth(_SysHealth([
        _Sensor("CPU Temp", "temperature", 42, "degrees C", "green"),
    ]))
    fixtures = {
        vim.HostSystem: [
            (_NoLazyMO("host:esx-01"), {"name": "esx-01", "runtime.healthSystemRuntime": rh}),
            # No health runtime: skipped, lazy attrs never touched.
            (_NoLazyMO("host:esx-02"), {"name": "esx-02", "runtime.healthSystemRuntime": None}),
        ]
    }
    rows = health.get_host_hardware_status(_si(fixtures))
    assert len(rows) == 1
    assert rows[0]["host"] == "esx-01"
    assert rows[0]["sensor_name"] == "CPU Temp"
    assert rows[0]["status"] == "green"
    assert rows[0]["reading"] == 42
