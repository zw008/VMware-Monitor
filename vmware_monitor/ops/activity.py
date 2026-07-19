"""Activity tracking: running tasks and active sessions (read-only).

Events (ops.health) are a historical log; this module shows what is happening
*right now* — in-flight tasks (clone, migrate, reconfigure) and who is logged
in. Useful to answer "why is the cluster busy?" or "who changed this?".

Read-only — listing tasks/sessions never cancels a task or terminates a
session (those are writes owned by vmware-aiops / vSphere admin).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim
from vmware_policy import paginated, sanitize

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

# Task states that mean "still doing work".
_ACTIVE_TASK_STATES = {"running", "queued"}


def get_active_tasks(
    si: ServiceInstance,
    include_recent: bool = True,
    limit: int | None = None,
) -> dict:
    """In-flight (and optionally just-completed) vCenter tasks.

    Returns the family list envelope. Each row has name, entity, state,
    progress_pct, start_time, queue/user, and error (when a recent task
    failed). Running/queued tasks first, then recent completed ones if
    include_recent is True. ``total`` is real — the whole ``recentTask``
    collection is materialised and filtered before ``limit`` is applied.

    Args:
        si: vSphere ServiceInstance.
        include_recent: Also include recently completed/failed tasks.
        limit: Max number of task rows to return (None = all).
    """
    content = si.RetrieveContent()
    task_mgr = content.taskManager
    recent = getattr(task_mgr, "recentTask", None) or []

    results: list[dict] = []
    for task in recent:
        info = getattr(task, "info", None)
        if info is None:
            continue
        state = str(info.state)
        active = state in _ACTIVE_TASK_STATES
        if not active and not include_recent:
            continue
        error = None
        if info.error is not None:
            # TaskInfo.error is a vmodl.MethodFault → .msg (verified against the
            # SDK by the vim-conformance test, not memory).
            error = sanitize(getattr(info.error, "msg", None) or str(info.error), max_len=300)
        results.append(
            {
                "name": sanitize(info.descriptionId or info.key),
                "entity": sanitize(info.entityName) if info.entityName else "N/A",
                "state": state,
                "progress_pct": info.progress
                if info.progress is not None
                else (100 if state == "success" else 0),
                "start_time": str(info.startTime) if info.startTime else "N/A",
                "user": sanitize(info.reason.userName)
                if isinstance(info.reason, vim.TaskReasonUser)
                else "system",
                "active": active,
                "error": error,
            }
        )

    # Active first, then by start time descending.
    results.sort(key=lambda x: (not x["active"], x["start_time"]), reverse=False)
    total = len(results)
    if limit is not None:
        results = results[:limit]
    return paginated(results, limit=limit, total=total)


def get_active_sessions(
    si: ServiceInstance,
    limit: int | None = None,
) -> dict:
    """Currently authenticated vCenter/ESXi sessions.

    Returns the family list envelope with a real ``total`` — the whole session
    list is materialised before ``limit`` is applied. Each row has user_name,
    full_name, login_time, last_active, ip_address, and a
    ``current`` flag for the session this skill is using. Requires Sessions
    privileges; low-privilege service accounts may be denied — in that case a
    single explanatory row is returned instead of a traceback (consistent with
    the read-only degradation pattern used for standalone-ESXi events).

    Args:
        si: vSphere ServiceInstance.
        limit: Max number of session rows to return (None = all).
    """
    content = si.RetrieveContent()
    session_mgr = content.sessionManager
    if session_mgr is None:
        return paginated([], limit=limit, total=0)

    current_key = None
    try:
        current = session_mgr.currentSession
        current_key = current.key if current else None
    except Exception:
        current_key = None

    try:
        sessions = list(session_mgr.sessionList or [])
    except vim.fault.NoPermission:
        # One explanatory row, and that row is the whole collection — total=1
        # keeps the envelope from flagging it as a possibly-truncated page.
        return paginated(
            [
                {
                    "note": "Sessions list requires the Sessions privilege; account lacks it.",
                    "user_name": "N/A",
                }
            ],
            limit=limit,
            total=1,
        )

    results: list[dict] = []
    for s in sessions:
        results.append(
            {
                "user_name": sanitize(s.userName),
                "full_name": sanitize(s.fullName) if s.fullName else "N/A",
                "login_time": str(s.loginTime) if s.loginTime else "N/A",
                "last_active": str(s.lastActiveTime) if s.lastActiveTime else "N/A",
                "ip_address": sanitize(s.ipAddress) if s.ipAddress else "N/A",
                "current": s.key == current_key,
            }
        )
    results.sort(key=lambda x: x["last_active"], reverse=True)
    total = len(results)
    if limit is not None:
        results = results[:limit]
    return paginated(results, limit=limit, total=total)
