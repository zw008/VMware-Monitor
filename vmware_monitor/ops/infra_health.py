"""Infrastructure health: certificates, licenses, NTP/time config (read-only).

These three areas cause silent, scheduled outages: an expired ESXi certificate
drops host management, an expired license disables features, and unsynced time
breaks Kerberos / vCenter SSO / log correlation. None are covered by inventory
or perf monitoring.

All read-only. Remediation (renew cert, assign license, fix NTP) is a write
operation owned by vmware-aiops / vSphere admin tooling, not this skill.

Honesty note on NTP: the vSphere SOAP API exposes NTP *configuration* (which
servers, is ntpd running) but NOT the live clock offset / stratum — that
requires `esxcli system ntp test` or host SSH, which this read-only skill does
not do. We report configuration health and say so, rather than inventing an
offset number.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pyVmomi import vim
from vmware_policy import sanitize

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

# Days-until-expiry below which a certificate/license is flagged.
CERT_WARN_DAYS = 30


def _get_objects(si: ServiceInstance, obj_type: list) -> list:
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(content.rootFolder, obj_type, True)
    try:
        return list(container.view)
    finally:
        container.Destroy()


def _days_until(when: datetime | None, now: datetime) -> int | None:
    if when is None:
        return None
    w = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return round((w - now).total_seconds() / 86400)


def get_certificate_status(
    si: ServiceInstance,
    warn_days: int = CERT_WARN_DAYS,
    limit: int | None = None,
) -> list[dict]:
    """Per-host ESXi management certificate expiry.

    Uses the API-native ``certificateManager.certificateInfo`` (no PEM parsing,
    no extra dependency). Returns host, not_after, days_until_expiry, and an
    ``expiring`` flag (True when within warn_days or already expired). Sorted
    soonest-to-expire first.

    Args:
        si: vSphere ServiceInstance.
        warn_days: Flag certs expiring within this many days.
        limit: Max number of host rows to return (None = all).
    """
    now = datetime.now(tz=timezone.utc)
    results: list[dict] = []
    for host in _get_objects(si, [vim.HostSystem]):
        cert_mgr = getattr(host.configManager, "certificateManager", None)
        info = getattr(cert_mgr, "certificateInfo", None) if cert_mgr else None
        not_after = getattr(info, "notAfter", None) if info else None
        days = _days_until(not_after, now)
        results.append(
            {
                "host": sanitize(host.name),
                "not_after": str(not_after) if not_after else "unknown",
                "days_until_expiry": days,
                "expiring": bool(days is not None and days <= warn_days),
            }
        )
    results.sort(key=lambda x: (x["days_until_expiry"] is None, x["days_until_expiry"] or 0))
    if limit is not None:
        results = results[:limit]
    return results


def get_license_status(si: ServiceInstance) -> list[dict]:
    """vCenter/ESXi license inventory with usage and expiry.

    Returns one row per license: name, edition_key, total/used units, and any
    expiration property the server exposes. ``total = 0`` means unlimited.
    """
    content = si.RetrieveContent()
    lic_mgr = content.licenseManager
    results: list[dict] = []
    for lic in lic_mgr.licenses:
        props = {p.key: p.value for p in (lic.properties or [])}
        expiry = props.get("expirationDate") or props.get("expirationHours")
        results.append(
            {
                "name": sanitize(lic.name),
                "edition_key": sanitize(str(lic.editionKey)) if lic.editionKey else "N/A",
                "total": lic.total,
                "used": lic.used if lic.used is not None else 0,
                "unlimited": lic.total == 0,
                "expiration": sanitize(str(expiry)) if expiry else "never",
            }
        )
    return sorted(results, key=lambda x: x["name"])


def get_ntp_status(
    si: ServiceInstance,
    host_name: str | None = None,
) -> list[dict]:
    """Per-host NTP configuration health (config + service state).

    Returns host, ntp_servers (configured), ntpd_running, ntpd_policy, and a
    ``healthy`` flag (servers configured AND ntpd running). The live clock
    offset is NOT included — see module docstring; the SOAP API does not expose
    it. A healthy=False here means "NTP is misconfigured", which is the
    actionable signal users actually need.

    Args:
        si: vSphere ServiceInstance.
        host_name: Filter to a single host by exact name (None = all hosts).
    """
    results: list[dict] = []
    for host in _get_objects(si, [vim.HostSystem]):
        if host_name and host.name != host_name:
            continue
        dt_info = getattr(host.config, "dateTimeInfo", None) if host.config else None
        ntp_cfg = getattr(dt_info, "ntpConfig", None) if dt_info else None
        servers = list(getattr(ntp_cfg, "server", []) or []) if ntp_cfg else []

        running = False
        policy = "unknown"
        svc_system = getattr(host.configManager, "serviceSystem", None)
        if svc_system and svc_system.serviceInfo:
            for svc in svc_system.serviceInfo.service:
                if svc.key == "ntpd":
                    running = svc.running
                    policy = svc.policy
                    break

        results.append(
            {
                "host": sanitize(host.name),
                "ntp_servers": [sanitize(s) for s in servers],
                "ntpd_running": running,
                "ntpd_policy": policy,
                "healthy": bool(servers and running),
                "note": "live clock offset not exposed by SOAP API; reports config only",
            }
        )
    return sorted(results, key=lambda x: x["host"])
