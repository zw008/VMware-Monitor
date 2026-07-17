## v1.7.7 (2026-07-17) — session-probe eviction fix + mcp 1.28.1

Family fix pack — no new tools, no schema changes.

### Fixed
- **Dead cached vCenter sessions were never evicted** (external fork report,
  VMware-AIops PR #32). The liveness probe's handler was
  `except (vmodl.fault.NotAuthenticated, Exception)` — but
  `vmodl.fault.NotAuthenticated` does not exist in pyVmomi (the real class
  lives under `vim.fault`), and except-tuples are evaluated at catch time, so
  the handler raised `AttributeError` instead of evicting. A long-running MCP
  server whose session idled out then permafailed every call until restart,
  surfacing the misleading `AttributeError: NotAuthenticated` instead of the
  real error. The probe now also treats a `None` `currentSession`
  (expired-token shape) as dead. Three regression tests pin the probe shapes
  (raise → evict + reconnect, None → evict + reconnect, live → cache reuse),
  and family_smoke gained a static check banning the nonexistent class.

### Security
- Lockfile bumps `mcp` to **1.28.1**, clearing three GHSA HIGH advisories
  against the MCP Python SDK (WebSocket Host/Origin validation, HTTP
  transport principal verification, experimental task-handler cross-client
  access). stdio-only servers are not directly exposed, and installs resolve
  `mcp` fresh from PyPI — this mainly matters for from-source checkouts.

## v1.7.6 (2026-07-14) — object-centered investigation bundles + cross-vCenter attention

Extends the issue #31 triage work from "is anything on fire?" to "what is happening
around *this* object?" — the object-centered drill-down juanpf-ha asked for.

### Added
- **Object investigation bundles** (read-only; surface 23 → 27). Three new MCP tools —
  `vm_investigation_bundle`, `host_investigation_bundle`, `datastore_investigation_bundle`
  — each answers "what is happening around this object?" in ONE call that *correlates*
  the object with its surrounding infrastructure and recent history: state, the
  host/cluster/datastores around it, snapshots, alarms (across every related scope),
  live performance, and a merged, newest-first **event timeline** stitched from the
  object AND its host/cluster/datastores via per-entity `EventFilterSpec.ByEntity`
  queries. Aggregation happens in the tool — the model explains a high-signal result,
  never raw inventory. All cross-object reads are batched (no per-object round-trips,
  issue #31 class).
- **`cross_vcenter_attention` MCP tool** — "what needs attention now?" across EVERY
  configured vCenter, merged into one globally-ranked `top_issues` list (each tagged
  with its `vcenter`) plus a per-target rollup. Degrades gracefully: an unreachable
  target is listed under `unreachable` with a reason and the rest still aggregate.
- **CLI**: `vmware-monitor investigate vm|host|datastore <name>` and
  `vmware-monitor attention`, each with `--hours` and `--html` / `--html-path`. The
  `--html` snapshot is self-contained and offline (no external assets), with drill-down
  detail in native `<details>` sections — collapse/expand with zero JavaScript.

### Changed
- Extracted the shared offline-HTML palette into `ops/_html_base.py` so the
  cluster-health, investigation, and attention renderers stay visually identical.

### Notes
- Point-in-time snapshots — no trend is invented. Strictly read-only.
## v1.7.5 (2026-07-13) — cluster health triage: one-glance summary, top-N issues, offline HTML snapshots

### Added
- **`cluster_health_summary` MCP tool** (read-only; surface 22 → 23). One aggregated
  read answers "is anything on fire?": three batched PropertyCollector passes roll
  hosts, VM power state, live CPU/memory pressure, and triggered alarms up to the
  owning cluster, assign an opinionated `status` (ok/warn/critical) with
  plain-language `attention` reasons, and flatten the individual anomalies into a
  ranked **`top_issues`** focus list (severity → kind → magnitude; capped by
  `top_n`, default 10, with an honest pre-cap `issues_total`). Alarm names are
  resolved in one extra batched call — no per-alarm round-trips (issue #31 class).
  Born from the issue #31 triage discussion.
- **`vmware-monitor summary` CLI** — `--top N`, `--cluster <substr>`, `--no-vms`,
  and `--html` / `--html-path <file>`: renders the same data as an **offline,
  self-contained HTML snapshot** (all CSS inlined, no external assets, light/dark
  aware, every vSphere-sourced value HTML-escaped). Default location
  `~/vmware-health/cluster-health-<vc>-<YYYYMMDD-HHMMSS>.html` — timestamped
  filenames turn the folder into a browsable point-in-time history.
- **Editable display template** `references/health-summary-template.md` — the
  default columns/thresholds plus a worked "add a column" example; every rendered
  view ends with a friendly customization hint.
- Public render helpers (`render_summary_console`, `write_html_snapshot`) so
  companion skills (vmware-aiops) can present the identical view without
  duplicating code.

## v1.7.4 (2026-07-13) — host-check boundary reads batched (issue #31 tail)

### Fixed
- **NTP / services / certificate checks at scale.** `get_ntp_status`,
  `get_host_services`, and `get_certificate_status` already batched each host's
  name + `configManager` reference in one PropertyCollector call, but then read
  the property they actually needed — `serviceInfo` / `certificateInfo`, which
  lives on the referenced `HostServiceSystem` / `HostCertificateManager` managed
  object that a `HostSystem` container view cannot cross — lazily, i.e. one extra
  SOAP round-trip per host (the issue #31 class, one hop removed). A new
  `ops/_collect._collect_objects` helper fetches the boundary property for every
  reference in a single second `RetrievePropertiesEx`, collapsing the per-host N
  into 2 calls total. Output shape unchanged.

## v1.7.3 (2026-07-03) — host_log_scan MCP tool

### Added
- **`host_log_scan` MCP tool** (read-only). The ESXi syslog error scan — recent
  hostd/vmkernel/vpxa lines matching error/warning patterns (error, fail,
  critical, panic, lost access, timeout, …) — was previously only reachable as a
  scanner/CLI path. It's now surfaced as a proper MCP tool with an optional
  single-host filter and a `lines` window; it returns only the matching lines
  (sanitized, injection-guarded), so output stays small even on large clusters.
  Requested by @juanpf-ha on issue #31. MCP tool surface 21 → 22.

## v1.7.2 (2026-07-02) — read-path scale beyond inventory (issue #31 follow-up)

### Fixed
- **All monitoring read paths at scale.** The v1.7.1 PropertyCollector fix
  covered inventory only. Snapshot aging (heavy per-VM `layoutEx`), VM/host
  performance, active alarms, host hardware/services status, certificate/NTP
  status, datastore/resource-pool capacity, and host-log scan each walked a
  container view reading lazy properties per object — N+1 SOAP round-trips that
  timed out on large vCenters. All now batch via a shared `PropertyCollector`
  helper (`ops/_collect.py`). Output shape unchanged.

## v1.7.1 (2026-07-02) — large-inventory scale fix (PropertyCollector, issue #31)

### Fixed
- **Large-inventory scale (GitHub issue #31 on VMware-AIops).** Read-only
  inventory tools (`list_virtual_machines`, `list_esxi_hosts`,
  `list_all_datastores`, `list_all_clusters`, `list_all_networks`, and
  `find_vm_by_name`) walked a container view and then read pyVmomi *lazy*
  properties per object (`vm.config.hardware.numCPU`, `vm.runtime.host.name`,
  `len(host.vm)`, per-VM `folder_path` walk …) — each a separate SOAP round-trip.
  On large vCenters (thousands of VMs / hundreds of hosts) this meant tens of
  thousands of round-trips, so even `limit=20` queries timed out. All of these
  now fetch every needed property in a single `PropertyCollector.RetrievePropertiesEx`
  call (paged via continuation tokens); `folder_path` is resolved from a batched
  folder map. Output shape is unchanged. Same root cause reported against
  VMware-AIops by juanpf-ha (~8,000-VM / ~340-host environment); fixed here in
  the sibling read-only skill too.

## v1.7.0 (2026-06-27) — guided onboarding + teaching auth errors

### Added
- **`vmware-monitor init` — interactive first-run setup wizard.** Prompts for host /
  username / password and writes `config.yaml` + `.env` for you. The password is
  stored grep-safe (`b64:`, never plaintext on disk) and `.env` is locked to
  0600, then the connection is verified. Replaces the manual "mkdir + cp
  config.example.yaml + edit YAML + chmod 600" dance.
- **10 new read-only monitoring tools (MCP 11 → 21).** Real-time host/VM
  performance (PerfManager: CPU/mem/disk/net), inventory-wide snapshot aging &
  sprawl, ESXi certificate expiry, license usage/expiry, NTP config health,
  datastore thin-provisioning over-commit, resource-pool usage, in-flight tasks,
  and active sessions — all strictly read-only. Honest about limits: no
  fabricated trends, and NTP live-offset is documented as not exposed by the
  SOAP API.

### Changed
- `doctor` now points to `vmware-monitor init` when config/credentials are missing
  (previously suggested a command that did not exist), keeping the manual steps
  as a fallback.
- Authentication and TLS failures now print a teaching message naming the exact
  file and env var to fix (`~/.vmware-monitor/.env` password var, `config.yaml`
  username) plus a `verify_ssl: false` hint for self-signed labs.

## v1.6.1 (2026-06-24)

### Added
- **`.env` passwords are auto-obfuscated to a grep-safe `b64:` form** on first
  load and decoded transparently at runtime — plaintext no longer sits in
  `~/.<skill>/.env` for a casual `grep` to find. Values are read/written through
  python-dotenv's own parser, so the stored secret never drifts from the
  configured one (handles quotes, inline comments, trailing whitespace, and a
  password that literally starts with `b64:`). **Obfuscation, not encryption** —
  for real at-rest secrecy, inject the password from a secret manager instead of
  storing `.env`. New regression suite (10 cases) covers dotenv parity, the
  `b64:`-prefixed edge case, idempotency, and 0600 preservation.

## v1.6.0 (2026-06-22) — family alignment + harness trust architecture

No skill code changes. Aligns to the v1.6.0 family release and automatically picks up the
vmware-policy 1.6.0 governance upgrades (token/runaway budget guard, audit accountability fields,
graduated-autonomy risk tiers) on next install. Read-only skill — no undo tokens applicable.

## v1.5.39 (2026-06-22) — family version alignment

No code changes. Version bump to stay aligned with the v1.5.39 family release
(AIops snapshot-delete async + honest-timeout token-burn fix; Storage datastore-browse timeout fix).

## v1.5.38 (2026-06-12) — release alignment

No functional changes — version bumped to keep the VMware skill family aligned at v1.5.38.

## v1.5.37 (2026-06-12) — backlog: wire up advertised health tools

### Added
- `health sensors`, `health services`, and `inventory networks` CLI commands + read-only MCP tools — these
  were implemented but unreachable while the help text advertised them. Tool count 8 → 11 (all read-only). (#16)

### Fixed
- Docs no longer reference a nonexistent `vmware-monitor init`; setup instructions corrected. (#17)
- Removed two orphan lookup helpers with no callers.

## v1.5.36 (2026-06-12) — MCP error-shape fix, resilient daemon, no false "all clear"

### Fixed
- **Five MCP tools lost their teaching hint to structured-output validation** — list-returning tools
  returned an error dict, which FastMCP rejected as a ToolError; error shapes now match annotations so
  the hint survives.
- **`get_recent_events` no longer reports "no events" on a real failure** — only the standalone-ESXi
  `NotSupported` case maps to empty; auth/network errors are raised.
- **Daemon PID/scan ordering fixed** — a crash in the first scan no longer leaves a stale PID file
  that makes `daemon status` lie; one bad log write no longer discards a scan cycle.
- **Audit-write failure degrades to a stderr warning** instead of killing read commands.
- `doctor` no longer recommends a nonexistent `init` command; CLI commands print teaching errors
  instead of tracebacks; atexit Disconnect guarded.

## v1.5.35 (2026-06-10) — security hardening: safe errors, webhook & PID hygiene

### Fixed
- **MCP tools route errors through `_safe_error()`** (no raw exception text to the agent).
- **Audit** dir 0700 / log 0600; **PID-file** directory created 0700.
- **Webhook** response bodies CR/LF-stripped before logging.

This release aligns the whole family back to a single version (1.5.35); vmware-policy and vmware-pilot return to the shared number after sitting at 1.5.22.

## v1.5.32 (2026-06-08) — Sensor health fix + missing snapshot-list MCP tool added

### Fixed
- Hardware sensors: health from `healthState.key` (green/yellow/red) — the
  previous code reported the sensor category as its status. Sensor type kept
  as a separate column.
- Event severity sets: `DVPortgroupReconfiguredEvent` casing (never matched).

### Added
- `vm_list_snapshots` MCP tool — the CLI had `vm snapshot-list` but the MCP
  server never registered it; docs claimed 8 tools while 7 existed (CLI/MCP
  parity). All 8 tools remain strictly read-only.

### Tests
- vim-attribute conformance regression (shared family defense); stale
  hardcoded repo path in the zero-destructive-code test fixed.

## v1.5.30 (2026-06-07) — Family version alignment

No functional changes. Version-alignment release with the v1.5.30 family
(tool description quality + NSX fixes in sibling skills).

## v1.5.29 (2026-05-29) — `--folder-filter` CLI flag (CLI/MCP Parity)

### New
- `vmware-monitor inventory vms --folder-filter <pattern>` now exposes the case-insensitive folder-path filter that has been available via MCP since v1.5.21. Closes the CLI/MCP exposure asymmetry flagged in CLAUDE.md 踩坑 #34.
- Table title shows `[folder~<pattern>]` marker when filter is active.

### Tests
- 7 new unit tests in `tests/test_folder_filter.py` covering: no-filter pass-through, prefix/case-insensitive/substring matches, no-match empty result, intersection with `power_state`, and CLI `--help` smoke containing `--folder-filter`.

### Documentation
- `references/cli-reference.md` drops the "MCP-only parameter" caveat and documents `--folder-filter` flag.
- `references/capabilities.md` updates the `folder_filter` parameter row to "CLI `--folder-filter`, MCP `folder_filter`".

## v1.5.28 (2026-05-20)

**Fix `subclass() arg 1 must be a class` in goose/old mcp environments** —
v1.5.25–1.5.27 replaced `X | None` with `Optional[X]` but kept
`from __future__ import annotations` at the top of `mcp_server/server.py`.
Under mcp 1.10–1.13 (which Goose and some sandboxes pin), `Tool.from_function`
calls `issubclass(param.annotation, Context)` without resolving forward refs,
so string annotations crash the entire server load. Removed
`from __future__ import annotations` from `mcp_server/server.py` so annotations
are real classes; verified all tools load under mcp 1.10 and 1.14.

Traceback location: `mcp/server/fastmcp/tools/base.py:67`. CLAUDE.md 踩坑 #33
updated. family_smoke.sh Check 4b now installs `mcp==1.10.0` to catch this
regression class.

## v1.5.27 (2026-05-20)

**Loosen Python requirement: now supports Python >= 3.10** — v1.5.25/26 fixed
the PEP 604 root cause in MCP tool signatures (Optional[X] instead of X | None),
but kept `requires-python = ">=3.11"` and a 3.11 hard guard in `mcp_cmd`. Both
relaxed to 3.10 so users on Python 3.10 (e.g. Goose default sandbox, Ubuntu
22.04 system python) can install and run directly without a Python upgrade.

- `pyproject.toml`: `requires-python = ">=3.10"` (was `>=3.11`; VMware-VKS
  was `>=3.12`, now also `>=3.10` for family alignment).
- `<pkg>/cli.py` `mcp_cmd()`: version guard now triggers on `< (3, 10)`.
- Behavior on Python 3.10 matches 3.11/3.12 — the Optional[X] fix from v1.5.25
  is what actually enables this; this release just stops blocking installs.

---

## v1.5.26

**Family-wide MCP server fix — Python 3.10 compatibility (踩坑 #33)** — `vmware-monitor mcp`
crashed at decorator time on Python 3.10 with `subclass() arg 1 must be a class`.
Root cause: `mcp_server/server.py` used PEP 604 `X | None` in tool signatures
plus `from __future__ import annotations`; on Python 3.10 + older mcp/pydantic
combos, `typing.get_type_hints()` evaluates `"str | None"` to a
`types.UnionType` instance, which FastMCP/Pydantic then feeds to `issubclass()`.
Reported by a goose user (qwen3.6:27, Python 3.10).

- `mcp_server/server.py`: all `X | None` → `Optional[X]`; ops layer untouched.
- `<pkg>/cli.py` `mcp_cmd()`: hard guard — exits with installation fix command
  if Python < 3.11 (defense in depth, our actual lower bound).
- `pyproject.toml`: `mcp[cli]>=1.10,<2.0` (was `>=1.0`) so uv doesn't pick
  an ancient version that has the same issubclass bug.

**Tooling — family smoke gains MCP schema-build check** — `scripts/family_smoke.sh`
new Check 4b runs `asyncio.run(mcp.list_tools())` per skill, forcing FastMCP to
build Pydantic models for every declared tool. Supports both module-level `mcp`
and `build_server()` factory patterns.

**Docs — CLAUDE.md gains 踩坑 #33 (PEP 604 / Python 3.10) and #34 (CLI/MCP exposure parity).**

---

## v1.5.24 (2026-05-19)

**Family version alignment** — no code changes in this skill. Bumped together
with VMware-AIops and VMware-VKS, which received a pyVmomi 8.x `ManagedObject`
setattr fix (踩坑 #32). `family_smoke.sh` now enforces the no-setattr rule
across all 9 skills.

## v1.5.23 (2026-05-19)

**VCF 9.0 / 9.1 compatibility declared** — family-wide docs sync.

- **docs:** README + `references/capabilities.md` version-compatibility tables now explicitly list vSphere 9.0 / 9.0U1 / 9.1 as ✅ Full. pyVmomi 8.0.3+ (currently pinned `<10.0`) continues to work against vSphere 9 SOAP API; all 8 read-only tools remain functional.
- **docs:** Added `Official Broadcom References` pointer to [VCF Python SDK](https://developer.broadcom.com/sdks), [REST API portal](https://developer.broadcom.com/xapis), and [CLI tools](https://developer.broadcom.com/tools).
- **align:** Family v1.5.23 — all 9 skills tracking VCF 9.0 / 9.1 compatibility declaration.

## v1.5.22 (2026-05-08)

**Family alignment** — no source changes in this skill.

- **align:** Tracks v1.5.22 family bump driven by Smithery onboarding for vmware-avi / vmware-harden / vmware-pilot.

## v1.5.21 (2026-05-08)

**Feature**: Added `folder_path` field to VM inventory and `folder_filter` parameter for case-insensitive folder-tree search (community contribution from @gavinlinasd, PR #11).

- **feat:** `list_vms()` and `get_vm_info()` now return a `folder_path` field showing each VM's vCenter inventory folder path (e.g. `/Colocation/Colo - ISER`). The path is also added to compact-mode output.
- **feat:** New `folder_filter` parameter on `list_vms()` performs case-insensitive substring matching against `folder_path` — e.g. `folder_filter="Colocation"` returns VMs anywhere under any Colocation folder, including nested subfolders.
- **feat:** `folder_path` added to `_VM_SORT_KEYS` so VMs can be sorted by folder.
- **test:** 5 new unit tests for the `folder_path` helper covering root, single-level, nested, datacenter-name handling, and no-parent edge cases.
- **deps:** Bumped `python-multipart` 0.0.26 → 0.0.27 (transitive, fixes GHSA HIGH DoS via unbounded multipart headers).

## v1.5.20 (2026-05-08)

**Family alignment** — no source changes in this skill.

- **align:** Tracks v1.5.20 family bump driven by vmware-nsx-security and vmware-aria PyPI README `mcp-name:` ownership marker fix required by MCP Registry validation. Other 7 skills already had the marker; this release re-publishes them to keep the family version aligned per CLAUDE.md policy.
- **registry:** All 9 skills now registered on registry.modelcontextprotocol.io as `isLatest=true`.

## v1.5.19 (2026-05-06)

**Family alignment** — no source changes in this skill.

- **build:** Bumped `requires-python` from `>=3.10` to `>=3.11` (regression eval uses `tomllib`).
- **smoke:** Family `scripts/family_smoke.sh` adds Check 3b — recursive `--help` on every subcommand to surface broken lazy imports (yjs review 2026-05-06; 踩坑 #27).
- **align:** Tracks v1.5.19 fixes in vmware-nsx (CRITICAL CLI imports), vmware-vks (ApiClient leak), vmware-harden (Twin indexes + LEFT JOIN), vmware-policy (approval gate + singleton lock).

## v1.5.18 (2026-05-02)

**Family alignment + tooling normalization** — no source changes in this skill.

- **dev:** Migrated `[project.optional-dependencies] dev` → `[dependency-groups] dev` (PEP 735) so `uv sync --group dev` works uniformly across the family. Canonical set: `pytest>=8.0,<10.0`, `pytest-cov`, `ruff`.
- **test:** New `tests/eval/regression/test_release_blockers.py` (5 evals) catches the v1.5.x release blockers — missing `mcp_server` in wheel, AST-detected unimported runtime names, Typer app load failure, module import errors. Run via `pytest tests/eval/regression/`.
- **align:** Family version bump to v1.5.18.

## v1.5.17 (2026-05-01)

**Family alignment** — no source changes in this skill.

This release tracks vmware-pilot v1.5.17 (new `investigate_alert` template + `review_workflow` MCP tool + `parallel_group` step type) and vmware-policy v1.5.17 (L5 pattern matcher integrated into `@vmware_tool`). Both work with the existing skill MCP surface unchanged.

- **align:** Family version bump to v1.5.17.

## v1.5.16 (2026-04-30)

**Enterprise Harness Engineering alignment** — adapted from the Linkloud × addxai framework articles ([part 1](https://mp.weixin.qq.com/s/hz4W7ILHJ1yz_pG0Z1xP-A), [part 2](https://mp.weixin.qq.com/s/F3qYbyB3S8oIqx-Y4BrWNQ)).

- **docs:** New `references/investigation-protocol.md` — causal-chain root cause analysis protocol shared with aiops/aria. Monitor serves as the read-only data source for diagnostic chains.
- **docs:** "Automation Level Reference" section in `references/capabilities.md` — clarifies that monitor is L1/L2 only by code-level design.
- **docs:** Common Workflows in `SKILL.md` enriched with judgment ("alarms tell you what vCenter decided is wrong, events tell you what happened — they diverge").
- **align:** Family version bump to v1.5.16.

## v1.5.15 (2026-04-29)

**UX improvements from real user feedback**

- **feat:** New top-level CLI subcommand `vmware-monitor mcp` starts the MCP server. Single command, single binary on PATH after `uv tool install vmware-monitor` — no more `uvx --from`, no PyPI re-resolve, no TLS-proxy issues.
- **feat:** Default `verify_ssl: true` on new targets (was `false`). Self-signed cert environments must now opt in explicitly with `verify_ssl: false` in `config.yaml`.
- **docs:** README, SKILL.md, setup-guide.md, and all `examples/mcp-configs/*.json` switched to `command: "vmware-monitor"`, `args: ["mcp"]`. uvx form moved to fallback section with TLS-proxy troubleshooting note.
- **compat:** Legacy `vmware-monitor-mcp` console script kept — existing user configs continue to work unchanged.

## v1.5.14 (2026-04-21)

**Bug fixes from code review by @yjs-2026 (follow-up)**

- **fix:** `health.py` — container views in `get_active_alarms`, `get_host_hardware_status`, `get_host_services` now wrapped in try/finally to prevent resource leaks on exception

## v1.5.13 (2026-04-21)

**Bug fixes from code review 2026-04-20**

- **fix:** `log_scanner.py` — `BrowseDiagnosticLog` now probes total line count first, then reads last N lines correctly (was passing line count as start offset)

## v1.5.12 (2026-04-17)

- Align with VMware skill family v1.5.12 (security & bug fixes from code review by @yjs-2026)

## v1.5.11 (2026-04-17)

- Align with VMware skill family v1.5.11 (AVI 22.x fixes from @timwangbc)

## v1.5.10 (2026-04-16)

- Security: bump python-multipart 0.0.22→0.0.26 (DoS via large multipart preamble/epilogue)
- Align with VMware skill family v1.5.10

## v1.5.8 (2026-04-15)

- Align with VMware skill family v1.5.8 (NSX/AVI/Aria/AIops bug fixes)

## v1.5.7 (2026-04-15)

- Align with VMware skill family v1.5.7 (Pilot `__from_step_N__` fix + VKS SSL/timeout fix)

## v1.5.6 (2026-04-15)

- Fix: CRITICAL — `mcp_server` module missing from PyPI wheel (ModuleNotFoundError when running vmware-monitor-mcp). Added hatch packages config to pyproject.toml
- Align with VMware skill family v1.5.6

## v1.5.5 (2026-04-15)

- Align with VMware skill family v1.5.5

## v1.5.4 (2026-04-14)

### Security Updates

- **pytest CVE-2025-71176**: Upgraded pytest 9.0.2 → 9.0.3 (insecure tmpdir handling)
- **Dependencies**: Updated rich version constraint from <15.0 to <16.0 for compatibility
- **Alignment**: Sync with VMware skill family v1.5.4 release

## v1.5.0 (2026-04-12)

### Anthropic Best Practices Integration

- **[READ]/[WRITE] tool prefixes**: All MCP tool descriptions now start with [READ] or [WRITE] to clearly indicate operation type
- **Read/write split counts**: SKILL.md MCP Tools section header shows exact read vs write tool counts
- **Negative routing**: Description frontmatter includes "Do NOT use when..." clause to prevent misrouting
- **Broadcom author attestation**: README.md, README-CN.md, and pyproject.toml include VMware by Broadcom author identity (wei-wz.zhou@broadcom.com) to resolve Snyk E005 brand warnings

### Monitor-specific

- **limit parameters**: list_esxi_hosts, list_all_datastores, list_all_clusters, get_alarms now support limit parameter
- **Workflow failure branches**: Daily health check and VM investigation workflows include error handling steps

## v1.4.9 (2026-04-11)

- Fix: require explicit VMware/vSphere context in skill routing triggers (prevent false triggers on generic "clone", "deploy", "alarms" etc.)
- Fix: clarify vmware-policy compatibility field (Python transitive dep, not a required standalone binary)

## v1.4.8 (2026-04-09)

- Security: bump cryptography 46.0.6→46.0.7 (CVE-2026-39892, buffer overflow)
- Security: bump urllib3 2.3.0→2.6.3 (multiple CVEs) [VMware-VKS]
- Security: bump requests 2.32.5→2.33.0 (medium CVE) [VMware-VKS]

## v1.4.7 (2026-04-08)

- Fix: align openclaw metadata with actual runtime requirements
- Fix: standardize audit log path to ~/.vmware/audit.db across all docs
- Fix: update credential env var docs to correct VMWARE_<TARGET>_PASSWORD convention
- Fix: declare .env config and vmware-policy optional dependency in metadata

# Release Notes

## v1.4.5 — 2026-04-03

- **Security**: bump pygments 2.19.2 → 2.20.0 (fix ReDoS CVE in GUID matching regex)
- **Infrastructure**: add uv.lock for reproducible builds and Dependabot security tracking


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.4.0 — 2026-03-29

### Architecture: Unified Audit & Policy

- **vmware-policy integration**: All MCP tools now wrapped with `@vmware_tool` decorator
- **Unified audit logging**: Operations logged to `~/.vmware/audit.db` (SQLite WAL), replacing per-skill JSON Lines logs
- **Policy enforcement**: `check_allowed()` with rules.yaml, maintenance windows, risk-level gating
- **Sanitize consolidation**: Replaced local `_sanitize()` with shared `vmware_policy.sanitize()`
- **Risk classification**: Each tool tagged with risk_level (low/medium/high) for confirmation gating
- **Agent detection**: Audit logs identify calling agent (Claude/Codex/local)
- **New family members**: vmware-policy (audit/policy infrastructure) + vmware-pilot (workflow orchestration)


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.1 — 2026-03-27

### Family expansion: NSX, NSX-Security, Aria

- Added vmware-nsx, vmware-nsx-security, vmware-aria to companion skills routing table
- README updated with complete 7-skill family table
- vmware-aiops is now the family entry point (`vmware-aiops hub status`)


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.0 — 2026-03-26

### Docs / Skill optimization

- SKILL.md restructured with progressive disclosure (3-level loading)
- Created `references/` directory: cli-reference.md, capabilities.md, setup-guide.md
- Added trigger phrases to YAML description for better skill auto-loading
- Added Common Workflows section (Daily Health Check, Investigate VM, Continuous Monitoring)
- Added Troubleshooting section (5 common issues)
- README.md and README-CN.md updated with Companion Skills, Workflows, Troubleshooting


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.2.3 (2026-03-22)

### Docs / SKILL.md restructure

- Reorder SKILL.md: tool table and Quick Install first, routing table last — improves Skills.sh/ClawHub page readability.


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.2.1 (2026-03-22)

### Skill Routing / Skill 智能路由推荐

- SKILL.md 新增 **Related Skills — Skill Routing** 路由表：遇到存储相关请求推荐 vmware-storage，遇到 VM 操作需求推荐 vmware-aiops。
- Added **Related Skills** routing table to SKILL.md: recommends vmware-storage for storage tasks, vmware-aiops for VM lifecycle operations.


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.2.0 (2026-03-21)

### mcp-config install — Auto-write Agent Config / 自动写入 Agent 配置

- **`vmware-monitor mcp-config install --agent <name>`** — Directly writes MCP server config into the target agent's config file.
  直接将 MCP server 配置写入目标 Agent 的配置文件，无需手动编辑 JSON/YAML。
  - Supports: claude-code, cursor, goose, continue, vscode, localcowork, mcp-agent / 支持 7 种 Agent
  - JSON merge (non-destructive) + auto-backup on conflict / JSON 合并（非破坏性）+ 冲突时自动备份

### Docker One-Command Launch / Docker 一键启动

- **Dockerfile + docker-compose.yml** — Run MCP server without installing Python or venv.
  无需安装 Python 或 venv，一条命令启动 MCP Server。
  ```bash
  docker compose up -d
  ```

### Cursor Integration Guide / Cursor 集成文档

- **`docs/integrations/cursor.md`** — Full guide for using vmware-monitor as a read-only Cursor MCP server.
  完整的 Cursor 集成指南，包含自动安装、手动配置、8 个只读工具说明和排障指南。

**PyPI**: `uv tool install vmware-monitor==1.2.0`


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.1.0 (2026-03-21)

> **Version unification release / 版本统一发布**
> All platforms (PyPI, GitHub Release, MCP Registry, Skills.sh, ClawHub, Smithery) now share the same version number starting from v1.1.0.
> 所有平台从 v1.1.0 起统一版本号。

### Doctor & MCP Config Generator / 诊断与配置生成

- `vmware-monitor doctor` — 8-check environment diagnostic / 8 项环境诊断
- `vmware-monitor mcp-config generate --agent <name>` — Generate config for 7 local AI agents / 为 7 种本地 AI Agent 生成配置

### Inventory Enhancements / 资源清单增强

- `list_vms` with limit/sort_by/power_state/fields filtering / 支持过滤、排序、字段选择
- Auto-tiered response for large inventories (>50 VMs) / 大规模环境自动精简返回

### Security Hardening / 安全加固

- Prompt injection protection with boundary markers / Prompt 注入防护（边界标记）
- Bandit security scan: 0 issues / Bandit 安全扫描零问题

### Platform & Integration / 平台与集成

- MCP Registry, Skills.sh, ClawHub, Smithery, Glama, mcp.so, Cline Marketplace published
- Local agent config templates for 7 agents (Claude Code, Cursor, Goose, LocalCowork, mcp-agent, Continue, VS Code Copilot)
- Ollama end-to-end setup guide

**PyPI**: `uv tool install vmware-monitor==1.1.0`


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v0.1.2 (2026-03-05)

### Usage Mode Optimization

- **Platform-aware calling priority**: Claude Code and Cursor users get MCP-first experience (structured tool calls, no interactive confirmation needed). Aider, Codex, Gemini CLI, and local models (Ollama) default to CLI mode for lower context overhead and universal compatibility.

- **Install order update**: Skills.sh (`npx skills add`) is now the primary install method; ClawHub as secondary option.

- **MCP load tip**: Added tip for MCP-native tools to check MCP server status (`/mcp`) before use.

**Files updated**: `skills/vmware-monitor/SKILL.md`, `plugins/.../SKILL.md`, `README.md`, `README-CN.md`


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v0.1.1 (2026-03-03)

### Security Hardening: Prompt Injection Protection

- **Boundary markers**: All vSphere-sourced content (event messages, host logs) is now wrapped in explicit boundary markers (`[VSPHERE_EVENT]...[/VSPHERE_EVENT]`, `[VSPHERE_HOST_LOG]...[/VSPHERE_HOST_LOG]`) so downstream LLM agents can distinguish trusted output from untrusted vSphere data.

- **Comprehensive control character sanitization**: Replaced simple null-byte removal with regex-based stripping of all C0/C1 control characters (except `
` and `	`). Prevents prompt injection via embedded control sequences in vSphere event messages.

- **MCP server documentation**: Added comprehensive module docstring to `mcp_server/server.py` with security considerations (all-read-only tool classification, credential handling, transport security) to resolve Socket "Obfuscated File" audit flag.

- **Security section in SKILL.md**: Added explicit Security section covering read-only design, TLS verification, credential handling, webhook data scope, prompt injection protection, and code review guidance.

- **README safety table updates**: Added Prompt Injection Protection and Webhook Data Scope rows to safety features table in both English and Chinese READMEs.

**Files updated**: `vmware_monitor/scanner/log_scanner.py`, `mcp_server/server.py`, `skills/vmware-monitor/SKILL.md`, `plugins/.../SKILL.md`, `README.md`, `README-CN.md`


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v0.1.0 (2026-02-28)

**Initial release — Read-only VMware monitoring with code-level safety.**

Extracted from [VMware-AIops](https://github.com/zw008/VMware-AIops) as an independent repository. Zero destructive code paths — no power, create, delete, reconfigure, snapshot mutate, clone, or migrate operations exist in the codebase.

### Features

- **Inventory**: List VMs, ESXi hosts, datastores, clusters
- **Health & Monitoring**: Active alarms, recent events (50+ event types), hardware sensors, host services
- **VM Info**: Detailed VM information and snapshot listing (read-only)
- **Scheduled Scanning**: APScheduler daemon with configurable intervals, alarm + event + host log scanning
- **Notifications**: JSONL structured logs, Slack/Discord webhook alerts
- **Audit Trail**: All queries logged to `~/.vmware-monitor/audit.log` (JSONL)
- **Multi-target**: Sequential scanning across all configured vCenter/ESXi targets
- **MCP Server**: 7 read-only tools via Model Context Protocol (FastMCP)
- **CLI**: `vmware-monitor` with inventory, health, vm, scan, daemon subcommands

### AI Platform Support

- Claude Code (native plugin + marketplace)
- OpenAI Codex CLI (AGENTS.md)
- Aider / Continue CLI (AGENTS.md)
- Gemini CLI (AGENTS.md)
- Trae IDE (AGENTS.md)
- Kimi Code CLI (AGENTS.md)
- MCP Server (Smithery / Claude Desktop / Cursor)

### Safety

- **Code-level isolation**: No destructive functions or pyVmomi write API calls in the codebase
- **Automated verification**: `test_no_destructive_code.py` checks 40+ destructive patterns
- **PR template**: Read-Only Verification checklist required for all pull requests
- **Credential security**: `.env` with `chmod 600`, config-based connections, zero password exposure

### Configuration

- Independent config directory: `~/.vmware-monitor/`
- YAML-based multi-target configuration
- Environment variable passwords: `VMWARE_{TARGET_NAME}_PASSWORD`
- SSL self-signed certificate support

### Compatibility

| vSphere Version | Support |
|----------------|---------|
| 8.0 / 8.0U1-U3 | Full |
| 7.0 / 7.0U1-U3 | Full |
| 6.7 | Compatible |
| 6.5 | Compatible |

Requires Python >= 3.10, pyVmomi >= 8.0.3.0.