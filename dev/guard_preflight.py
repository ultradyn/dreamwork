#!/usr/bin/env python3
"""Guard-suite preflight: is this the wrong-answer regime? (#606)

What this is
------------
`just guards` runs this BEFORE binding a port or spawning a server. It reads
the one-min load average, the core count, and the live ccc lane count, and
classifies the machine into one of three bands. On the RISK band it refuses
unless ``DREAMWORK_GUARDS_FORCE=1`` is set, and when forced the recipe
re-prints its line onto the run's summary so the verdict TRAVELS WITH the
result — an annotated result beats a refused one when the coordinator
genuinely needs an answer now (the brief's "must not break" constraint).

Why this is soundness, not scheduling (#666)
-------------------------------------------
pytest under load is SLOW BUT HONEST; a browser guard under load returns a
WRONG ANSWER — it dies before its first assertion and the #471 did-not-judge
sentinel reads like a failure while gating nothing. That asymmetry is why a
load-induced FAIL waved through as flaky is how a real regression eventually
gets waved through too. So the band this instrument refuses on is the one
that produces wrong answers, not the one that produces slowness.

Why the lane count, not just load (#606)
---------------------------------------
Load on this box sits near 30 on 16 cores whether or not a lane is out
(justfile:337), so a bare load threshold fires constantly and trains override
(#136: a signal that always fires is one nobody reads). The lane count is the
lever the coordinator actually controls — "wait for the fleet to drain" is
actionable in a way "wait for load to drop" is not, because load includes the
desktop, a rebuild, everything on the box. So load CONFIRMS the regime (it is
what actually breaks the guard); the lane count names the CAUSE the coordinator
can act on. The two compose.

Thresholds are derived from MEASURED data, not guessed
------------------------------------------------------
The boilerplate records: single guards judged correctly at load 22.79; the
``health`` guard (four servers at once) ran clean end-to-end at 23.72; the
failures were at load 38-42. So load in the low-to-mid 20s is fine, and the
wrong-answer regime begins in the low 30s. The constants below carry those
numbers and the margin, so a future reader knows exactly where they came from
and a recalibration re-derives rather than guesses.

What it cannot see (#675)
-------------------------
``discover_lanes`` sees only the ccc dispatch path; Agent-tool subagents are
structurally invisible to it. That blindness is #675's to fix (status_sync is
off-limits here). The instrument says so in its output rather than rendering
an unqualified count — the same standard the tick line holds (#673). For THIS
task the ccc count is the right signal, because ccc lanes are the fleet the
coordinator dispatches and the fleet whose memory cost the #666 third note
measured.

Restoration discipline for the red-proof is in test_guard_preflight.py: the
load/cores/lane readers are injectable, so the contract tests run against
synthetic readings and never touch the real machine.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ── thresholds (measured, not guessed — see module docstring) ──────────

# Below this a run is fine. Measured clean: single guards at 22.79, the
# four-server `health` guard at 23.72. 25 keeps a 2-point margin above the
# highest confirmed-clean run and matches the boilerplate's "low-to-mid 20s
# is fine; do not refuse on that".
LOAD_OK = 25.0

# At or above this a multi-server browser guard returns a WRONG ANSWER, not a
# slow one (#666). Measured failures at 38-42; the #666 third note measured
# load 32.17 with six lanes as the structural-break point. 32 is the lower
# bound of the observed failure regime.
LOAD_RISK = 32.0


# ── readers (real /proc + status_sync; injectable for tests) ───────────


def read_loadavg() -> float | None:
    """One-minute load average, or None if /proc/loadavg is unreadable.

    None — not 0.0 — is the #671/#136 distinction: a missing reading must
    never render as a calm zero.
    """
    try:
        text = Path("/proc/loadavg").read_text()
    except OSError:
        return None
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def read_cores() -> int | None:
    """Core count via nproc, or None if it cannot be read."""
    try:
        return os.cpu_count()
    except RuntimeError:
        return None


def count_lanes(target: Path | None = None) -> int | None:
    """Live ccc lane count via ``status_sync.live_lane_count``, or None on failure.

    None — not 0 — when ``/proc`` is unreadable, so an instrument failure
    never renders as "no lanes". A CONTRACT BREAK (the accessor's shape
    changing underneath the caller) is NOT caught here: it propagates as a
    ``TypeError``/``ValueError``, distinct from the ``OSError`` that means
    "/proc unreadable on this host" (#136). Those are different facts — the
    first is a bug that must be loud, the second a legitimate unknown.
    #728: a bare ``except Exception`` here turned #675's arity change into
    a silent ``?`` beside a confident verdict, which is how it hid.
    ``target`` is the project root whose sibling and legacy ``.worktrees/``
    roots hold lanes;
    resolved from cwd when omitted. #675: this sees only the ccc dispatch
    path, never Agent-tool subagents.
    """
    try:
        # status_sync is a repo-root module; a direct script run puts dev/
        # (not the repo root) on sys.path, so add the script's grandparent.
        import sys as _sys
        _root = str(Path(__file__).resolve().parent.parent)
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        import status_sync  # read-only call, no edit (#675)
    except ImportError:
        return None
    t = target if target is not None else _main_checkout()
    if t is None:
        return None
    try:
        return status_sync.live_lane_count(t)  # #728: accessor, not an unpack
    except OSError:
        # /proc unreadable on this host — a legitimate unknown (#136).
        return None
    # NOTE: TypeError/ValueError (a contract mismatch in the accessor) is
    # deliberately NOT caught — see docstring. main() renders it as
    # COUNT-BROKEN so the break is loud rather than a silent '?'.


def _main_checkout() -> Path | None:
    """Resolve the main checkout from a worktree cwd, or None.

    Git's common dir names the main checkout independent of whether the linked
    tree is under the legacy in-repo or new sibling ``.worktrees`` root.
    """
    cwd = Path.cwd()
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=cwd,
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if cp.returncode != 0:
        return cwd
    common = Path(cp.stdout.strip())
    if not common.is_absolute():
        common = (cwd / common).resolve()
    return common.parent if common.name == ".git" else None


# ── classify + render ──────────────────────────────────────────────────

# Verdict constants — the justfile branches on the leading token, so the
# spelling is load-bearing and pinned by the tests.
OK = "OK"
CAUTION = "CAUTION"
RISK = "WRONG-ANSWER-RISK"


def classify(load: float | None, cores: int | None, lanes: int | None) -> str:
    """Map a reading to a band. None readings are treated conservatively:
    a missing load cannot confirm the regime, so a missing load with lanes
    out is CAUTION (the cause is present, the confirmation absent), while a
    missing load with no lanes is OK (nothing the coordinator can act on).

    The band is load-driven because load is what actually breaks the guard;
    the lane count names the actionable cause but does not by itself produce
    wrong answers (one idle lane at load 5 is fine).
    """
    if load is None:
        # Cannot confirm the regime. Lanes out => the cause is present.
        return CAUTION if (lanes or 0) > 0 else OK
    if load < LOAD_OK:
        return OK
    if load < LOAD_RISK:
        return CAUTION
    return RISK


def render(verdict: str, load: float | None, cores: int | None,
           lanes: int | None) -> str:
    """The one-line preflight. None readings name themselves, never zero.

    The line is consumed by humans AND grepped by the justfile, so the
    verdict token leads and the bracketed facts follow in a stable order."""
    load_s = f"{load:.2f}" if load is not None else "?"
    cores_s = str(cores) if cores is not None else "?"
    if lanes is None:
        # #728: '?' alone reads as one unknown field beside a confident
        # verdict; name the count unavailable so a reader knows the verdict
        # rests on load alone (the count half of #606's two legs is gone).
        lanes_s = "? (ccc-only; #675; count unavailable)"
    else:
        lanes_s = str(lanes)
    ratio = ""
    if load is not None and cores:
        ratio = f" ({load / cores:.1f}x cores)"
    facts = f"[load {load_s}{ratio} on {cores_s} cores, {lanes_s} ccc lane(s)]"
    note = _recommendation(verdict, load, lanes)
    return f"guard preflight: {verdict} {facts} — {note}"


def _recommendation(verdict: str, load: float | None,
                    lanes: int | None) -> str:
    """An actionable clause for each band (#136: a refusal that says nothing
    trains override). Names the thing the coordinator can DO."""
    if lanes is None:
        # #728: do NOT classify on the missing count as "no fleet" — that
        # is the paper-over this fix removes. The count half of #606's
        # two-legged instrument is gone; say the verdict rests on load
        # alone and the actionable lever (the fleet) is unreadable.
        if verdict == OK:
            return ("load is fine but the lane count is unavailable, so the "
                    "verdict rests on load alone (the count half is gone)")
        if verdict == CAUTION:
            return ("load in the measured grey zone; lane count unavailable, "
                    "so whether a fleet is out is UNKNOWN — verdict on load "
                    "alone, treat the fleet lever as unreadable")
        return ("WRONG-ANSWER regime on load alone; lane count unavailable, "
                "so an undiscovered fleet may be making it worse — run a "
                "subset (DREAMWORK_GUARDS=<name>) or force with "
                "DREAMWORK_GUARDS_FORCE=1")
    if verdict == OK:
        return "guards should judge honestly"
    if verdict == CAUTION:
        if (lanes or 0) > 0:
            return ("load in the measured grey zone with a fleet out; "
                    "single guards likely honest, multi-server guards "
                    "(health/dashboard) may flake — wait for the fleet or "
                    "run a subset")
        return ("load in the measured grey zone with no ccc fleet; "
                "single guards likely honest, multi-server guards may flake")
    # RISK
    if (lanes or 0) > 0:
        return ("WRONG-ANSWER regime: a browser guard can die before judging "
                "(#666/#471). Wait for the fleet to drain, run a subset "
                "(DREAMWORK_GUARDS=<name>), or force with "
                "DREAMWORK_GUARDS_FORCE=1 — the verdict will carry this fact")
    return ("WRONG-ANSWER regime: a browser guard can die before judging "
            "(#666/#471). Run a subset (DREAMWORK_GUARDS=<name>) or force "
            "with DREAMWORK_GUARDS_FORCE=1 — the verdict will carry this fact")


def main(argv: list[str] | None = None) -> int:
    """Print the preflight line. Exit 0 always — it is an instrument, and the
    justfile decides whether to refuse on RISK. (A Python exit code is the
    wrong layer for the refusal: the recipe needs to print the actionable
    banner AND honor the force flag, which is shell's job.)"""
    load = read_loadavg()
    cores = read_cores()
    try:
        lanes = count_lanes()
    except (TypeError, ValueError) as e:
        # #728/#136: a contract break in the lane-count accessor is a BUG,
        # not a legitimate unknown — it must be loud and distinct from the
        # '?' of an unreadable /proc. Name the error and mark the verdict
        # as resting on load alone rather than printing '?' beside a
        # confident one (#671).
        print(render_count_broken(e, load, cores))
        return 0
    verdict = classify(load, cores, lanes)
    print(render(verdict, load, cores, lanes))
    return 0


def render_count_broken(err: Exception, load: float | None,
                        cores: int | None) -> str:
    """The preflight line for a lane-count accessor contract break (#728).

    Distinct from render()'s '?': that means '/proc unreadable on this
    host' (a legitimate unknown); this means 'the function I call changed
    shape underneath me' (#136) — a bug, so the error type is named and the
    load verdict is marked as standing on one leg (#606). The line still
    leads with the load verdict token so the justfile's RISK grep holds."""
    load_s = f"{load:.2f}" if load is not None else "?"
    cores_s = str(cores) if cores is not None else "?"
    verdict = classify(load, cores, None)
    return (f"guard preflight: COUNT-BROKEN {verdict} [load {load_s} on "
            f"{cores_s} cores, lane count UNAVAILABLE: "
            f"{type(err).__name__}: {err}] — the lane-count accessor's "
            f"contract broke (#728); verdict rests on LOAD ALONE, the "
            f"count half is gone (#606)")


if __name__ == "__main__":
    sys.exit(main())
