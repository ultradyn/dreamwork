#!/usr/bin/env python3
"""Merge one rebased lane, gate it, then retire it through ``dev/reap.py``.

Every gate runs on a DETACHED HEAD holding the merge; ``refs/heads/master`` is
fast-forwarded onto it only once all of them have passed (#882). On 2026-08-01
this tool printed ``REFUSE phase=named-tests`` directly above ``examined:
merge=69fc8e9b``: it had already merged, and master carried a red merge while
the log said refused. A gate whose verdict arrives after its action is not a
gate.

Detaching beats merge-then-revert-on-refusal, and the difference is what
happens when the *recovery* fails. Here ``refs/heads/master`` never points at
an ungated merge at all, so a failed restore leaves the ref correct and only
the working tree detached — loud, local, and invisible to a lane rebasing onto
master. Revert-on-refusal fails the other way: interrupt it and master keeps
the bad merge, which is the incident this replaces.

The gates need the merged tree and its history, not the branch's — ``lint.py``
reads ``git log`` — so they run where HEAD *is* the merge commit, and
``merge-identity`` proves that before any of them are believed.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Sequence


WARN_ROW = re.compile(r"^\s+WARN(?:\s|$)")
LINT_TRAILER = re.compile(r"^clean \((\d+) warning\(s\)\)$", re.MULTILINE)

# The gates this tool promises to run before the base branch is allowed to
# move. Declared apart from the code that runs them so that a gate deleted
# from the sequence is a REFUSAL rather than a shorter, quieter, green run:
# an empty phase list otherwise reports "all passed" and "none ran" alike.
GATES = ("named-tests", "guard-selection", "repo-wide-guards", "lint-comparison")


def _run(args: Sequence[str], repo: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=repo, env=env, capture_output=True, text=True
    )


def _relay(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], repo)


def _git_text(repo: Path, *args: str) -> str | None:
    result = _git(repo, *args)
    if result.returncode:
        _relay(result)
        return None
    return result.stdout.strip()


def _worktrees(repo: Path) -> dict[str, Path] | None:
    result = _git(repo, "worktree", "list", "--porcelain")
    if result.returncode:
        _relay(result)
        return None
    found: dict[str, Path] = {}
    path: Path | None = None
    branch: str | None = None
    for line in [*result.stdout.splitlines(), ""]:
        if not line:
            if path is not None and branch is not None:
                found[branch.removeprefix("refs/heads/")] = path
            path = branch = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            path = Path(value).resolve()
        elif key == "branch":
            branch = value
    return found


def _warn_rows(output: str) -> tuple[str, ...]:
    return tuple(sorted(set(line for line in output.splitlines() if WARN_ROW.match(line))))


def _print_rows(label: str, rows: Sequence[str]) -> None:
    print(f"lint WARN rows {label}: {len(rows)}")
    for row in rows:
        print(row)


def _base_state(repo: Path, base: str, base_sha: str | None) -> str:
    """Where the base branch actually is, right now, in one greppable line.

    Every refusal carries this because a `REFUSE` that names only what it
    declined to do reads as "nothing happened" — which is precisely how the
    #882 incident was mis-read.
    """
    now = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}") or "UNREADABLE"
    head = _git_text(repo, "rev-parse", "HEAD") or "UNREADABLE"
    if base_sha is None:
        return f"{base}={now}; no merge was attempted by this run; HEAD={head}"
    if now == base_sha:
        return f"{base}={now} unchanged by this run; HEAD={head}"
    if _git(repo, "merge-base", "--is-ancestor", base_sha, now).returncode == 0:
        return f"{base}={now} ADVANCED from {base_sha} by this run; HEAD={head}"
    return (
        f"{base}={now} MOVED OFF {base_sha} during this run; HEAD={head}; "
        f"any lane that rebased onto {base} in the interval must rebase again onto {now}"
    )


def _restore(repo: Path, base: str, base_sha: str) -> str | None:
    """Put the checkout back on ``base`` and PROVE it, or say how it did not.

    The checkout's exit status is not the evidence — it says only that git
    believed it worked. Reading the branch, HEAD and the tree back is. A
    restore that is performed but not verified is the same defect class as a
    merge that is performed but not gated.
    """
    checkout = _git(repo, "checkout", base)
    current = _git_text(repo, "branch", "--show-current")
    head = _git_text(repo, "rev-parse", "HEAD")
    dirty = _git(repo, "status", "--porcelain=v1", "--untracked-files=no")
    faults = []
    if checkout.returncode:
        faults.append(f"git checkout {base} exited {checkout.returncode}")
    if current != base:
        faults.append(f"checkout is on {current or 'a detached commit'}, not {base}")
    if head != base_sha:
        faults.append(f"HEAD is {head or 'UNREADABLE'}, not the pre-merge {base_sha}")
    if dirty.returncode or dirty.stdout:
        faults.append(f"{len(dirty.stdout.splitlines())} tracked path(s) still differ from {base}")
    return "; ".join(faults) or None


def _refuse(
    phase: str,
    reason: str,
    examined: str,
    retained: str,
    *,
    base_state: str,
    alert: str | None = None,
) -> int:
    print(f"REFUSE phase={phase}: {reason}", file=sys.stderr)
    if alert:
        print(f"RESTORE FAILED: {alert}", file=sys.stderr)
    print(f"examined: {examined}", file=sys.stderr)
    print(f"base: {base_state}", file=sys.stderr)
    print(f"retained: {retained}", file=sys.stderr)
    print("deliberately did not perform: dev/reap.py lane retirement", file=sys.stderr)
    return 1


def _lint(repo: Path) -> tuple[subprocess.CompletedProcess[str], tuple[str, ...] | None]:
    result = _run([sys.executable, "lint.py"], repo)
    _relay(result)
    combined = result.stdout + result.stderr
    trailer = LINT_TRAILER.search(combined)
    rows = _warn_rows(combined)
    if result.returncode or trailer is None or int(trailer.group(1)) != len(rows):
        return result, None
    return result, rows


def land(branch: str, tests: Sequence[str], *, base: str = "master") -> int:
    repo_text = _git_text(Path.cwd(), "rev-parse", "--show-toplevel")
    repo = Path(repo_text).resolve() if repo_text else Path.cwd().resolve()
    retained = f"branch={branch}; worktree=not-yet-resolved"

    if not tests:
        return _refuse(
            "selection",
            "named test selection is empty",
            f"branch argument={branch}; named tests=0",
            retained,
            base_state=_base_state(repo, base, None),
        )

    current = _git_text(repo, "branch", "--show-current")
    base_sha = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
    branch_sha = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{branch}")
    worktrees = _worktrees(repo)
    if current != base or not base_sha or not branch_sha or worktrees is None:
        return _refuse(
            "preflight",
            f"requires current branch {base} and resolvable local branch {branch}",
            f"current={current or 'UNKNOWN'}; base={base_sha or 'UNKNOWN'}; branch={branch_sha or 'UNKNOWN'}",
            retained,
            base_state=_base_state(repo, base, None),
        )
    lane = worktrees.get(branch)
    if lane is None:
        return _refuse(
            "preflight",
            "branch has no registered linked worktree",
            f"base={base_sha}; branch={branch_sha}; registered worktrees={len(worktrees)}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    retained = f"branch={branch}; worktree={lane}"

    ancestor = _git(repo, "merge-base", "--is-ancestor", base_sha, branch_sha)
    if ancestor.returncode:
        return _refuse(
            "preflight",
            f"branch is not rebased onto current {base}",
            f"base={base_sha}; branch={branch_sha}; worktree={lane}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )

    main_dirty = _git(repo, "status", "--porcelain=v1", "--untracked-files=no")
    lane_dirty = _git(lane, "status", "--porcelain=v1", "--untracked-files=no")
    if main_dirty.returncode or lane_dirty.returncode or main_dirty.stdout or lane_dirty.stdout:
        return _refuse(
            "preflight",
            "tracked worktree state is not clean",
            f"base={base_sha}; branch={branch_sha}; main-status={len(main_dirty.stdout.splitlines())}; lane-status={len(lane_dirty.stdout.splitlines())}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    lane_all = _git(lane, "status", "--porcelain=v1", "--ignored")
    if lane_all.returncode:
        return _refuse(
            "preflight",
            "could not record lane worktree state",
            f"base={base_sha}; branch={branch_sha}; status command exit={lane_all.returncode}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(
        f"pre-merge: base={base}@{base_sha} branch={branch}@{branch_sha} "
        f"worktree={lane} status-rows={len(lane_all.stdout.splitlines())} named-tests={len(tests)}"
    )
    for row in lane_all.stdout.splitlines():
        print(f"pre-merge lane-status: {row}")

    _, baseline = _lint(repo)
    if baseline is None:
        return _refuse(
            "lint-baseline",
            "WARN baseline was not captured (lint failed or emitted no clean trailer)",
            f"lint.py in {repo}; base={base_sha}; branch={branch_sha}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    _print_rows("baseline", baseline)

    detach = _git(repo, "checkout", "--detach", base_sha)
    if detach.returncode:
        _relay(detach)
        return _refuse(
            "detach",
            f"could not detach HEAD at {base} to build the merge off-branch (exit {detach.returncode})",
            f"base={base_sha}; branch={branch_sha}; worktree={lane}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(f"detached at {base_sha}: {base} does not move until every gate in {list(GATES)!r} passes")

    merged_sha = "not-created"

    def refuse_gated(phase: str, reason: str, examined: str) -> int:
        """Refuse a post-merge phase, restoring the checkout first."""
        faults = _restore(repo, base, base_sha)
        return _refuse(
            phase,
            reason,
            examined,
            retained,
            base_state=_base_state(repo, base, base_sha),
            alert=None
            if faults is None
            else (
                f"{faults}; the checkout may still hold the ungated merge {merged_sha} — "
                f"run `git checkout {base}` in {repo}"
            ),
        )

    merge = _git(repo, "merge", "--no-ff", branch, "-m", f"Merge {branch}")
    _relay(merge)
    if merge.returncode:
        _git(repo, "merge", "--abort")
        return refuse_gated(
            "merge",
            f"git merge --no-ff exited {merge.returncode}",
            f"base={base_sha}; branch={branch_sha}; worktree={lane}",
        )
    merged_sha = _git_text(repo, "rev-parse", "HEAD") or "UNKNOWN"

    # The gates below examine whatever HEAD is; prove it is the merge of the
    # two shas preflight read, so no gate can pass against the branch tree, a
    # stale merge, or a base that moved. The parents come from git, which the
    # tree under test cannot rewrite.
    parents = (_git_text(repo, "rev-list", "--parents", "-n", "1", "HEAD") or "").split()[1:]
    if parents != [base_sha, branch_sha]:
        return refuse_gated(
            "merge-identity",
            "HEAD is not the merge of the examined base and branch, so no gate below would judge it",
            f"merge={merged_sha}; parents={parents!r}; expected=[{base_sha!r}, {branch_sha!r}]",
        )
    print(f"merge-identity: {merged_sha} has parents {base}@{base_sha} and {branch}@{branch_sha}")

    passed: list[str] = []

    named = _run(["just", "pytest", *tests], repo)
    _relay(named)
    if named.returncode:
        return refuse_gated(
            "named-tests",
            f"named test selection failed with exit {named.returncode}",
            f"merge={merged_sha}; tests={list(tests)!r}",
        )
    passed.append("named-tests")

    guard_list = _run([sys.executable, "dev/repo_wide_guards.py", "list"], repo)
    _relay(guard_list)
    guards = guard_list.stdout.split()
    if guard_list.returncode or not guards:
        reason = (
            f"repo-wide guard list command exited {guard_list.returncode}"
            if guard_list.returncode
            else "repo-wide guard list is empty"
        )
        return refuse_gated(
            "guard-selection",
            reason,
            f"merge={merged_sha}; generator=dev/repo_wide_guards.py list; selected={len(guards)}",
        )
    passed.append("guard-selection")
    print(f"repo-wide guard selection: {len(guards)} test path(s): {' '.join(guards)}")
    guarded = _run(["just", "pytest", *guards], repo)
    _relay(guarded)
    if guarded.returncode:
        return refuse_gated(
            "repo-wide-guards",
            f"generated guard set failed with exit {guarded.returncode}",
            f"merge={merged_sha}; guards={guards!r}",
        )
    passed.append("repo-wide-guards")

    _, after = _lint(repo)
    if after is None:
        return refuse_gated(
            "lint-comparison",
            "post-merge WARN rows were unavailable (lint failed or emitted no clean trailer)",
            f"merge={merged_sha}; baseline rows={len(baseline)}",
        )
    _print_rows("post-merge", after)
    added = tuple(sorted(set(after) - set(baseline)))
    removed = tuple(sorted(set(baseline) - set(after)))
    print(f"lint WARN row-set comparison: added={len(added)} removed={len(removed)}")
    for row in added:
        print(f"+ {row}")
    for row in removed:
        print(f"- {row}")
    if added or removed:
        return refuse_gated(
            "lint-comparison",
            "WARN row set changed from the pre-merge baseline",
            f"merge={merged_sha}; baseline={len(baseline)} rows; post-merge={len(after)} rows",
        )
    passed.append("lint-comparison")

    missing = tuple(gate for gate in GATES if gate not in passed)
    if not GATES or not passed or missing:
        return refuse_gated(
            "gate-coverage",
            f"only {len(passed)} of {len(GATES)} declared gates ran, so a pass here would be vacuous",
            f"merge={merged_sha}; ran={passed!r}; declared={list(GATES)!r}; missing={list(missing)!r}",
        )
    print(f"gate-coverage: {len(passed)} of {len(GATES)} declared gates passed: {' '.join(passed)}")

    back = _restore(repo, base, base_sha)
    if back is not None:
        return _refuse(
            "advance",
            f"could not return to {base} to fast-forward it onto the gated merge",
            f"merge={merged_sha}; faults={back}",
            retained,
            base_state=_base_state(repo, base, base_sha),
            alert=f"{back}; the checkout may still hold the gated merge {merged_sha}",
        )
    forward = _git(repo, "merge", "--ff-only", merged_sha)
    landed = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
    if forward.returncode or landed != merged_sha:
        _relay(forward)
        return _refuse(
            "advance",
            f"fast-forward of {base} onto the gated merge did not land",
            f"merge={merged_sha}; ff-exit={forward.returncode}; {base}={landed or 'UNREADABLE'}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(f"advance: {base} {base_sha} -> {merged_sha} after {len(passed)} gate(s)")

    reap = _run(
        [sys.executable, str(Path(__file__).with_name("reap.py")), str(lane), "--base", base],
        repo,
        env=os.environ.copy(),
    )
    _relay(reap)
    if reap.returncode:
        return _refuse(
            "retirement",
            f"dev/reap.py refused with exit {reap.returncode}",
            f"merge={merged_sha}; branch={branch_sha}; worktree={lane}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(f"landed: merge={merged_sha}; branch retained={branch}; worktree retired by dev/reap.py")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge a rebased lane, run named and repo-wide gates, then reap its worktree."
    )
    parser.add_argument("branch", help="explicit local lane branch")
    parser.add_argument("tests", nargs="*", help="explicit named pytest paths/node ids")
    parser.add_argument("--base", default="master", help="checked-out base branch (default: master)")
    args = parser.parse_args(argv)
    return land(args.branch, args.tests, base=args.base)


if __name__ == "__main__":
    raise SystemExit(main())
