"""Cross-vCenter "what needs attention now?" — one ranked list across all targets.

The top level of the object-investigation family (GitHub issue #31 follow-up):
instead of a per-vCenter glance, roll every configured vCenter's cluster-health
summary into a single, globally-ranked ``top_issues`` list — the "where do I look
first, anywhere in the estate?" view. Aggregation happens in the tool; the model
explains the ranked result in operational language and never sees raw inventory.

One dead vCenter must not sink the roll-up: the connection layer resolves targets
into reachable sessions + an ``unreachable`` list (see ``ConnectionManager.
connect_all``), and this aggregator additionally tolerates a target that connects
but errors mid-summary — it is moved to ``unreachable`` and the rest proceed.

Read-only. Point-in-time — no trend is invented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vmware_monitor.ops.cluster_summary import _rank_issues, get_cluster_health_summary

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

# Per-target we want ALL anomalies (not a per-target top-N) so the global ranking
# is faithful; this cap only guards against a pathologically huge single target.
_PER_TARGET_ISSUE_CAP = 100000

_STATUS_ORDER = {"critical": 0, "warn": 1, "ok": 2}

CUSTOMIZATION_HINT = (
    "Want a different cut? Just ask — e.g. "
    '"only critical issues", "group by vCenter", "just the prod cluster", '
    'or "render this as an HTML page". Scope, ranking, and grouping are adjustable.'
)


def get_cross_vcenter_attention(
    sessions: list[tuple[str, ServiceInstance]],
    unreachable: list[tuple[str, str]] | None = None,
    cluster_filter: str | None = None,
    top_n: int = 10,
) -> dict:
    """Merge every target's cluster-health into one globally-ranked attention view.

    Args:
        sessions: ``[(target_name, si)]`` for reachable, connected targets.
        unreachable: ``[(target_name, reason)]`` for targets that failed to connect
            (from ``ConnectionManager.connect_all``); merged into the result so the
            gaps are visible.
        cluster_filter: Case-insensitive cluster substring passed through to each
            target's summary (None = all clusters).
        top_n: Cap the merged ``top_issues`` focus list (default 10). ``issues_total``
            always reports the pre-cap count.

    Returns:
        dict with ``targets`` (per-vCenter rollup rows), ``top_issues`` (merged,
        globally ranked, each tagged with its ``vcenter``), ``issues_total``,
        ``totals`` (estate-wide), ``unreachable`` (targets skipped, with reason),
        ``snapshot`` and ``customization_hint``.
    """
    unreachable_out = [{"vcenter": n, "reason": r} for n, r in (unreachable or [])]
    targets: list[dict] = []
    all_issues: list[dict] = []
    totals = {
        "vcenters": 0,
        "clusters": 0,
        "hosts_total": 0,
        "hosts_connected": 0,
        "alarms": {"critical": 0, "warning": 0},
        "worst_status": "ok",
    }

    for name, si in sessions:
        try:
            data = get_cluster_health_summary(
                si, cluster_filter=cluster_filter, top_n=_PER_TARGET_ISSUE_CAP
            )
        except Exception as e:  # noqa: BLE001 — a mid-summary failure degrades, not fails
            unreachable_out.append({"vcenter": name, "reason": type(e).__name__})
            continue

        t = data["totals"]
        worst = t.get("worst_status", "ok")
        targets.append(
            {
                "vcenter": name,
                "worst_status": worst,
                "clusters": t.get("clusters", 0),
                "hosts_connected": t.get("hosts_connected", 0),
                "hosts_total": t.get("hosts_total", 0),
                "alarms": t.get("alarms", {"critical": 0, "warning": 0}),
            }
        )
        for issue in data.get("top_issues", []):
            all_issues.append({**issue, "vcenter": name})

        totals["vcenters"] += 1
        totals["clusters"] += t.get("clusters", 0)
        totals["hosts_total"] += t.get("hosts_total", 0)
        totals["hosts_connected"] += t.get("hosts_connected", 0)
        totals["alarms"]["critical"] += t.get("alarms", {}).get("critical", 0)
        totals["alarms"]["warning"] += t.get("alarms", {}).get("warning", 0)
        if _STATUS_ORDER.get(worst, 2) < _STATUS_ORDER.get(totals["worst_status"], 2):
            totals["worst_status"] = worst

    # Global re-rank across every target's anomalies (reuses the summary ranking).
    top_issues, issues_total = _rank_issues(all_issues, top_n)
    targets.sort(key=lambda r: (_STATUS_ORDER.get(r["worst_status"], 2), r["vcenter"]))

    return {
        "targets": targets,
        "top_issues": top_issues,
        "issues_total": issues_total,
        "totals": totals,
        "unreachable": unreachable_out,
        "snapshot": "point-in-time; not a trend (no history retained)",
        "customization_hint": CUSTOMIZATION_HINT,
    }
