#!/usr/bin/env python3
"""Report live processes whose cwd is at or under a target directory.

The mechanical liveness check for worktree cleanup (#316). File state
cannot tell you a live process is still in a worktree — a tree whose
agent is mid-thought is byte-identical to one whose agent has gone — so
`git status`, `git status --ignored`, and every artifact classification
built on them cannot answer "is anyone still in there?". This does. It
reads `/proc/<pid>/cwd` for every pid and reports any process whose
working directory is the target or anything beneath it, by pid and full
command line, because "something is in there" without a name sends the
reader on a hunt.

It also reports the reverse case, which is how the #316 incident was
finally noticed: a cwd that reads "<path> (deleted)" is a process
stranded in a directory already removed. Same primitive, read the other
way.

This is why a visible command line is no liveness test either: a `ccc`
agent's process is a shell wrapper (`zsh -c ...`), so its argv never
contains the tool's name. A grep over process argv is authoritative-
looking and structurally incapable of being right. This reads the
kernel's own record of where each process actually is, which is the one
source that cannot lie about it.

/proc races are normal. A pid can vanish between listing `/proc` and
reading its cwd; such a pid is treated as "not found", never as an error.
A cwd that cannot be read (another user's process) is skipped the same
way. The report therefore covers same-uid processes, which is the case
that matters: the coordinator and the agents it dispatched share a uid.

This needs no judgement, which is the point: target-path-and-elapsed
heuristics ask a human to weigh "is 20 hours long?", and this does not.

Exit codes: 0 clear, 1 one-or-more processes found (live or stranded),
2 usage error. Designed for a human to read the report; the exit code is
a convenience gate, not a substitute for reading it.

The cleanup contract in `references/lifecycle.md` runs this BEFORE it
classifies a single artifact, because a live process makes the artifact
question moot. The force flag does not answer this question and must not
be read as answering it — declining to ask is precisely what it does.
"""
from __future__ import annotations

import os
import sys

_DELETED_SUFFIX = " (deleted)"


def _readlink_cwd(pid: int) -> str | None:
    """Raw readlink of ``/proc/<pid>/cwd``, or None if unreadable.

    None covers the /proc race (pid gone between listing and reading) and
    any unreadable cwd (another user's process, permission denied). Both
    are "not found": this reports what it can see of same-uid processes
    and does not error on the rest.
    """
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


_CMD_WIDTH = 140


def _one_line(cmd: str):
    """One scannable line, and whether anything was cut.

    A command line is not a short string here. The processes this tool exists
    to find are dispatched agents, and an agent's argv CONTAINS ITS WHOLE
    PROMPT — thousands of characters, with newlines. Printed raw, one process
    filled the terminal and the "one line per process, cwd beneath it" format
    stopped existing: the reader could not see the second process at all, let
    alone the verdict at the bottom. So the newline collapse is not cosmetic,
    it is what keeps the report a report.

    The pid is the actionable field and it is never abridged; the command line
    only has to be enough to recognise. The full text stays one command away
    and the caller is told so.
    """
    flat = " ".join(cmd.split())
    if len(flat) <= _CMD_WIDTH:
        return flat, False
    return f"{flat[:_CMD_WIDTH]}… (+{len(flat) - _CMD_WIDTH} chars)", True


def _read_cmdline(pid: int) -> str:
    """Full command line for a pid, falling back to ``comm`` if empty.

    Kernel threads and some early-init tasks carry an empty cmdline;
    ``comm`` (the truncated task name) is always present. The fallback is
    why a shell-wrapper agent still shows up as *something* even when its
    argv is unhelpful.
    """
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            raw = fh.read()
    except OSError:
        raw = b""
    parts = [p.decode("utf-8", "replace") for p in raw.split(b"\x00") if p]
    if parts:
        return " ".join(parts)
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8") as fh:
            return fh.read().strip() or f"<pid {pid}>"
    except OSError:
        return f"<pid {pid}>"


def classify(raw_cwd: str, target: str) -> str | None:
    """Relate a raw readlink result to a resolved target path.

    Returns one of:
      * ``"live"``     — cwd is target or beneath it, directory present;
      * ``"stranded"`` — cwd is target or beneath it, but the kernel has
                         marked it deleted (suffix ``" (deleted)"``);
      * ``None``       — cwd is unrelated to target.

    The deleted suffix is the signature of a process whose directory is
    already gone — the exact state the #316 incident ended in. The
    boundary check uses ``target + os.sep`` so a sibling whose name is a
    longer prefix (``/a/bb`` vs target ``/a/b``) does not match.
    """
    stranded = raw_cwd.endswith(_DELETED_SUFFIX)
    cwd = raw_cwd[: -len(_DELETED_SUFFIX)] if stranded else raw_cwd
    if cwd == target or cwd.startswith(target + os.sep):
        return "stranded" if stranded else "live"
    return None


def find_processes(target: str) -> list[dict]:
    """Processes whose cwd is at or under ``target`` (path resolved once).

    Each entry is ``{"pid", "cwd", "cmdline", "state"}`` where ``state`` is
    ``"live"`` or ``"stranded"``. Order is ascending pid for a stable
    report across runs. ``target`` is resolved with ``realpath`` exactly
    once so it is comparable to the kernel's resolved cwd.
    """
    resolved = os.path.realpath(target)
    found: list[dict] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        raw = _readlink_cwd(pid)
        if raw is None:
            continue
        state = classify(raw, resolved)
        if state is None:
            continue
        found.append({
            "pid": pid,
            "cwd": raw,
            "cmdline": _read_cmdline(pid),
            "state": state,
        })
    found.sort(key=lambda d: d["pid"])
    return found


def format_report(target: str, found: list[dict]) -> str:
    """Human-readable report. The caller decides what to do about it."""
    resolved = os.path.realpath(target)
    if not found:
        return (f"clear: no process has {resolved}\n"
                f"        (or anything under it) as cwd")
    live = [d for d in found if d["state"] == "live"]
    stranded = [d for d in found if d["state"] == "stranded"]
    lines = [f"{len(found)} process(es) in {resolved}:"]
    truncated = False
    for d in found:
        shown, cut = _one_line(d["cmdline"])
        truncated = truncated or cut
        lines.append(f"  pid {d['pid']:<7} [{d['state']}] {shown}")
        lines.append(f"             cwd: {d['cwd']}")
    if truncated:
        lines.append(
            "        (command lines abridged; full text: "
            "tr '\\0' ' ' < /proc/<pid>/cmdline)"
        )
    if live:
        lines.append(
            "do not remove: live process(es) above are still in this tree "
            "(file state cannot see them)"
        )
    if stranded:
        lines.append(
            "stranded process(es): their directory is already gone; "
            "they cannot be saved, only noted"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].strip():
        sys.stderr.write("usage: occupied.py <directory>\n")
        sys.stderr.write(
            "  reports live processes whose cwd is at or under <directory>.\n"
            "  exit 0 clear, 1 found (live or stranded), 2 usage error.\n"
        )
        return 2
    found = find_processes(argv[1])
    sys.stdout.write(format_report(argv[1], found) + "\n")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
