#!/usr/bin/env python3
"""Concurrent-test advisory: how busy is THIS box before I add my own suite? (#666)

What this is
------------
`just pytest` / `just test` prints this advisory before running the suite. It
reports how many OTHER pytest processes are already live on the machine, plus
how many browser/guard (Chromium) processes, plus a memory-pressure token when
available memory is low. Advisory only — it gates nothing, queues nothing, and
requires no cooperation from any other lane. That is what makes it landable
today; it was the affected lane's own suggestion (#666 option (a)).

Why the cause was mis-attributed twice, and why this carries that forward
------------------------------------------------------------------------
The task's own third note decomposed the load figure the first two notes quoted
as CPU contention and found the machine ~70% CPU-idle; what was actually scarce
was MEMORY (swap 52G/60G, kswapd0 at 13.4%), and Linux load average counts
uninterruptible-sleep (D-state, blocked on swap-in) processes. So a browser
guard does not fail under load because CPU is starved — it fails because a guard
with a FIXED TIMEOUT waits on a page whose process is blocked on swap-in. That
is why the harm is a WRONG ANSWER rather than a slow one, and why pytest under
the same conditions stays HONEST: pytest has no timeout racing a human-scale
interaction. One Chromium costs more than several pytest lanes together, so the
axis this advisory exposes is "how many browser-binding lanes are out", not just
"how many suites". The memory token is the part a pytest count cannot see but
the third note measured.

Three traps, each of which makes the number worse than useless if missed
-----------------------------------------------------------------------
1. DO NOT COUNT YOURSELF. The advisory runs from inside the process tree that is
   about to run pytest, and a naive `pgrep -f pytest` matches ANY process whose
   joined argv contains the substring "pytest" — including the very shell that is
   running this helper (measured at write time: `pgrep -fc pytest` returned 1
   with zero real suites live, because the shell's own command text contained the
   word). The fix is two-layer: classify by parsed argv TOKENS (argv[0] basename
   == 'pytest', or a `python* -m pytest` form) rather than a substring of the
   joined cmdline, AND exclude this process plus all its ancestors. A shell
   running a script that merely mentions pytest has argv[0]==zsh and matches
   neither rule; the ancestor exclusion is belt-and-braces for the case where the
   helper itself is nested inside a pytest process.
2. SAY WHAT YOU COUNTED (#671, #136). "0 other suites" and "I could not enumerate
   processes" must not render identically: the first is a calm all-clear, the
   second is a broken instrument reporting nothing. /proc unreadable, absent, or
   denied are all real, and each renders as a fault-looking line that names the
   reason, never as zero. A count that examined nothing must not read as zero.
3. A COUNT IS A QUESTION, NOT A VERDICT (#590). The advisory describes the
   machine; it must never read as "it is safe to proceed". Every rendered line
   ends with "(advisory)" so a non-zero number is a prompt to think, not a gate.

Restoration discipline for the red-proof is in test_concurrent_tests.py: the
/proc reader is injectable, so the contract tests run against a synthetic
process list and never touch the real one.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── classification ─────────────────────────────────────────────────────

# Browser/guard process argv[0] basenames. Playwright headless launches a chrome
# binary (often `headless_shell` or `chrome`); these are the dominant resident-
# memory consumer the third note names. Advisory heuristic, not an inventory.
_BROWSER_BASES = ("chrome", "chromium", "headless_shell")


def classify(argv: list[str]) -> str | None:
    """Classify one process by its parsed argv. Returns 'pytest', 'browser', or None.

    Token-based on purpose (see trap 1 in the module docstring): a substring
    match on the joined cmdline counts the shell running this helper, because
    that shell's command text contains the literal word "pytest". argv[0]'s
    basename does not.
    """
    if not argv:
        return None
    base = Path(argv[0]).name
    if base == "pytest":
        return "pytest"
    if base.startswith("python") and "-m" in argv:
        i = argv.index("-m")
        if i + 1 < len(argv) and Path(argv[i + 1]).name == "pytest":
            return "pytest"
    if any(tok in base for tok in _BROWSER_BASES):
        return "browser"
    return None


# ── process enumeration (real /proc; injectable for tests) ──────────────


def read_procs() -> list[tuple[int, list[str]]] | None:
    """Read every readable /proc/<pid>. None means "could not enumerate".

    None — not [] — is the #671/#136 distinction: an empty list is a genuine
    "machine looked empty", while None is "the instrument could not look". Each
    unreadable entry is skipped rather than fatal, so a single pid owned by
    another user (common on a shared box) does not turn the whole advisory red.
    """
    proc = Path("/proc")
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None
    out: list[tuple[int, list[str]]] = []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        cmd = entry / "cmdline"
        try:
            raw = cmd.read_bytes()
        except OSError:
            continue  # raced or permission-denied — skip, do not abort
        if not raw:
            continue  # kernel thread / zombie: no argv
        argv = [tok.decode("utf-8", "replace") for tok in raw.split(b"\0") if tok]
        if argv:
            out.append((int(entry.name), argv))
    return out


def ancestors() -> set[int]:
    """This process's pid plus every ancestor up to init (the 'do not count' set).

    The advisory must not count the tree that is about to run pytest as already
    running pytest. Walks PPid from /proc/self/status; on any read failure falls
    back to just {self}, which is the minimum correct exclusion.
    """
    seen: set[int] = set()
    pid = os.getpid()
    seen.add(pid)
    cur = pid
    for _ in range(64):  # bounded; real chains are shallow
        try:
            status = Path(f"/proc/{cur}/status").read_text()
        except OSError:
            break
        ppid: int | None = None
        for line in status.splitlines():
            if line.startswith("PPid:"):
                try:
                    ppid = int(line.split()[1])
                except (ValueError, IndexError):
                    break
                break
        if ppid is None or ppid <= 1 or ppid in seen:
            break
        seen.add(ppid)
        cur = ppid
    return seen


# ── memory pressure (the third note's actual scarce resource) ──────────


def read_meminfo() -> dict[str, int] | None:
    """Swap/Mem figures from /proc/meminfo in kB, or None if unreadable."""
    try:
        text = Path("/proc/meminfo").read_text()
    except OSError:
        return None
    want = ("SwapTotal", "SwapFree", "MemAvailable", "MemTotal")
    out: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].rstrip(":") in want:
            try:
                out[parts[0].rstrip(":")] = int(parts[1])
            except ValueError:
                pass
    return out or None


def _gib(kib: int) -> str:
    return f"{kib / (1024 * 1024):.0f}G"


# Available memory below which a browser-binding lane is at real risk of a
# fixed-timeout guard stalling on swap-in (the wrong-answer failure the third
# note measured). The trigger keys on THIS — what a new process can actually get
# — never on swap-used, which on a long-lived desktop is high whenever uptime is
# high and so fired "memory-bound" on a healthy 28G-available machine (#785).
# Absolute, not relative: headroom for a process is an absolute quantity. The
# healthy states measured on this box (27-30 GiB available) sit ~3-4x above it,
# so the token does not fire on the input that produced #785.
_LOW_AVAIL_KIB = 8 * 1024 * 1024  # 8 GiB


# ── scan + render ───────────────────────────────────────────────────────


def scan(
    procs: list[tuple[int, list[str]]] | None,
    *,
    exclude: set[int],
) -> dict:
    """Tally pytest and browser counts from a process list.

    `procs` is what read_procs() (or a test) supplies: None means "could not
    enumerate" and is carried through so render() can make it look like a fault.
    """
    if procs is None:
        return {"pytest": None, "browser": None, "enumerated": False}
    pytest_n = browser_n = 0
    for pid, argv in procs:
        if pid in exclude:
            continue
        kind = classify(argv)
        if kind == "pytest":
            pytest_n += 1
        elif kind == "browser":
            browser_n += 1
    return {"pytest": pytest_n, "browser": browser_n, "enumerated": True}


def render(result: dict, mem: dict[str, int] | None) -> str:
    """The one-line advisory. Enum-failure never renders as zero (#671/#136);
    the line never reads as a verdict (#590).

    Built as a list of '; '-joined clauses so the punctuation stays uniform —
    an earlier string-append form left a stray space before each semicolon."""
    if not result["enumerated"]:
        clauses = ["concurrent tests: process list unreadable (could not count — not zero)"]
    else:
        n = result["pytest"]
        b = result["browser"]
        p_clause = (f"{n} other pytest suite{'s' if n != 1 else ''}" if n
                    else "no other pytest suites")
        b_clause = f"{b} browser/guard process{'es' if b != 1 else ''}"
        clauses = [f"concurrent tests: {p_clause}", b_clause]
    # Memory token: surfaces low AVAILABLE memory — what a new process can
    # actually get (#785). NOT swap-used: that reads high on any long-lived
    # desktop (idle desktop pages correctly evicted by uptime, not pressure), so
    # keying on it printed "memory-bound" beside 28G available and sent the
    # reader chasing a leak that was not there. The wording reports the reading
    # ("low available memory"); it does not diagnose a cause it did not prove.
    # Absent on a calm machine (#612). A missing or impossible MemAvailable
    # reports that pressure was not measured; neither state fabricates a
    # verdict, and neither is allowed to look like the healthy silent path.
    if mem and mem.get("MemTotal", 0) > 0:
        total = mem["MemTotal"]
        avail = mem.get("MemAvailable")
        if avail is None:
            clauses.append("mem: MemAvailable absent (memory pressure not measured)")
        elif avail < 0 or avail > total:
            clauses.append(
                f"mem: impossible MemAvailable {_gib(avail)} of {_gib(total)} MemTotal "
                "(memory pressure not measured)"
            )
        elif avail < _LOW_AVAIL_KIB:
            clauses.append(
                f"mem: {_gib(avail)} available of {_gib(total)} "
                "(low available memory — a browser lane costs RAM a pytest lane does not)"
            )
    return "; ".join(clauses) + " (advisory)"


def main(argv: list[str] | None = None) -> int:
    """Print the advisory. Exit 0 always — it gates nothing."""
    procs = read_procs()
    result = scan(procs, exclude=ancestors())
    print(render(result, read_meminfo()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
