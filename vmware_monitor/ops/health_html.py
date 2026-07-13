"""Render a cluster-health snapshot as a self-contained, offline HTML file.

Takes the dict from ``ops.cluster_summary.get_cluster_health_summary`` and returns
a single standalone HTML document — no external CSS/JS/fonts, so it opens from
``file://`` with nothing leaving the machine (unlike a cloud-hosted artifact,
which would upload internal host/cluster names). This is the "make it tangible
for stakeholders" view; it is a **point-in-time snapshot**, not a live page.

Every value that originates from vSphere (cluster/host names, alarm names) is
HTML-escaped here — the ops layer's ``sanitize`` strips control characters but
does not neutralise markup, so escaping at render time is what prevents a crafted
VM/cluster name from injecting into the page.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

# Darker slate palette, theme-aware (light + dark), semantic severity colours
# kept separate from the accent hue. Mirrors the reviewed sample exactly.
_CSS = """
  :root {
    --ground:#d7dde7; --surface:#eef2f7; --surface-2:#e4e9f1; --ink:#131a26;
    --muted:#4d5a6e; --faint:#74839a; --border:#cbd3e0; --accent:#1f5698;
    --crit:#bf283f; --crit-bg:#f4dde1; --warn:#9c6207; --warn-bg:#f4e7cf;
    --ok:#237a4b; --ok-bg:#dcefe3; --meter-track:#d3dae6;
    --shadow:0 1px 2px rgba(23,35,54,.06),0 2px 8px rgba(23,35,54,.05);
    --mono:ui-monospace,"SF Mono","SFMono-Regular",Menlo,Consolas,monospace;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }
  @media (prefers-color-scheme:dark){:root{
    --ground:#070b12; --surface:#0f1723; --surface-2:#141d2b; --ink:#e7edf6;
    --muted:#8c9bb1; --faint:#63728a; --border:#202a38; --accent:#6aa6df;
    --crit:#f2647c; --crit-bg:#2e1620; --warn:#e0a44a; --warn-bg:#2c2210;
    --ok:#5cca8c; --ok-bg:#0e2c1f; --meter-track:#212b3a;
    --shadow:0 1px 2px rgba(0,0,0,.35),0 2px 10px rgba(0,0,0,.3);
  }}
  :root[data-theme="light"]{
    --ground:#d7dde7; --surface:#eef2f7; --surface-2:#e4e9f1; --ink:#131a26;
    --muted:#4d5a6e; --faint:#74839a; --border:#cbd3e0; --accent:#1f5698;
    --crit:#bf283f; --crit-bg:#f4dde1; --warn:#9c6207; --warn-bg:#f4e7cf;
    --ok:#237a4b; --ok-bg:#dcefe3; --meter-track:#d3dae6;
  }
  :root[data-theme="dark"]{
    --ground:#070b12; --surface:#0f1723; --surface-2:#141d2b; --ink:#e7edf6;
    --muted:#8c9bb1; --faint:#63728a; --border:#202a38; --accent:#6aa6df;
    --crit:#f2647c; --crit-bg:#2e1620; --warn:#e0a44a; --warn-bg:#2c2210;
    --ok:#5cca8c; --ok-bg:#0e2c1f; --meter-track:#212b3a;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
    line-height:1.5;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1080px;margin:0 auto;padding:32px 24px 56px}
  header{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px}
  .eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);font-weight:600}
  h1{font-size:26px;margin:2px 0 0;font-weight:680;letter-spacing:-.01em;text-wrap:balance;width:100%}
  h1 .vc{color:var(--accent)}
  .stamp{font-family:var(--mono);font-size:12.5px;color:var(--muted)}
  .overall{margin-left:auto;align-self:center;display:inline-flex;align-items:center;gap:8px;
    font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase;
    padding:7px 14px;border-radius:999px;border:1px solid transparent}
  .overall.crit{color:var(--crit);background:var(--crit-bg);border-color:color-mix(in srgb,var(--crit) 30%,transparent)}
  .overall.warn{color:var(--warn);background:var(--warn-bg);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}
  .overall.ok{color:var(--ok);background:var(--ok-bg);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}
  .overall .dot{width:8px;height:8px;border-radius:50%;background:currentColor}
  .totals{display:grid;grid-template-columns:repeat(var(--tc,4),1fr);gap:1px;background:var(--border);
    border:1px solid var(--border);border-radius:12px;overflow:hidden;margin:20px 0 32px;box-shadow:var(--shadow)}
  .totals .cell{background:var(--surface);padding:14px 16px}
  .totals .k{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint)}
  .totals .v{font-family:var(--mono);font-size:21px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums}
  .totals .v small{font-size:13px;color:var(--muted);font-weight:400}
  .totals .v .c{color:var(--crit)} .totals .v .w{color:var(--warn)}
  .section-label{font-size:12px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;
    color:var(--muted);margin:0 0 12px;display:flex;align-items:baseline;gap:8px}
  .section-label .count{font-family:var(--mono);color:var(--faint);font-weight:500;letter-spacing:0}
  .issues{display:flex;flex-direction:column;gap:8px;margin-bottom:36px}
  .issue{display:grid;grid-template-columns:26px 92px 1fr auto;gap:4px 14px;align-items:center;
    background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--sev);
    border-radius:10px;padding:12px 16px 12px 15px;box-shadow:var(--shadow)}
  .issue.crit{--sev:var(--crit)} .issue.warn{--sev:var(--warn)}
  .issue .rank{font-family:var(--mono);font-size:13px;color:var(--faint);text-align:right;font-variant-numeric:tabular-nums}
  .chip{font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
    padding:3px 9px;border-radius:6px;text-align:center;white-space:nowrap}
  .chip.crit{color:var(--crit);background:var(--crit-bg)} .chip.warn{color:var(--warn);background:var(--warn-bg)}
  .issue .what{min-width:0} .issue .prob{font-weight:600;font-size:14.5px}
  .issue .obj{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:2px}
  .issue .obj b{color:var(--ink);font-weight:600}
  .issue .next{font-family:var(--mono);font-size:11.5px;color:var(--faint);text-align:right;max-width:260px}
  .issue .next .arrow{color:var(--accent)}
  @media (max-width:720px){.issue{grid-template-columns:26px 1fr}
    .issue .chip{grid-column:2;justify-self:start} .issue .next{grid-column:2;text-align:left;max-width:none}}
  .clean-all{background:var(--surface);border:1px solid var(--border);border-radius:10px;
    padding:16px;color:var(--ok);font-weight:600;box-shadow:var(--shadow);margin-bottom:36px}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}
  .card>.top{display:flex;align-items:center;gap:10px;padding:14px 16px;
    border-bottom:1px solid var(--border);border-top:3px solid var(--sev)}
  .card.crit{--sev:var(--crit)} .card.warn{--sev:var(--warn)} .card.ok{--sev:var(--ok)}
  .card .cname{font-weight:680;font-size:16px;letter-spacing:-.01em}
  .pill{margin-left:auto;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
    padding:4px 10px;border-radius:999px}
  .pill.crit{color:var(--crit);background:var(--crit-bg)} .pill.warn{color:var(--warn);background:var(--warn-bg)}
  .pill.ok{color:var(--ok);background:var(--ok-bg)}
  .card .body{padding:14px 16px;display:flex;flex-direction:column;gap:11px}
  .metric{display:grid;grid-template-columns:58px 1fr auto;gap:10px;align-items:center}
  .metric .ml{font-size:12px;color:var(--muted)}
  .metric .mv{font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums;text-align:right}
  .meter{height:6px;border-radius:3px;background:var(--meter-track);overflow:hidden}
  .meter>span{display:block;height:100%;border-radius:3px;background:var(--mc)}
  .mok{--mc:var(--ok)} .mwarn{--mc:var(--warn)} .mcrit{--mc:var(--crit)} .macc{--mc:var(--accent)}
  .kv{display:flex;flex-wrap:wrap;gap:6px}
  .tag{font-size:11px;font-family:var(--mono);padding:3px 8px;border-radius:6px;
    background:var(--surface-2);border:1px solid var(--border);color:var(--muted)}
  .tag b{color:var(--ink);font-weight:600}
  .tag.on b{color:var(--ok)} .tag.off b{color:var(--crit)} .tag.dim{opacity:.7}
  .attn{display:flex;flex-direction:column;gap:4px;margin-top:2px}
  .attn .a{font-size:12.5px;color:var(--ink);display:flex;gap:7px}
  .attn .a::before{content:"•";color:var(--sev)}
  .attn .clean{font-size:12.5px;color:var(--ok)}
  footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:10px}
  .hint{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;
    padding:13px 16px;font-size:13.5px;color:var(--ink)}
  .hint b{color:var(--accent)}
  .meta{font-family:var(--mono);font-size:11.5px;color:var(--faint);display:flex;flex-wrap:wrap;gap:4px 18px}
"""

_SEV_LABEL = {"critical": "Critical", "warning": "Warning"}
_SEV_CLASS = {"critical": "crit", "warning": "warn"}
_STATUS_CLASS = {"critical": "crit", "warn": "warn", "ok": "ok"}
_STATUS_LABEL = {"critical": "Critical", "warn": "Warn", "ok": "OK"}


def _meter_class(pct: float) -> str:
    """Threshold colour for a utilisation meter."""
    if pct >= 95:
        return "mcrit"
    if pct >= 85:
        return "mwarn"
    return "mok"


def _clamp(pct: float) -> float:
    return max(0.0, min(100.0, pct))


def _issue_row(rank: int, issue: dict) -> str:
    sev = issue.get("severity", "warning")
    cls = _SEV_CLASS.get(sev, "warn")
    label = _SEV_LABEL.get(sev, sev.title())
    detail = escape(str(issue.get("detail", "")))
    if issue.get("kind") == "alarm":
        detail += ' <span style="color:var(--faint);font-weight:400">(alarm)</span>'
    obj = escape(str(issue.get("object", "")))
    cluster = escape(str(issue.get("cluster") or ""))
    if issue.get("scope") == "host":
        loc = f"host <b>{obj}</b>" + (f" · cluster {cluster}" if cluster else "")
    else:
        loc = f"cluster <b>{obj}</b>"
    nxt = escape(str(issue.get("drilldown", "")))
    return (
        f'<div class="issue {cls}"><div class="rank">{rank}</div>'
        f'<div class="chip {cls}">{label}</div>'
        f'<div class="what"><div class="prob">{detail}</div><div class="obj">{loc}</div></div>'
        f'<div class="next"><span class="arrow">&rarr;</span> {nxt}</div></div>'
    )


def _metric(label: str, width: float, klass: str, value: str) -> str:
    return (
        f'<div class="metric"><span class="ml">{label}</span>'
        f'<div class="meter {klass}"><span style="width:{_clamp(width):.0f}%"></span></div>'
        f'<span class="mv">{escape(value)}</span></div>'
    )


def _cluster_card(c: dict, has_vms: bool) -> str:
    status = c.get("status", "ok")
    cls = _STATUS_CLASS.get(status, "ok")
    name = escape(str(c.get("name", "")))
    hosts_t = c.get("hosts_total", 0)
    hosts_c = c.get("hosts_connected", 0)
    hosts_pct = (hosts_c / hosts_t * 100) if hosts_t else 0
    parts = [
        f'<div class="card {cls}"><div class="top"><span class="cname">{name}</span>'
        f'<span class="pill {cls}">{_STATUS_LABEL.get(status, status)}</span></div><div class="body">',
        _metric(
            "Hosts", hosts_pct, "mok" if hosts_c == hosts_t else "mcrit", f"{hosts_c}/{hosts_t}"
        ),
    ]
    if has_vms:
        vms_t = c.get("vms_total", 0)
        vms_on = c.get("vms_on", 0)
        vms_pct = (vms_on / vms_t * 100) if vms_t else 0
        parts.append(_metric("VMs on", vms_pct, "macc", f"{vms_on}/{vms_t}"))
    cpu = c.get("cpu_used_pct", 0)
    mem = c.get("mem_used_pct", 0)
    parts.append(_metric("CPU", cpu, _meter_class(cpu), f"{cpu:g}%"))
    parts.append(_metric("Memory", mem, _meter_class(mem), f"{mem:g}%"))

    ha = "on" if c.get("ha_enabled") else "off"
    drs = "on" if c.get("drs_enabled") else "off"
    al = c.get("alarms", {})
    parts.append(
        f'<div class="kv"><span class="tag {ha}">HA <b>{ha}</b></span>'
        f'<span class="tag {"on" if drs == "on" else "dim"}">DRS <b>{drs}</b></span>'
        f'<span class="tag">alarms <b>{al.get("critical", 0)}</b>c / <b>{al.get("warning", 0)}</b>w</span></div>'
    )
    attention = c.get("attention") or []
    if attention:
        rows = "".join(f'<div class="a">{escape(str(a))}</div>' for a in attention)
        parts.append(f'<div class="attn">{rows}</div>')
    else:
        parts.append('<div class="attn"><div class="clean">No issues — cluster healthy</div></div>')
    parts.append("</div></div>")
    return "".join(parts)


def render_cluster_health_html(
    data: dict,
    vcenter: str,
    generated_at: datetime,
    filename: str = "",
) -> str:
    """Render a cluster-health summary dict as a standalone HTML document.

    Args:
        data: Return value of ``get_cluster_health_summary``.
        vcenter: Target name, shown in the title/header.
        generated_at: Snapshot time, shown in the header and footer.
        filename: Optional file name to record in the footer (for provenance).

    Returns:
        A complete ``<!doctype html>`` document string with all CSS inlined and
        every dynamic value HTML-escaped. No external requests.
    """
    totals = data.get("totals", {})
    clusters = data.get("clusters", [])
    has_vms = "vms_total" in totals
    worst = totals.get("worst_status", "ok")
    vc = escape(str(vcenter))
    stamp = generated_at.strftime("%Y-%m-%d %H:%M %Z") or generated_at.strftime("%Y-%m-%d %H:%M")

    # Totals strip
    cells = [
        f'<div class="cell"><div class="k">Clusters</div><div class="v">{totals.get("clusters", 0)}</div></div>',
        f'<div class="cell"><div class="k">Hosts connected</div><div class="v">'
        f"{totals.get('hosts_connected', 0)}<small>/{totals.get('hosts_total', 0)}</small></div></div>",
    ]
    if has_vms:
        cells.append(
            f'<div class="cell"><div class="k">VMs powered on</div><div class="v">'
            f"{totals.get('vms_on', 0)}<small>/{totals.get('vms_total', 0)}</small></div></div>"
        )
    al = totals.get("alarms", {})
    cells.append(
        f'<div class="cell"><div class="k">Active alarms</div><div class="v">'
        f'<span class="c">{al.get("critical", 0)}</span><small> crit</small> · '
        f'<span class="w">{al.get("warning", 0)}</span><small> warn</small></div></div>'
    )
    tc = len(cells)

    # Top issues
    issues = data.get("top_issues", [])
    issues_total = data.get("issues_total", len(issues))
    if issues:
        count = f"{len(issues)} shown · {issues_total} total"
        rows = "".join(_issue_row(i + 1, iss) for i, iss in enumerate(issues))
        issues_block = (
            f'<div class="section-label">Top issues <span class="count">{count}</span></div>'
            f'<div class="issues">{rows}</div>'
        )
    else:
        issues_block = '<div class="clean-all">No issues detected — every cluster is OK.</div>'

    cards = "".join(_cluster_card(c, has_vms) for c in clusters)
    hint = escape(str(data.get("customization_hint", "")))
    snapshot = escape(str(data.get("snapshot", "point-in-time snapshot")))
    fname = escape(filename) if filename else ""
    meta_bits = [f"<span>{snapshot}</span>"]
    if fname:
        meta_bits.append(f"<span>file: {fname}</span>")
    meta_bits.append("<span>generated by vmware-monitor summary --html</span>")

    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Cluster Health — {vc} — {escape(stamp)}</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div class="wrap"><header><div style="width:100%">'
        '<div class="eyebrow">VMware cluster health · triage snapshot</div>'
        f'<h1>What needs attention on <span class="vc">{vc}</span></h1></div>'
        f'<div class="stamp">Snapshot {escape(stamp)}</div>'
        f'<div class="overall {_STATUS_CLASS.get(worst, "ok")}"><span class="dot"></span>'
        f"{_STATUS_LABEL.get(worst, worst)}</div></header>"
        f'<div class="totals" style="--tc:{tc}">{"".join(cells)}</div>'
        f"{issues_block}"
        '<div class="section-label">Clusters <span class="count">worst status first</span></div>'
        f'<div class="cards">{cards}</div>'
        f'<footer><div class="hint">{hint}</div>'
        f'<div class="meta">{"".join(meta_bits)}</div></footer>'
        "</div></body></html>"
    )
