"""Capability — when a call fails, is the model told enough to fix it?

What this measures
------------------
CLAUDE.md mandates "教学性错误" (teaching errors): an error must not merely
report a failure, it must carry the correction. This eval extracts every error
message the package can raise — by parsing the AST, so it sees messages no test
happens to trigger — and scores each on three dimensions. It also checks the
live MCP error payload shape.

Why it matters for a small model
--------------------------------
Error recovery is where the capability gap between a large and a small model is
widest. Given ``VM 'web-99' not found``, a large model recovers on its own: it
infers that names come from an inventory call, finds one in the tool list, calls
it, and retries with a corrected name. A small model does none of that. It
either surfaces the raw error to the user as a dead end, or — the failure mode
issue #31 actually reported — smooths it over into a confident, wrong summary.

The difference between those two outcomes is entirely in the message text.
``VM 'web-99' not found. Run list_vms (filter by name, e.g. 'web-99*') to see
available VMs and copy an exact name.`` converts recovery from an inference
problem into an instruction-following problem, which is precisely the thing weak
models remain good at. Every point scored here moves one more failure across
that line.

The three dimensions
--------------------
``names_input``    — the message interpolates the offending value, or states the
                     valid range/set it violated. Without this the model cannot
                     tell which of several arguments was wrong.
``states_remedy``  — an actionable instruction ("run", "check", "set", "copy an
                     exact name"), not just a diagnosis.
``names_artifact`` — names the specific tool, CLI command, env var, or file to
                     act on. This is what makes the remedy executable rather
                     than aspirational; a model told to "verify connectivity"
                     without being told *how* will invent a command.

How to read the score
---------------------
A 0–100 index over all raise sites × three dimensions. **>70** most failures are
self-correcting for a weak model; **50–70** the common paths teach and the long
tail does not; **<50** errors are mostly dead ends. ``names_input`` is usually
near-saturated because f-strings make it nearly free — the signal lives in
``states_remedy`` and ``names_artifact``, so read those per-dimension figures
before the aggregate.

The ``dead_end_errors`` list in the detail block is the actionable output of this
whole file: those are the exact messages to rewrite next, in priority order.
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

from ._scoring import Score
from ._skill import CLI_NAME, PACKAGE, SERVER_MODULE

pytestmark = pytest.mark.capability

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[3] / PACKAGE

#: Imperative recovery language. Deliberately verb-led: "not found" is a
#: diagnosis, "run list_vms" is a remedy, and only the second one helps.
REMEDY_MARKERS = (
    "run ",
    "check ",
    "set ",
    "use ",
    "copy ",
    "edit ",
    "verify ",
    "try ",
    "see ",
    "install ",
    "configure ",
    "add ",
    "remove ",
    "retry",
    "re-run",
    "rerun",
    "must be",
    "expected ",
    "did you mean",
    "available:",
    "supported:",
    "choose ",
    "pick ",
    "specify ",
    "provide ",
    "pass ",
    "ensure ",
)

#: Concrete things a model can act on: a CLI, a tool name, a config file, an
#: env var. Detected structurally rather than by keyword where possible.
ARTIFACT_MARKERS = (
    CLI_NAME,
    "config.yaml",
    "config.example.yaml",
    ".env",
    "doctor",
    "list_",
    "get_",
    "_mcp",
    "environment variable",
    "--",
)


def _iter_raise_messages():
    """Yield ``(file, lineno, template, interpolates)`` for every literal raise.

    ``template`` renders f-string holes as ``{}`` so the static text can be
    scored; ``interpolates`` records whether any hole existed at all, which is
    the structural form of "names the offending input".
    """
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):  # pragma: no cover - unreadable source
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
                continue
            if not node.exc.args:
                continue
            arg = node.exc.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield (path.name, node.lineno, arg.value, False)
            elif isinstance(arg, ast.JoinedStr):
                text = "".join(
                    v.value if isinstance(v, ast.Constant) else "{}" for v in arg.values
                )
                holes = any(isinstance(v, ast.FormattedValue) for v in arg.values)
                yield (path.name, node.lineno, text, holes)


def _grade(text: str, interpolates: bool) -> dict[str, bool]:
    low = text.lower()
    states_range = any(k in low for k in ("must be", "available:", "supported:", "expected "))
    return {
        "names_input": interpolates or states_range,
        "states_remedy": any(m in low for m in REMEDY_MARKERS),
        "names_artifact": any(m in low for m in ARTIFACT_MARKERS),
    }


@pytest.fixture(scope="session")
def graded_errors():
    return tuple(
        (f, ln, text, _grade(text, holes)) for f, ln, text, holes in _iter_raise_messages()
    )


def test_error_actionability_index(board, graded_errors):
    """Record the aggregate index and name the dead ends worth rewriting."""
    assert graded_errors, "found no raise sites to score — has the package layout moved?"

    dims = ("names_input", "states_remedy", "names_artifact")
    earned = sum(sum(g.values()) for *_r, g in graded_errors)
    possible = len(graded_errors) * len(dims)
    per_dimension = {
        d: round(100.0 * sum(g[d] for *_r, g in graded_errors) / len(graded_errors), 1)
        for d in dims
    }

    dead_ends = [
        {"where": f"{f}:{ln}", "message": text[:100], "missing": sorted(k for k, v in g.items() if not v)}
        for f, ln, text, g in graded_errors
        if not g["states_remedy"] and not g["names_artifact"]
    ]

    score = board.add(
        Score(
            name="error_actionability",
            value=earned,
            maximum=possible,
            detail={
                "raise_sites": len(graded_errors),
                "per_dimension_pct": per_dimension,
                "dead_end_count": len(dead_ends),
                "dead_end_errors": dead_ends[:15],
            },
        )
    )
    print(f"\n[capability] error_actionability = {score.pct}%  ({earned}/{possible})")
    print(f"             per-dimension: {per_dimension}")
    print(f"             dead ends (no remedy, no artifact): {len(dead_ends)}/{len(graded_errors)}")

    assert score.pct >= 35.0, (
        f"error messages collapsed to {score.pct}% actionable — failures are now dead "
        f"ends for a model that cannot infer recovery. Worst: {dead_ends[:5]}"
    )


def test_teaching_error_rate(board, graded_errors):
    """Share of errors carrying *both* a remedy and something concrete to act on.

    Stricter than the aggregate and closer to what CLAUDE.md actually mandates:
    an error that names the bad value but not the fix still leaves a weak model
    stuck. This is the number to move.
    """
    teaching = [g for *_r, g in graded_errors if g["states_remedy"] and g["names_artifact"]]
    score = board.add(
        Score(
            name="teaching_error_rate",
            value=len(teaching),
            maximum=len(graded_errors),
            unit="messages",
        )
    )
    print(f"\n[capability] teaching_error_rate = {score.pct}%  ({len(teaching)}/{len(graded_errors)})")
    assert score.pct >= 15.0, "almost no error message tells the model how to recover"


def _error_returns_in_server():
    """Yield ``(lineno, is_dict, has_hint, hint_text)`` for each caught-error return.

    Scanned statically out of the MCP server module rather than by calling a
    wrapper, because the family does not agree on one: this skill may use a
    decorator, a shared helper, or a hand-written ``try/except`` inside every
    tool. The static form covers all three, and covers the hand-written case
    *exhaustively* — which is the one that drifts, since each site is written
    independently and nothing forces them to match.
    """
    module = importlib.import_module(SERVER_MODULE)
    server_dir = pathlib.Path(module.__file__).parent

    def _resolve(node) -> str:
        """Render a hint expression as text, following module-level constants.

        Hoisting a shared hint into a constant (``_DOCTOR_HINT``) is the better
        pattern than repeating a literal at every call site, so the scan must
        follow the reference — otherwise the rubric would quietly reward
        copy-paste over the cleaner form.
        """
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.JoinedStr):
            # Resolve interpolations too, not just the literal segments. The
            # first version joined only Constant parts, so
            # `f"Error: {msg} {_DOCTOR_HINT}"` rendered as "Error:  " and the
            # hint vanished — scoring a centralised, hint-carrying wrapper as
            # though it returned a bare string. An eval that misreads the
            # better pattern as the worse one is worse than no eval.
            parts = []
            for piece in node.values:
                if isinstance(piece, ast.Constant):
                    parts.append(str(piece.value))
                elif isinstance(piece, ast.FormattedValue):
                    parts.append(_resolve(piece.value))
            return "".join(parts)
        if isinstance(node, ast.Name):
            # Resolve against the module the *source file* belongs to, not the
            # server module. A hint hoisted into `_DOCTOR_HINT` in a helper file
            # returned "" when looked up on `server`, scoring a hint-carrying
            # payload as having none.
            if node.id in file_constants:
                return file_constants[node.id]
            return str(getattr(module, node.id, ""))
        return ""

    # Walk every module in the server package, not just server.py: skills split
    # their error wrapping across helpers (`_shared.py`, `tools/*.py`), and a
    # scan of one file would silently miss those sites — reporting a clean
    # score for a surface it never looked at.
    handlers = []
    for source in sorted(server_dir.rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8", errors="replace"))
        # Module-level string constants of this file, so a hint hoisted into a
        # constant resolves in the file that defines it.
        consts = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    for tgt in stmt.targets:
                        if isinstance(tgt, ast.Name):
                            consts[tgt.id] = stmt.value.value
        handlers.extend(
            (n, consts) for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)
        )

    for handler, file_constants in handlers:
        for node in ast.walk(handler):
            if not (isinstance(node, ast.Return) and node.value is not None):
                continue
            value = node.value
            if isinstance(value, ast.Dict):
                keys = {k.value for k in value.keys if isinstance(k, ast.Constant)}
                if "error" not in keys:
                    continue
                hint = ""
                for k, v in zip(value.keys, value.values):
                    if isinstance(k, ast.Constant) and k.value == "hint":
                        hint = _resolve(v)
                yield (node.lineno, True, bool(hint), hint, "items" in keys)
            elif isinstance(value, (ast.Constant, ast.JoinedStr)):
                text = _resolve(value)
                if text.lower().lstrip().startswith("error"):
                    yield (node.lineno, False, False, text, False)


def test_tool_failure_payloads_are_self_describing(board):
    """Every caught-error return in the MCP server must carry a usable next step.

    This is the most-seen error surface in the skill: it wraps *all* tool
    failures, including ones whose underlying message scored well above. Two
    properties matter beyond the message text.

    A **dict with a hint** keeps a failure machine-distinguishable from a result.
    A bare ``"Error: ..."`` string is the failure mode worth naming: the model
    receives what looks like ordinary tool output, and a weak model summarises it
    to the user as a finding rather than recognising it as a fault.

    A payload carrying ``items`` would be worse still — a failed call that reads
    as a successful empty page is issue #31's exact reported symptom, so that one
    is asserted outright rather than merely scored.
    """
    sites = tuple(_error_returns_in_server())
    assert sites, "found no error returns in the MCP server — has the module moved?"

    dict_shaped = [s for s in sites if s[1]]
    with_hint = [s for s in sites if s[2]]
    actionable_hint = [s for s in sites if any(m in str(s[3]).lower() for m in ARTIFACT_MARKERS)]
    string_shaped = [s for s in sites if not s[1]]
    leaks_items = [s for s in sites if s[4]]

    checks = len(dict_shaped) + len(with_hint) + len(actionable_hint)
    score = board.add(
        Score(
            name="tool_failure_payload_quality",
            value=checks,
            maximum=len(sites) * 3,
            unit="checks",
            detail={
                "error_return_sites": len(sites),
                "dict_shaped": len(dict_shaped),
                "carries_hint": len(with_hint),
                "hint_names_artifact": len(actionable_hint),
                "bare_string_error_lines": [s[0] for s in string_shaped],
            },
        )
    )
    print(
        f"\n[capability] tool_failure_payload_quality = {score.pct}%  "
        f"({len(sites)} sites: {len(dict_shaped)} dict-shaped, "
        f"{len(with_hint)} with hint, {len(actionable_hint)} actionable)"
    )
    if string_shaped:
        print(f"             bare-string errors at lines: {[s[0] for s in string_shaped]}")

    assert not leaks_items, (
        "an error payload now carries 'items' — a failed call can be read as a "
        "successful empty result, which is issue #31's exact failure mode"
    )
    assert score.pct >= 30.0, "tool failure payloads no longer tell the model anything"
