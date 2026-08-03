"""Shared process identity probes for Dreamwork lanes."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from worktree_paths import WORKTREE_DIR
from worktree_paths import worktree_roots


class LivenessUnknown(Exception):
    """The probe could not determine whether a lane is live."""


@dataclass(frozen=True)
class FinishedWork:
    """The work a dead lane left behind, split the way ``dev/reap.py`` splits it.

    ``finished`` today is one word for a lane whose runner is gone, whether it
    reported and exited, died holding nothing, or died holding a day's work on
    its branch or in a dirty tree (#1154). The dangerous state — work that
    reaping would destroy or that sits unreviewed on a branch — looked exactly
    like the disposable one, because the classifier never looked at the work.

    These counts mirror ``dev/reap.py``'s ``tracked-dirty=N untracked=N
    ignored=N`` split on purpose: that is the model this repo already trusts for
    the decision "would work be lost", and a second taxonomy would drift. The
    split keeps ignored churn (``__pycache__``, ``lane.lock`` — present in every
    lane) OUT of ``holding_work``, so a lane with only cache dirt reads clean
    and not as "died holding work".

      - ``tracked_dirty`` — modified or staged tracked files. Work that reaping
        destroys (the ``cx-1140ingest`` shape: 448 insertions, zero commits).
      - ``untracked`` — notable untracked paths beyond the per-lane scratch set
        (``BRIEF.md``). A deliverable the lane forgot to commit.
      - ``unmerged`` — commits on the branch not on the base. Work on the branch
        (the ``cx-1060label6`` shape: 8 commits of accepted work).
      - ``ignored`` — ignored churn, named for audit (#868) but never counted
        toward ``holding_work``.

    ``commits_known`` is False when the branch could not be compared to the base
    (no ``master``, detached): ``unmerged`` is then 0 and the tick line says so
    rather than asserting an all-clear (#136).
    """

    tracked_dirty: int
    untracked: int
    ignored: int
    unmerged: int
    commits_known: bool = True

    @property
    def holding_work(self) -> bool:
        """Whether the dead lane left work that must not be silently reaped.

        Keys on the WORKING TREE and the branch, never on the runner: a lane
        that reported and then died has a clean tree and reads ``False`` here,
        so it is not classified as work-losing because its process vanished.
        Commit count alone does NOT decide this — a lane can hold a day's work
        with zero commits (#1154).
        """
        return self.tracked_dirty > 0 or self.untracked > 0 or self.unmerged > 0


# The per-lane scratch every lane carries, modelled on reap.EXPECTED_UNTRACKED.
# BRIEF.md is written into each worktree by the coordinator and never tracked;
# suppressing it would hide nothing, but counting it would call an idle lane
# "holding work". Kept as a literal of one name (#612): a fact about the lane
# model, not a computed value.
_FINISHED_EXPECTED_UNTRACKED = frozenset({"BRIEF.md"})

# Disposable ignored entries present in every lane (__pycache__, *.pyc,
# *.lock). Mirrors reap._is_disposable_ignored so the two never disagree on
# what "ignored churn" means; the comment there is the authority.
_FINISHED_DISPOSABLE_IGNORED_DIRS = frozenset(
    {".pytest_cache", ".ruff_cache", "node_modules"})


def _is_disposable_ignored(path: str) -> bool:
    parts = path.split("/")
    return (
        path.endswith((".pyc", ".lock"))
        or any(part in _FINISHED_DISPOSABLE_IGNORED_DIRS for part in parts))


def _finished_status_kinds(raw: bytes):
    """Parse ``git status -z --ignored`` into (kind, path) rows.

    Re-states reap._status_paths's porcelain walk rather than importing the
    dev/ script: lane_liveness is a top-level probe imported by tick_line and
    status_sync, and a dev/ import with its land_lane fallback would be the
    wrong direction. The split is the model reap trusts; the two are kept in
    sync by the test that builds all three tree states (#1154).
    """
    fields = raw.split(b"\0")
    rows = []
    index = 0
    while index < len(fields) and fields[index]:
        field = fields[index]
        if len(field) < 4:
            return None
        code = field[:2].decode("ascii", errors="replace")
        path = field[3:].decode("utf-8", errors="surrogateescape")
        index += 1
        if "R" in code or "C" in code:
            if index >= len(fields) or not fields[index]:
                return None
            index += 1
        kind = ("untracked" if code == "??"
                else "ignored" if code == "!!" else "tracked")
        rows.append((kind, path))
    return rows


def classify_finished_work(
        worktree: Path, *, base: str = "master") -> FinishedWork | None:
    """Classify the work a finished lane's worktree holds (#1154).

    Returns None when the worktree is not a git repo (``git status`` failed),
    so the caller renders ``finished`` without a work verdict rather than
    guessing clean. Mirrors reap's tracked/untracked/ignored split; see
    :class:`FinishedWork` for why each bucket is reported separately.
    """
    status = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain=v1", "-z",
         "--untracked-files=all", "--ignored"],
        capture_output=True, check=False,
    )
    if status.returncode:
        return None
    rows = _finished_status_kinds(status.stdout)
    if rows is None:
        return None
    tracked = sum(1 for kind, _ in rows if kind == "tracked")
    ignored = sum(1 for kind, _ in rows if kind == "ignored")
    notable_untracked = sum(
        1 for kind, path in rows
        if kind == "untracked" and path not in _FINISHED_EXPECTED_UNTRACKED)
    # Disposable ignored churn (__pycache__, *.lock) is present in every lane;
    # subtract it from the reported ignored count so a clean lane reads
    # ignored=0 and the audit trail shows the classifier saw the churn and
    # correctly discounted it (#868).
    notable_ignored = sum(
        1 for kind, path in rows
        if kind == "ignored" and not _is_disposable_ignored(path))
    cherry = subprocess.run(
        ["git", "-C", str(worktree), "cherry", base, "HEAD"],
        capture_output=True, text=True, check=False,
    )
    commits_known = cherry.returncode == 0
    unmerged = 0
    if commits_known:
        unmerged = sum(
            1 for line in cherry.stdout.splitlines()
            if line.startswith("+ "))
    return FinishedWork(
        tracked_dirty=tracked,
        untracked=notable_untracked,
        # Report NON-disposable ignored so the count is a signal, not noise:
        # a stray hand-written file inside an ignored dir is still evidence.
        ignored=notable_ignored,
        unmerged=unmerged,
        commits_known=commits_known,
    )


@dataclass(frozen=True)
class FinishedLane:
    """A dispatched lane whose recorded runner is no longer present.

    ``work`` classifies what the dead lane left behind (#1154): None when the
    worktree could not be classified (no git repo), otherwise a split that
    separates the dangerous state — died holding work on the branch or in a
    dirty tree — from the disposable one. The runner being gone is the same
    fact for both; the work is what differs.
    """

    lane: str
    task: object
    pid: object
    identity: str
    work: FinishedWork | None = None


@dataclass(frozen=True)
class LiveLane:
    """A live lane's progress verdict — the LIVE-side dimension #1154 left open.

    ``inspect_lanes`` already answers "is a runner alive" (#1084 lock + cwd
    channels). It did NOT answer "is that runner able to do work": a
    permission-wedged lane holds a live pid and reads live, indistinguishable
    from a computing one (#1155 — a wedged lane is indistinguishable from a
    working one in the fleet count). This verdict splits the live set so the
    fleet count no longer asserts a working count it never measured.

    States (#136 — none collapsed into another, and "cannot tell" is one):

      - ``working`` — positive evidence the runner is computing: accumulated
        CPU at or above ``WORKING_CPU_FLOOR_S``. A process that has burned
        real cycles has done work. (Case C: 31s CPU at 9 min while its
        transcript sat at 0 bytes; Case B reading the codebase accumulates
        CPU the same way.)
      - ``wedged`` — positive evidence of a SPECIFIC wedge: a marker the
        wedge probe recognised (e.g. a permission-rejection line in the
        runner's log). ``wedged`` is reachable ONLY from a marker — CPU and
        age never produce it — so the dangerous verdict the coordinator might
        act on by destroying work is never made on circumstantial evidence
        alone (Case B has zero commits for 11 min and is never wedged).
      - ``not-yet-observed`` — alive but too young to expect a signal:
        elapsed under ``YOUNG_ELAPSED_S``, CPU below floor, no marker. A lane
        30s after dispatch is NOT wedged; it has not had time to show either
        sign (#1155: a lane 30s after dispatch is not yet observed working).
      - ``unknown`` — cannot tell. Either the signals were unreadable (no pid,
        /proc gone) or present-but-ambiguous: old enough to have produced CPU
        that produced almost none, with no recognised wedge marker. The
        latter is the honest stall signature — a permission-wedge with an
        unfindable log lands here, NOT in ``wedged``, because the probe has no
        positive evidence to name. See ``reason``.

    ``reason`` names the deciding signal so the tick line can carry it: which
    marker, how much CPU, how old, or why the probe could not read.

    The thresholds are HEURISTICS derived from the brief's measured Cases A/C
    (#967: those are few observations, not proof). They are conservative and
    unverifiable against the live fleet — disturbing live lanes is forbidden —
    and their blind spots are stated in :func:`classify_live_lane`.
    """

    lane: str
    state: str
    reason: str


# Live-progress states (module constants so the tick line and callers agree by
# symbol, and a typo is a NameError rather than a silent miss — #136: states
# must not collapse, and a misspelled state string folds silently into nothing).
LIVE_WORKING = "working"
LIVE_WEDGED = "wedged"
LIVE_NOT_YET = "not-yet-observed"
LIVE_UNKNOWN = "unknown"

# A process that has burned this much CPU has done real work. Case C's 31s is
# an order of magnitude above; a permission-wedge's ~0 is well below; any lane
# that has exec'd a tool clears a few seconds. Conservative and named, not
# magic: see #967 — these encode the brief's two data points, they do not prove
# them, and they cannot be re-measured without disturbing the live fleet.
WORKING_CPU_FLOOR_S = 3.0
# Under this wall-clock age a lane is too young to expect accumulated CPU or a
# wedge marker; it is "not yet observed working", never wedged. The brief's
# "30 seconds after dispatch" sits well under it.
YOUNG_ELAPSED_S = 90.0


@dataclass(frozen=True)
class LaneInspection:
    """One checkable view of lane locks, worktrees, and process evidence."""

    live: tuple[str, ...]
    worktree_only: tuple[str, ...]
    process_only: tuple[str, ...]
    examined_processes: int
    finished: tuple[FinishedLane, ...] = ()
    cwd_live: tuple[str, ...] = ()
    live_liveness: tuple[LiveLane, ...] = ()


def pid_alive(pid) -> bool:
    """Return the result of ``kill -0``; raise when it cannot be interpreted."""
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (TypeError, ValueError):
        raise LivenessUnknown("unparseable dreamers pid: %r" % (pid,))
    except OSError as exc:
        raise LivenessUnknown("kill -0 %r failed: %s" % (pid, exc)) from exc


def read_proc_cwd(pid: int) -> str | None:
    """Return ``/proc/<pid>/cwd``, or None if it disappeared or is unreadable."""
    try:
        return os.readlink("/proc/%d/cwd" % pid)
    except OSError:
        return None


def read_proc_cpu(pid: int) -> tuple[float, float | None] | None:
    """Return ``(cpu_seconds, elapsed_seconds)`` for ``pid`` from ``/proc``.

    ``cpu_seconds`` is accumulated utime+stime; ``elapsed_seconds`` is wall
    time since the process started. Both are the LIVE-side progress signals
    that discriminate a computing runner from a blocked one (#1155): a
    permission-wedged runner is blocked, not computing, so its CPU stays near
    zero while a working one accumulates (Case C: 31s at 9 min).

    Returns None when /proc/<pid>/stat cannot be read (the pid is gone, or
    this is not Linux). The classifier treats None as "no signal" rather than
    as zero, so a vanished runner is ``unknown`` not ``working`` — an absent
    measurement must not read as a zero measurement (#136).

    When the stat IS readable but ``/proc/uptime`` is not, ``elapsed_seconds``
    is ``None`` (age unknown) while ``cpu_seconds`` carries a real value. This
    is the #136 distinction: "cannot tell the age" is a state (``unknown``),
    not a default that folds into ``not-yet-observed`` (elapsed 0 < floor).
    """
    try:
        raw = Path("/proc/%d/stat" % int(pid)).read_text()
    except (OSError, ValueError):
        return None
    # comm is parenthesised and may contain spaces/parens; split after the
    # last ')'. Fields after comm are 1-indexed from 2: utime=14, stime=15,
    # starttime=22 → indices 11, 12, 19 in the post-comm list.
    rparen = raw.rfind(")")
    if rparen < 0:
        return None
    fields = raw[rparen + 2:].split()
    if len(fields) <= 19:
        return None
    try:
        utime = int(fields[11])
        stime = int(fields[12])
        starttime = int(fields[19])
    except (ValueError, IndexError):
        return None
    try:
        hz = os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError):
        hz = 100
    cpu_seconds = (utime + stime) / hz if hz else 0.0
    try:
        with open("/proc/uptime") as handle:
            uptime = float(handle.read().split()[0])
    except (OSError, ValueError, IndexError):
        # CPU is readable but uptime is not: return CPU with ABSENT age so the
        # classifier reports unknown ("cannot tell") rather than folding a
        # missing age into not-yet-observed (the #136 collapse, #1155 P1 #2).
        return (cpu_seconds, None)
    now = time.time()
    start_epoch = (now - uptime) + (starttime / hz if hz else 0)
    return (cpu_seconds, max(0.0, now - start_epoch))


# Untracked paths that are NOT a deliverable — lane scratch and tool churn a
# working lane produces without committing. This is the exclusion list the P1
# fix hinges on (#1155 round 4): too broad and the hazard returns (every lane
# looks busy forever), too narrow and a lane holding an uncommitted deliverable
# reads wedged. Each entry names what it is and why excluding it is safe:
#
#   BRIEF.md — coordinator-written per-lane scratch, never tracked (#1154's
#     same exclusion). Counting it would call an idle lane "in progress".
#   .pytest_cache — pytest creates this on every run; the repo's .gitignore
#     omits .pytest_cache/ (it lists __pycache__/ but NOT .pytest_cache/), so
#     .pytest_cache/ reads as ?? (untracked) in a real fleet worktree. Tool
#     churn, not a deliverable.
#
# NO .dreamwork ENTRY (#1155 round 4). The round-3 blanket .dreamwork entry
# was path-specific in NAME but top-level-component in EFFECT, so it discarded
# EVERY untracked path under .dreamwork/ — including deliverables. The .dreamwork/
# tree holds BOTH lane-local state and deliverables (#136 — two states), and the
# enumeration shows the gitignore already separates them:
#
#   LANE-LOCAL STATE (all gitignored → invisible to git status --porcelain,
#     which does NOT pass --ignored — they appear as !!, never ??):
#     status.json, lane.lock, .lane.lock.*, inbox.md, user-events.sqlite3*,
#     ledger.sqlite3*, run-mode, posture, subagent-policy, question-sigs.json,
#     expedite, .ledger-lint-mtimes.json, .status-keys, plugin-commands.json,
#     watch-events.log, submissions.log, applied.md(.lock), chats-v1/,
#     launch-attempts/, inbox-archive/, salvage/, docs/briefs/
#   DELIVERABLES (tracked or NOT gitignored → appear as ?? when new = progress):
#     docs/*.md (design docs, plans, audits), dreams/, evidence/, relay/,
#     reports/, review/, answers.md, lane-*-report.md, lessons.md,
#     questions.md, tasks.md, skill-version, watch-port, watch-tint
#
# Because git status --porcelain never lists gitignored files, the blanket
# .dreamwork entry was protecting against nothing visible while discarding
# every deliverable whose top-level component was .dreamwork. Removing it
# lets .dreamwork/docs/plans/foo.md count as progress while gitignored
# state stays invisible. This is #868's both-denominators call: 20+ lane-
# local files are already hidden by .gitignore; 6+ deliverable subtrees were
# wrongly hidden by the exclusion.
#
# __pycache__/ IS gitignored, so .pyc files inside it appear as !! (ignored),
# not ?? (untracked) — no exclusion needed. *.pyc is NOT in the real .gitignore
# (#1155 round 4 P2b), but a root-level .pyc is not normal Python churn (Python
# writes .pyc into __pycache__/); if one appears and counts as progress the
# result is a conservative false-UNKNOWN, never a destructive false-WEDGED.
# The list is the MINIMUM set the real fleet produces as untracked
# non-deliverables: it does not guess at future churn, because an unrecognised
# untracked path is progress (a lane that wrote something new did work), and
# the probe's age and CPU gates still protect against false negatives (#1155
# blind spot at :401).
_LIVE_PROGRESS_UNTRACKED_SCRATCH = frozenset({
    "BRIEF.md", ".pytest_cache"})


def _is_live_progress_scratch(path: str) -> bool:
    """Whether an untracked porcelain path is scratch, not a deliverable.

    Checks the TOP-LEVEL path component: ``.pytest_cache/sub/file`` is scratch
    because ``.pytest_cache`` is, and ``new_module.py`` at the worktree root is
    NOT scratch because its top-level component (itself) is not in the set.
    This is the precise boundary the brief names (#1155 round 3 direction-2):
    ``*.py`` under a scratch dir is scratch; ``new_module.py`` at the root is
    work. ``.dreamwork/`` is NOT in the set (#1155 round 4): its lane-local
    state is gitignored (invisible to --porcelain) and its tracked content is
    deliverables (docs, reports, dreams), so excluding it all discarded work.
    """
    return path.split("/", 1)[0] in _LIVE_PROGRESS_UNTRACKED_SCRATCH


def _worktree_has_progress(worktree: Path) -> bool | None:
    """Whether a live lane's worktree shows git progress (#1155).

    Returns True when the branch has commits ahead of ``master``, the working
    tree has dirty tracked files, OR an untracked deliverable exists — any is
    positive evidence the runner did work. Returns False when the worktree is
    at base with a clean tree and only scratch untracked files (the shape of a
    permission-wedged lane that never got past its first rejected ``git
    status``). Returns None when git could not answer (not a repo, git failed)
    — the caller treats None as "cannot tell" rather than guessing clean
    (#136).

    An untracked deliverable is an untracked file BEYOND known lane scratch
    (BRIEF.md, .pytest_cache — see ``_LIVE_PROGRESS_UNTRACKED_SCRATCH``). A
    lane that wrote ``new_module.py`` and has not committed it is the NORMAL
    state of a lane mid-increment, and classifying it wedged would point the
    destructive reaping tool at precisely the lane whose work exists only in
    the working tree (#1155 round 3 P1 / #702 / #760: reap separates untracked
    from ignored for exactly this reason). A lane whose only work is a new
    ``.dreamwork/docs/plans/foo.md`` is the same case under a tracked subtree
    (#1155 round 4 P1).
    """
    cherry = subprocess.run(
        ["git", "-C", str(worktree), "cherry", "master", "HEAD"],
        capture_output=True, text=True, check=False)
    if cherry.returncode != 0:
        return None
    has_commits = any(
        line.startswith("+ ") for line in cherry.stdout.splitlines())
    if has_commits:
        return True
    status = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        capture_output=True, text=True, check=False)
    if status.returncode != 0:
        return None
    for line in status.stdout.splitlines():
        if not line:
            continue
        if line.startswith("?? "):
            # An untracked file BEYOND known scratch is a deliverable (#1155
            # round 3 P1): a lane that wrote new_module.py and has not
            # committed it is doing work, not wedged.
            if not _is_live_progress_scratch(line[3:]):
                return True
        else:
            # Dirty tracked file — the runner modified committed code.
            return True
    return False


def _default_wedge_probe(
        worktree: Path, pid: int, *,
        cpu_seconds: float | None,
        elapsed_seconds: float | None) -> str | None:
    """The production default wedge probe (#1155 round 2).

    A real wedged lane — one whose opencode runner auto-rejected its own
    worktree on the first ``git status`` — leaves two kinds of evidence:
    on disk (worktree at base, zero commits, clean tree) and in the process
    table (near-zero CPU after enough wall time to have produced some). This
    probe combines both: it returns a wedge marker ONLY when the process is
    old enough to expect progress, is NOT accumulating CPU, and the worktree
    shows no git progress. A lane that fails any of those gates returns None.

    WHAT IT CAN SEE (#651):
      - git commits ahead of master and dirty tracked files (on-disk progress)
      - CPU and elapsed (passed from the cpu_reader the tick already runs)

    WHAT IT CANNOT SEE:
      - a wedge whose runner burns CPU in a retry loop (CPU ≥ floor → the
        probe returns None; classify_live_lane then reads WORKING — positive
        evidence of computation wins, #1155 P1 #1)
      - a wedge whose runner made one commit then hung (the commit is
        progress; the probe returns None, and the lane reads UNKNOWN not
        WEDGED — a false negative, not a false positive)
      - a wedge on a non-Linux host or a gone pid (cpu is None → None)
      - the auto-reject log message itself (runner output is redirected
        outside the worktree by the dispatcher; this probe reads what IS
        in the worktree and the process table, not what is not)

    The marker is FRESH and RUNNER-BOUND (#1155 P1 #1): it is recomputed from
    the live worktree and the live process on every tick, never from a log
    phrase that appeared once and persists forever. A lane that recovers and
    starts committing or burning CPU drops the marker on the next tick.
    """
    # A young lane has not had time to produce commits or CPU — not a wedge.
    if elapsed_seconds is None:
        return None
    if elapsed_seconds < YOUNG_ELAPSED_S:
        return None
    # A computing runner is not wedged regardless of worktree state.
    if cpu_seconds is not None and cpu_seconds >= WORKING_CPU_FLOOR_S:
        return None
    # Check on-disk progress. None = cannot tell (not a repo, git failed) →
    # degrade to no marker so the lane reads UNKNOWN, not a false WEDGED.
    progress = _worktree_has_progress(worktree)
    if progress is None or progress:
        return None
    return ("permission-wedge: live runner %.0fs, %.1fs cpu, no git progress"
            % (elapsed_seconds, cpu_seconds or 0.0))


def classify_live_lane(
        lane: str,
        cpu_seconds: float | None,
        elapsed_seconds: float | None,
        wedge_marker: str | None) -> LiveLane:
    """The pure LIVE-side state machine for one lane (#1155).

    Inputs are the MEASURED signals (so tests inject numbers, never a real
    process); the verdict is the four-state split documented on
    :class:`LiveLane`. Ordering is load-bearing:

      1. CPU at/above floor → ``working``. Checked FIRST (#1155 P1 #1): a
         rejected call proves a rejection happened, not that the runner never
         recovered — and 120 CPU-seconds is positive evidence it did. So a
         marker paired with high CPU reads ``working``, not ``wedged``.
      2. wedge marker → ``wedged``. Reachable only when CPU is below floor,
         so a retry-loop wedge that burns CPU reads ``working`` at step 1
         (a known false negative, stated below — better than a false positive
         that flags a working lane for destruction).
      3. young (elapsed under floor) → ``not-yet-observed`` (too soon to
         expect CPU or a marker; never wedged).
      4. otherwise → ``unknown`` (the honest stall signature).

    Steps 3-4 can NEVER produce ``wedged``: only the marker can, and only
    when CPU has already been checked below floor. So the dangerous verdict
    requires BOTH a marker AND low CPU — never CPU/age alone (#1155
    direction-2: flagging Case B wedged because it had not committed would
    kill working).

    BLIND SPOTS stated (#651): a wedge that burns CPU in a tight loop reads
    ``working`` (step 1 wins — positive evidence of computation); a wedge
    whose cause produced one commit then hung reads ``unknown`` (the commit
    is progress, so no marker — a false negative, not a false positive); a
    wedge whose cause has no marker and no worktree progress reads ``wedged``
    if old and low-CPU, ``unknown`` if the age cannot be determined; a young
    lane that is already wedged reads ``not-yet-observed`` until it ages past
    ``YOUNG_ELAPSED_S`` — youth is not innocence, but a marker found under the
    age floor is still reported ``wedged`` (step 1 precedes step 3).
    """
    if cpu_seconds is not None and cpu_seconds >= WORKING_CPU_FLOOR_S:
        return LiveLane(lane, LIVE_WORKING, "%.1fs cpu" % cpu_seconds)
    if wedge_marker:
        return LiveLane(lane, LIVE_WEDGED, wedge_marker)
    if cpu_seconds is None or elapsed_seconds is None:
        return LiveLane(
            lane, LIVE_UNKNOWN,
            "cannot tell: %s" % (
                "no cpu signal" if cpu_seconds is None
                else "process age unknown (/proc/uptime unreadable)"))
    if elapsed_seconds < YOUNG_ELAPSED_S:
        return LiveLane(lane, LIVE_NOT_YET,
                        "alive %.0fs, %.1fs cpu, no marker"
                        % (elapsed_seconds, cpu_seconds))
    return LiveLane(
        lane, LIVE_UNKNOWN,
        "alive %.0fs, %.1fs cpu, no wedge marker — could be a wedge this "
        "probe cannot identify, or a slow worker"
        % (elapsed_seconds, cpu_seconds))


def pid_matches_lane(
        pid, brief,
        *,
        is_pid_alive: Callable[[object], bool] = pid_alive,
        proc_cwd: Callable[[int], str | None] = read_proc_cwd,
) -> bool:
    """Whether ``pid`` is alive and still carries ``brief``'s lane identity."""
    if not is_pid_alive(pid):
        return False
    if not isinstance(brief, str) or not brief:
        raise LivenessUnknown("live pid has no lane brief identity: %r" % pid)

    lane_dir = str(Path(brief).parent)
    cwd = proc_cwd(int(pid))
    if os.path.isabs(lane_dir) and (
            cwd == lane_dir or (cwd and cwd.startswith(lane_dir + os.sep))):
        return True

    try:
        with open("/proc/%d/cmdline" % int(pid), "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise LivenessUnknown("cannot read pid %r identity: %s" % (pid, exc)) from exc

    needles = [brief.encode()]
    if WORKTREE_DIR in Path(brief).parts:
        needles.append(lane_dir.encode())
    return any(needle in raw for needle in needles)


# What counts as a lane runner, and the ancestor-self exclusion (#729), are
# shared with status_sync from lane_runner_identity — the single source — so
# the tick's fleet count and status.json's agree by construction, not by two
# hand-kept lists (#1113: the #868/#1084 "the fleet count lied" defect class
# was two copies drifting). is_lane_runner takes raw BYTES so this channel
# reuses the /proc read the governed-prompt scan already did (no second
# shell-out; a pattern in this tool's own command line can never match itself).
from lane_runner_identity import ancestor_pids as _ancestor_pids  # noqa: E402
from lane_runner_identity import is_lane_runner as _is_lane_runner  # noqa: E402


def _worktree_registry(target: Path) -> tuple[Path, tuple[Path, ...]]:
    """Return the main checkout and registered lanes under its two roots."""
    try:
        result = subprocess.run(
            ["git", "-C", str(target), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        raise LivenessUnknown("cannot list registered worktrees: %s" % exc) from exc
    if result.returncode:
        detail = result.stderr.strip().splitlines()[0] if result.stderr.strip() else "git failed"
        raise LivenessUnknown(
            "cannot list registered worktrees: %s" % detail)
    records = []
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        records.append(Path(line.removeprefix("worktree ")).resolve())
    if not records:
        raise LivenessUnknown("cannot list registered worktrees: git returned no records")
    # Porcelain lists the main checkout first even when invoked from a linked
    # worktree.  The gate breadcrumb is main-owned, so neither the lane roots
    # nor that breadcrumb may be rooted on the invocation checkout.
    main_checkout = records[0]
    roots = tuple(root.resolve() for root in worktree_roots(main_checkout))
    paths = []
    for path in records[1:]:
        if any(path.parent == root for root in roots):
            paths.append(path)
    return main_checkout, tuple(paths)


def _registered_worktrees(target: Path) -> tuple[Path, ...]:
    """Return git-registered lane worktrees under this target's two roots."""
    return _worktree_registry(target)[1]


def _in_flight_gate_worktree(main_checkout: Path) -> Path | None:
    """Return the exact scratch named by the main checkout's gate breadcrumb.

    This deliberately restates ``lint._in_flight_gate_worktree`` instead of
    importing the executable linter into this shared runtime probe.  Its
    identity rule is the same: breadcrumb path, never the ``.gate-*`` name.
    """
    path = main_checkout / ".dreamwork" / "gate-in-flight.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    raw = record.get("gate_worktree")
    if not raw:
        return None
    try:
        return Path(str(raw)).resolve()
    except OSError:
        return None


def _prompt_worktree(raw: bytes, roots: tuple[Path, ...]) -> Path | None:
    """Read only an exact governed ``Worktree:`` line from process argv.

    NULs delimit argv elements, so mapping them to newlines lets the same
    line-anchored grammar read the one prompt argument.  Incidental prose or
    paths such as ``.../.worktrees/review`` are deliberately not identity.
    """
    text = raw.replace(b"\x00", b"\n").decode("utf-8", "replace")
    matches = re.findall(r"^Worktree:\s+([^\r\n]+?)\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        return None
    path = Path(matches[0]).resolve()
    return path if any(path.parent == root for root in roots) else None


def inspect_lanes(
        target: Path,
        *,
        process_entries: list[str] | None = None,
        registered_worktrees: tuple[Path, ...] | None = None,
        read_cmdline: Callable[[int], bytes] | None = None,
        read_cwd: Callable[[int], str | None] | None = None,
        skip_pids: set[int] | None = None,
        work_classifier: Callable[[Path], FinishedWork | None] | None = None,
        read_cpu: Callable[[int], tuple[float, float] | None] | None = None,
        wedge_probe: Callable[[Path, int], str | None] | None = None,
) -> LaneInspection:
    """Inspect the canonical lane locks and report both mismatch directions.

    A lock-confirmed live lane is the intersection of a git-registered
    worktree, its strict lane lock, and the exact process identity checked by
    :func:`pid_matches_lane`. The cwd channel is the dispatch-route-invariant
    fallback (#1084): a hand-dispatched lane has no ``lane.lock`` (every
    follow-up round is dispatched that way), so the lock channel is blind to
    it. The cwd channel names a lane live when a known RUNNER process holds
    the worktree as its cwd — a measurement that cannot vary with dispatch
    route the way a launch-lane-created marker does. Where the two channels
    disagree, the cwd-only lanes are reported in ``cwd_live`` rather than
    silently dropped or silently merged (#136).

    Lockless idle worktrees, finished dispatched lanes, and governed process
    prompts whose worktree is no longer registered are named separately.
    """
    target = target.resolve()
    if process_entries is None:
        try:
            process_entries = os.listdir("/proc")
        except OSError as exc:
            raise LivenessUnknown("cannot enumerate process candidates: %s" % exc) from exc
    pids = [int(entry) for entry in process_entries if entry.isdigit()]
    if not pids:
        raise LivenessUnknown("lane detector examined 0 process candidates")

    if registered_worktrees is None:
        main_checkout, worktrees = _worktree_registry(target)
    else:
        main_checkout = target
        worktrees = tuple(path.resolve() for path in registered_worktrees)
    roots = tuple(root.resolve() for root in worktree_roots(main_checkout))
    gate_scratch = _in_flight_gate_worktree(main_checkout)
    if gate_scratch is not None:
        worktrees = tuple(path for path in worktrees if path != gate_scratch)
    registered = {path.resolve() for path in worktrees}
    reader = read_cmdline or (
        lambda pid: Path("/proc/%d/cmdline" % pid).read_bytes())
    process_paths = set()
    for pid in pids:
        try:
            raw = reader(pid)
            if not re.search(rb"(?m)^# Task #\d+\b", raw.replace(b"\x00", b"\n")):
                continue
            path = _prompt_worktree(raw, roots)
        except OSError:
            continue
        if path is not None:
            process_paths.add(path)

    live = []
    worktree_only = []
    finished = []
    lock_live_pids: dict[str, object] = {}
    for worktree in sorted(registered, key=lambda path: path.name):
        lock = worktree / ".dreamwork" / "lane.lock"
        try:
            record = json.loads(lock.read_text(encoding="utf-8"))
        except FileNotFoundError:
            worktree_only.append(worktree.name)
            continue
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LivenessUnknown("cannot classify lane lock %s: %s" % (lock, exc)) from exc
        required = {"pid", "task", "lane", "identity"}
        if not isinstance(record, dict) or not required.issubset(record):
            raise LivenessUnknown("cannot classify lane lock %s: missing lane identity" % lock)
        if record["lane"] != worktree.name:
            raise LivenessUnknown(
                "lane lock %s names lane %r, expected %r"
                % (lock, record["lane"], worktree.name))
        identity = Path(str(record["identity"]))
        if identity.parent.resolve() != worktree:
            raise LivenessUnknown(
                "lane lock %s identity is outside its worktree: %s"
                % (lock, identity))
        if pid_matches_lane(record["pid"], str(identity)):
            live.append(worktree.name)
            lock_live_pids[worktree.name] = record["pid"]
        else:
            classify = work_classifier or classify_finished_work
            finished.append(FinishedLane(
                lane=record["lane"], task=record["task"], pid=record["pid"],
                identity=str(identity), work=classify(worktree)))

    # CWD-RUNNER SCAN — the dispatch-route-invariant channel (#1084). A lane
    # whose runner lives in its worktree but has no lane.lock (hand-dispatched,
    # every follow-up round) is invisible to the lock loop above. The cwd is
    # the measurement that was right in both fleet-undercount samples: it
    # cannot vary with dispatch route. A runner is distinguished from a
    # leftover (shell, editor, inotifywait) by its argv[0] basename, not by
    # cwd alone (#671/#729). Deleted cwds (" (deleted)" — a phantom whose
    # worktree was removed) are excluded. The set dedupes to one lane per
    # worktree, so a lane's many descendants count once.
    live_set = set(live)
    cwd_reader = read_cwd or read_proc_cwd
    skip = skip_pids if skip_pids is not None else _ancestor_pids()
    wt_by_path = {str(wt): wt.name for wt in worktrees}
    cwd_occupied: dict[str, int] = {}
    for pid in pids:
        if pid in skip:
            continue
        cwd = cwd_reader(pid)
        if cwd is None or cwd.endswith(" (deleted)"):
            continue
        lane_name = next(
            (name for wt_str, name in wt_by_path.items()
             if cwd == wt_str or cwd.startswith(wt_str + os.sep)),
            None)
        if lane_name is None:
            continue
        if _is_lane_runner(reader(pid)):
            # First runner pid wins; a lane's many descendants share the cwd
            # (#837) and need only one pid to measure CPU/elapsed.
            cwd_occupied.setdefault(lane_name, pid)
    cwd_live_names = tuple(sorted(
        name for name in cwd_occupied if name not in live_set))
    cwd_live_set = set(cwd_live_names)
    # A worktree the cwd channel found live is neither idle (worktree_only)
    # nor finished (the lock is stale, the lane was re-armed): it is live.
    worktree_only = tuple(n for n in worktree_only if n not in cwd_live_set)
    finished = tuple(f for f in finished if f.lane not in cwd_live_set)

    # LIVE-SIDE LIVENESS (#1155) — the dimension #1154 left open. "Is a
    # runner alive" is now answered; "is it able to do work" is not. A
    # permission-wedged lane holds a live pid and reads live, indistinguishable
    # from a computing one. classify_live_lane splits the live set (lock +
    # cwd) using CPU/elapsed (the discriminator the brief measured) and an
    # injectable wedge marker, so the fleet count no longer asserts a working
    # count it never measured. cpu/wedge probes default to the live ones and
    # may both be injected in tests; each lane gets the verdict its own pid's
    # signals produce, never a fleet-wide guess.
    live_names = sorted(live_set | cwd_live_set)
    pid_by_lane = dict(lock_live_pids)
    pid_by_lane.update(cwd_occupied)
    wt_by_name = {wt.name: wt for wt in worktrees}
    cpu_reader = read_cpu or read_proc_cpu
    if wedge_probe is not None:
        wedge = wedge_probe
    else:
        # The production default (#1155 round 2): a probe that combines the
        # cpu_reader's signals (old enough? computing?) with a worktree git
        # check (any commits or dirty files?) to find wedge evidence the tick
        # can actually reach — not an always-None stub. The closure captures
        # cpu_reader so the probe and the classifier share one measurement.
        def wedge(wt, p, *, cpu_s=None, elapsed_seconds=None):
            return _default_wedge_probe(
                wt, p, cpu_seconds=cpu_s, elapsed_seconds=elapsed_seconds)
    live_liveness = tuple(
        _classify_lane_pid(lane, pid_by_lane.get(lane), wt_by_name,
                           cpu_reader, wedge)
        for lane in live_names)

    return LaneInspection(
        live=tuple(live),
        worktree_only=tuple(worktree_only),
        process_only=tuple(sorted(path.name for path in process_paths - registered)),
        examined_processes=len(pids),
        finished=tuple(finished),
        cwd_live=cwd_live_names,
        live_liveness=live_liveness,
    )


def _classify_lane_pid(lane, pid, wt_by_name, cpu_reader, wedge):
    """Classify one live lane by its pid's CPU/elapsed and wedge marker.

    Centralises the "no pid → unknown" and probe-error handling so the
    classification loop stays a one-liner: a None pid (a lock-record pid that
    is not an int, or a pid that left the table) degrades to ``unknown``
    rather than raising, because liveness already named the lane live and the
    progress verdict must not un-name it (#136: a missing signal reads
    unknown, never as a confident state).

    The DEFAULT probe (when the caller passes none) is a closure over the
    cpu_reader: it needs CPU+elapsed to gate on age and computation before
    checking the worktree, and the cpu_reader is already the injectable seam
    the tick and tests share. An INJECTED probe keeps the ``f(worktree, pid)``
    signature — the closure is used only when no probe is supplied, so the
    production path (tick_line.py, no probe argument) gets the real one.
    """
    worktree = wt_by_name.get(lane)
    if pid is None or not isinstance(pid, int):
        return LiveLane(lane, LIVE_UNKNOWN, "no pid for live lane (lock "
                        "record unreadable or pid left the table)")
    try:
        cpu = cpu_reader(pid)
    except Exception:  # noqa: BLE001 — a probe error degrades to unknown
        cpu = None
    cpu_s = cpu[0] if cpu else None
    elapsed = cpu[1] if cpu else None
    marker = None
    if worktree is not None:
        try:
            try:
                marker = wedge(worktree, pid, cpu_s=cpu_s,
                               elapsed_seconds=elapsed)
            except TypeError:
                # Backward-compatible injected probe: f(worktree, pid) only.
                marker = wedge(worktree, pid)
        except Exception:  # noqa: BLE001 — a probe error degrades to unknown
            # #1155 P2b: a probe that raises (either the keyword form or the
            # backward-compat fallback) leaves the lane unclassified, not
            # propagating. The failure is a state (unknown via marker=None),
            # not an exception that crashes the tick.
            marker = None
    return classify_live_lane(lane, cpu_s, elapsed, marker)
