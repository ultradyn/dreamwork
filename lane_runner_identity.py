"""The single source for runner identity — both runner concepts (#1113, #1130).

Two fleet probes must agree about the fleet: the tick line
(``lane_liveness``) and ``status.json`` (``status_sync``). Before this
module they agreed only because someone kept two copies of the runner
list in step by hand — the exact mechanism behind the #868 / #1084
"the fleet count lied" recurrences: invisible drift under a delegation
target, not a loud failure. This module is the one place BOTH runner
tuples live (``LANE_RUNNERS`` and ``DISPATCH_RUNNERS``), their
bytes-level classifiers, and the ancestor walker; both probes import
them, so the two counts agree by construction.

Two concepts, deliberately unequal (#136 three-state, #675):
  - ``LANE_RUNNERS`` — a process whose argv[0] basename is one of these
    is a LANE RUNNER. The cwd-live channel (tick line) sees all of them.
  - ``DISPATCH_RUNNERS`` — a process whose argv[0] basename is one of
    these is a DISPATCHED lane (started by dispatch_lane.py). It is
    NARROWER: every dispatch runner is a lane runner, but an Agent-tool
    lane (claude/grok/codex) is a lane runner that is NOT a dispatch
    runner — ``found`` routes it to ``agent_tool`` instead. The two
    tuples MUST stay distinct and MUST NOT be collapsed.

They share a home so a reader extending either is forced past the other:
the hardcoded ``== "ccc"`` that preceded ``DISPATCH_RUNNERS`` was a
silent second classifier (#1113 ended the first copy; #1124 named the
second; #1130 moved it here beside its sibling).

Dependencies point INTO this module (both ``lane_liveness`` and
``status_sync`` import it); it imports nothing from either, so it sits
below them in the layering and cannot take part in a cycle. It depends
only on the stdlib ``os`` — a runner-name check needs nothing else.

Why a module of its own rather than a home inside ``lane_liveness``:
"runner identity" (which argv[0] counts, how to walk ancestors) is a
lower-level primitive than "liveness" (which builds on identity plus
locks plus cwd). Status reading its identity from a module called
``lane_liveness`` would invert that layering and couple the classifier
to all of liveness's imports.
"""

from __future__ import annotations

import os


# Known lane runners — a process whose argv[0] basename is one of these is a
# lane runner; a head/grep/tail/bash sharing the cwd is NOT. Copies
# reaper.parse_cmdline's SHAPE (a basename check, not a cwd-prefix match) so
# the cwd channel and the lock channel agree on what counts as a runner. THE
# single source — both fleet probes read this tuple, so a name added here is
# seen by both at once (#1113).
LANE_RUNNERS = ("ccc", "claude", "grok", "codex")


def is_lane_runner(raw: bytes) -> bool:
    """Whether ``raw`` cmdline's argv[0] basename is a known lane runner.

    A ``head -3``, a ``grep``, a ``tail -F``, a ``bash`` — these share a
    lane's cwd but are NOT lane processes. Copies reaper.parse_cmdline's
    shape: a basename check on the NUL-split argv[0], never a substring of
    the raw cmdline (the /proc cmdline is NUL-separated, #716). Takes raw
    BYTES so a caller that already read /proc/<pid>/cmdline can reuse that
    read — no second shell-out, so a pattern in this tool's own command
    line can never match itself.

    This is the ONE classifier. ``status_sync._is_lane_runner(pid)`` is a
    thin I/O wrapper that reads /proc then calls this; ``lane_liveness``
    calls it directly with its already-read bytes. A future basename
    normalisation lands here and is seen by both at once.
    """
    if not raw:
        return False
    first = raw.split(b"\x00", 1)[0]
    return os.path.basename(first.decode("utf-8", "replace")) in LANE_RUNNERS


# Dispatch runners — a process whose argv[0] basename is one of these is a
# DISPATCHED lane (started by dispatch_lane.py), distinct from an Agent-tool
# lane (#675: a non-ccc process with a lane cwd). NARROWER than LANE_RUNNERS:
# every dispatch runner is a lane runner, but the cwd-live channel ALSO sees
# Agent-tool lanes (claude/grok/codex), which are NOT dispatches — so the two
# concepts MUST stay distinct and MUST NOT be collapsed (#136 three-state).
# Lived beside LANE_RUNNERS (#1130) so both concepts share one home and a
# reader extending either is forced past the other: the hardcoded ``== "ccc"``
# this replaces was a silent second classifier (#1113 ended the first copy;
# #1124 named the second).
DISPATCH_RUNNERS = ("ccc",)


def is_dispatch_runner(raw: bytes) -> bool:
    """Whether ``raw`` cmdline's argv[0] basename is a dispatch runner.

    The bytes-level classifier for the dispatch concept, parallel to
    ``is_lane_runner`` for the lane-runner concept. Takes raw BYTES so a
    caller that already read /proc/<pid>/cmdline reuses that read (no second
    shell-out; a NUL-containing cmdline cannot parse as a dispatch runner by
    accident, #716). ``status_sync._is_ccc_proc`` is the pid-level I/O
    wrapper; this is the classifier. The two classifier functions are
    deliberately separate — they read two deliberately unequal tuples, so
    the #136 three-state distinction (found / cwd_live / agent_tool) is
    expressible. Do not merge their bodies or derive one tuple from the other.
    """
    if not raw:
        return False
    first = raw.split(b"\x00", 1)[0]
    return os.path.basename(first.decode("utf-8", "replace")) in DISPATCH_RUNNERS


def ancestor_pids() -> set[int]:
    """Pids from ``os.getpid()`` up to init via ``/proc/<pid>/stat`` field 4.

    #729: a process that is an ancestor of the thing doing the counting is by
    construction not a lane. Exact, not heuristic, no allowlist — the
    coordinator (claude) started in a worktree that was later removed, so its
    cwd really IS deleted and the reading is correct; what was wrong was the
    CLASSIFICATION. Walking the ppid chain identifies it as self, not a
    phantom. Field 2 (comm) may contain spaces and parens, so we cut between
    the first '(' and the last ')' like reaper.parse_proc_stat before indexing
    field 4 (ppid) as ``rest[1]`` (fields 3.. follow comm).
    """
    ancestors: set[int] = set()
    pid = os.getpid()
    seen: set[int] = set()           # cycle guard against a corrupt stat file
    while pid > 1 and pid not in seen:
        ancestors.add(pid)
        seen.add(pid)
        try:
            with open("/proc/%d/stat" % pid) as f:
                text = f.read()
        except OSError:
            break
        rparen = text.rfind(")")
        if rparen < 0:
            break
        rest = text[rparen + 2:].split()
        if len(rest) < 2:
            break
        try:
            pid = int(rest[1])        # field 4 (ppid) == index 1 after comm
        except ValueError:
            break
    return ancestors
