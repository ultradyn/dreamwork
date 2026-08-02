#!/usr/bin/env python3
"""Lane-containment pre-commit guard (#465).

A lane dispatched into a worktree (normally ``../.worktrees/<name>``) can
edit the **main checkout** instead of its worktree, and nothing notices until a
merge fails — or worse, a coordinator commit sweeps the lane's half-finished
edits into a ledger commit under the wrong message (``12f47e3`` in this repo's
history). The invariant the whole fan-out rests on — *parallel increments only
ever touch disjoint files* — is void the moment a lane writes outside its
worktree, and a brief cannot enforce it (the incident's brief named the worktree
twice and was ignored). Only a check can.

This is the **early-failing half** of the layered answer (see
``.dreamwork/docs/plans/lane-containment.md`` for the full IGC). It refuses a
commit landing in the **main checkout** when a dispatched lane is out and the
staged paths intersect that lane's declared ownership. It catches the defect at
the commit boundary — where it becomes dangerous — and needs no cooperation from
the lane: it reads ownership from the lane's own brief, and lane presence from
the registered worktrees.

WHY A COMMIT-TIME GUARD, NOT A FIRST-WRITE GUARD
-----------------------------------------------
The realised harm was a merge failing on dirty files; the unrealised worse harm
was a coordinator commit sweeping lane edits. Both are commit-shaped. A
first-write guard with no lane cooperation is not achievable on this harness
(the only candidate needs the lane to read and echo a marker, and "a rule a
brief states is what already failed"). The commit boundary is the honest place
this defect becomes dangerous, and the successor — a pre-merge assertion — is
the cannot-be-bypassed backstop for edits that land between commits.

WHY OWNERSHIP FROM THE BRIEF, NOT status.json
---------------------------------------------
``status.json``'s ``dreamers`` entry is ``{"task", "pid", "brief"}`` — it
carries the task id and the dispatch pid, but **no file ownership and no
worktree path**. A guard that read an ownership list out of ``status.json``
would read nothing. The brief is the one document the lane was actually handed,
it is committed under ``.dreamwork/docs/briefs/``, and every brief already
carries a prose "Yours: …" list. Declaring ownership as a machine-parseable
``Lane-owns:`` line (see ``file-formats.md``) makes the brief the single source
of what the lane was told it owns — no second store, no drift.

WHAT IT DOES
------------
1. Detects it is in the **main checkout**: ``git rev-parse --git-dir`` resolves
   to the common dir (the path contains no ``/worktrees/`` segment). In a linked
   worktree it exits 0 immediately — lanes commit freely from their own trees.
2. Enumerates dispatched lanes from ``git worktree list --porcelain`` using the
   canonical worktree roots shared with the launcher, not a branch-name prefix.
3. Reads each lane's owned paths from the ``Lane-owns:`` lines in its brief.
4. Intersects the staged paths with each live lane's owned set. On any overlap
   it refuses (exit 1), naming the lane, the contested paths, and the remedy.
5. No-ops cleanly when no lane is out, when nothing is staged, or when no lane
   declares ownership — the ordinary solo case costs a few git calls.

REPO-LOCAL, EXPLICITLY ENABLED
------------------------------
The tracked ``.githooks/`` forwards ``pre-commit``, ``commit-msg`` and
``pre-push`` to their global counterparts before adding this guard to
``pre-commit``. Enable it with ``just enable-lane-guard``; disable it with
``just disable-lane-guard``. Those recipes change the shared repository's
local ``core.hooksPath`` and are intentionally never run automatically.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Emergency escape hatch, documented in the refusal message. A lane's stray
# edit should be committed from the worktree, not force-landed on master; but a
# hook that cannot be bypassed in a genuine emergency is a hook that gets
# disabled, and a disabled hook protects nothing.
BYPASS_ENV = "DREAMWORK_LANE_GUARD_BYPASS"

# The git-dir of a linked worktree contains this segment; the main checkout's
# git-dir (the common dir) does not.
WORKTREE_GITDIR_SEGMENT = "/worktrees/"


class GuardError(Exception):
    """Raised when a precondition the guard depends on is unmet.

    A guard that cannot evaluate its inputs must fail loud rather than fail
    open: a merge blocked by an error message is recoverable; a merge that
    proceeds because the guard silently declined is the silent-wrong-state this
    repo documents. Callers print the message and exit 1.
    """


def _run_git(args: list[str], cwd: Path) -> str:
    """Run git, returning stdout. Raises GuardError on non-zero / missing git."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:  # git itself missing
        raise GuardError(f"git not found on PATH ({exc})") from exc
    if result.returncode != 0:
        raise GuardError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip() or '(no stderr)'}"
        )
    return result.stdout


def is_main_checkout(repo_root: Path) -> bool:
    """True when this commit is landing in the main checkout, not a worktree.

    The main checkout's git-dir is the common dir (``.git``); a linked
    worktree's is ``.git/worktrees/<name>``. The segment discriminator is robust
    to absolute vs relative git-dir resolution.
    """
    try:
        git_dir = _run_git(["rev-parse", "--git-dir"], repo_root).strip()
    except GuardError:
        # If we cannot tell, we are not the main checkout for the purpose of
        # this guard — decline to act rather than risk a false refusal in a tree
        # we do not understand.
        return False
    return WORKTREE_GITDIR_SEGMENT not in git_dir


def repo_root(cwd: Path) -> Path:
    """The work-tree root for cwd, as an absolute path."""
    root = _run_git(["rev-parse", "--show-toplevel"], cwd).strip()
    return Path(root)


def _parse_worktree_list(repo_root: Path) -> list[tuple[Path, str]]:
    """Return ``[(worktree_path, branch)]`` for registered lane worktrees.

    Reuses lint's production classifier so the hook and ambient backstop cannot
    drift. ``git worktree list --porcelain`` is the registry; the canonical
    sibling/legacy roots define lane membership and branch names may change.
    """
    lint = _import_lint()
    try:
        lanes = lint._live_lane_worktrees(repo_root)
    except lint.LaneEnumerationError as exc:
        raise GuardError(
            f"could not classify registered worktrees: {exc}; "
            f"worktrees examined={exc.examined}; lanes classified={exc.classified}"
        ) from exc
    return lint.LaneWorktrees(
        [(Path(path), branch) for path, branch in lanes], examined=lanes.examined)


def _main_checkout_root(repo_root: Path) -> Path:
    """The main checkout's root, given any tree sharing its git common dir.

    ``git rev-parse --git-common-dir`` resolves to ``.git`` for both the main
    checkout and linked worktrees (the common dir is shared). Its parent is the
    main checkout's root. This lets a lane worktree's owned paths be read from
    the main checkout's briefs dir, where the coordinator writes them.
    """
    common = _run_git(["rev-parse", "--git-common-dir"], repo_root).strip()
    common_path = (repo_root / common).resolve() if not Path(common).is_absolute() else Path(common)
    # common is <main_root>/.git → main root is its parent.
    return common_path.parent


def _briefs_for_lane(main_root: Path, lane_name: str) -> list[Path]:
    """The brief this lane was dispatched with, if one is recorded.

    A lane's brief lives in the **main checkout's** ``.dreamwork/docs/briefs/``
    (the coordinator writes it there; the worktree, branched before the brief
    was written, does not carry it). The lane is matched by its worktree name
    suffix (the segment after ``wt/``), which appears in the brief as
    ``.worktrees/<suffix>`` (matching either root) or ``wt/<suffix>``. A
    ``.lane-brief`` marker in the
    worktree (holding the brief's absolute path) is the fast path if a dispatch
    writes one; the scan is the resilient path. Both read the brief the lane was
    actually given, never ``status.json`` (which carries no worktree path).
    """
    # Fast path: an explicit marker the dispatch may write into the worktree.
    # Not relied upon (no dispatch writes it today), but cheap to honour.
    suffix = lane_name
    main_briefs = main_root / ".dreamwork" / "docs" / "briefs"
    found: list[Path] = []
    if not main_briefs.is_dir():
        return found
    for b in sorted(main_briefs.glob("*.md")):
        try:
            text = b.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if f"wt/{suffix}" in text or f".worktrees/{suffix}" in text:
            found.append(b)
    return found


def _owned_paths_for_lane(main_root: Path, lane_name: str) -> set[str]:
    """Paths a lane was told it owns, from its brief's ``Lane-owns:`` lines.

    Returns repo-relative POSIX paths. Empty set if the brief declares nothing
    (the guard then no-ops for that lane, and ``lint.check_brief_lane_owns``
    elsewhere errors so an empty set is never silently load-bearing).
    """
    owned: set[str] = set()
    for brief in _briefs_for_lane(main_root, lane_name):
        try:
            text = brief.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        owned |= _owns_in_text(text)
    return owned


def _owns_in_text(text: str) -> set[str]:
    """The ``Lane-owns:`` paths declared in one brief's text."""
    owned: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line.lower().startswith("lane-owns:"):
            continue
        payload = line.split(":", 1)[1].strip()
        # Comma-separated paths, POSIX-normalised.
        for token in payload.split(","):
            token = token.strip().strip("`").strip()
            if token:
                owned.add(token.replace("\\", "/"))
    return owned


def _staged_paths(repo_root: Path) -> set[str]:
    """Paths staged for the commit about to land, POSIX-normalised."""
    out = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"], repo_root)
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}


def _contested(staged: set[str], owned: set[str]) -> set[str]:
    """Paths in both sets, treating directory ownership as a prefix.

    A lane that owns ``dev/capture/`` owns every path under it; a lane that
    owns ``watch.py`` owns exactly that file.
    """
    contested: set[str] = set()
    for s in staged:
        for o in owned:
            if s == o or s.startswith(o.rstrip("/") + "/"):
                contested.add(s)
                break
    return contested


def check(root: Path) -> int:
    """Run the guard against a commit landing in ``root``. Returns an exit code.

    0 = allow (no lane out, or no overlap); 1 = refuse (contested path); 2 =
    guard could not evaluate its inputs (fail loud).
    """
    if not is_main_checkout(root):
        # A linked worktree commits freely; the guard only acts on the main
        # checkout, which is where a lane's stray edits become dangerous.
        sys.stderr.write(
            "lane-containment guard: OK — linked worktree commit; "
            "the MAIN CHECKOUT alone is guarded\n"
        )
        return 0
    try:
        lanes = _parse_worktree_list(root)
    except GuardError as exc:
        sys.stderr.write(f"lane-containment guard: {exc}; refusing\n")
        return 2
    if not lanes:
        # This is an allow, not evidence of containment: there was no lane
        # population against which ownership could be compared.
        sys.stderr.write(
            "lane-containment guard: NOT EVALUATED — no lane worktrees exist; "
            "allowing commit without an ownership comparison\n"
        )
        return 0
    staged = _staged_paths(root)
    if not staged:
        # Nothing to commit (e.g. ``--amend`` with no changes, or a hook fired
        # by something other than a content commit). Nothing to guard.
        return 0
    findings: list[str] = []
    undeclared: list[str] = []
    main_root = _main_checkout_root(root)
    for lane_root, branch in lanes:
        owned = _owned_paths_for_lane(main_root, lane_root.name)
        if not owned:
            # No declared ownership → nothing to protect for this lane. The
            # lint companion (check_brief_lane_owns) ensures this is loud at
            # brief-write time rather than a silent no-op at commit time.
            undeclared.append(f"{branch} ({lane_root})")
            continue
        contested = _contested(staged, owned)
        if contested:
            findings.append(
                f"  lane {branch} ({lane_root}) owns: "
                f"{', '.join(sorted(owned))}\n"
                f"    contested staged paths: {', '.join(sorted(contested))}"
            )
    if not findings:
        if undeclared:
            sys.stderr.write(
                "lane-containment guard: INCOMPLETE — allowing commit, but "
                f"{len(undeclared)} of {len(lanes)} lane(s) declare no "
                "Lane-owns: paths and are unprotected: "
                + ", ".join(undeclared)
                + "\n"
            )
        else:
            sys.stderr.write(
                f"lane-containment guard: OK — examined {len(lanes)} lane(s); "
                f"{len(staged)} staged path(s); no ownership overlap\n"
            )
        return 0
    sys.stderr.write(
        "lane-containment guard (#465): refusing commit in the MAIN CHECKOUT.\n"
        "A dispatched lane owns one or more of the staged paths. Committing\n"
        "them on master would reproduce the #465 defect — a lane editing the\n"
        "main checkout instead of its worktree. Either commit from the lane's\n"
        "worktree, or unstage the contested paths on master.\n\n"
        + "\n".join(findings)
        + "\n\nEmergency bypass: "
        f"{BYPASS_ENV}=1 git commit ... (then fix the root cause)\n"
    )
    return 1


def _selftest() -> int:
    """A no-side-effect smoke check that the guard evaluates on this tree.

    Reports the detected main-checkout status, the enumerated lanes, and each
    lane's declared ownership. Does NOT refuse — this is introspection, not the
    commit gate. Useful to confirm the guard sees what it should before relying
    on it.
    """
    root = repo_root(Path.cwd())
    main = is_main_checkout(root)
    print(f"root: {root}")
    print(f"is_main_checkout: {main}")
    lanes = _parse_worktree_list(root)
    print(f"worktrees examined: {lanes.examined}")
    print(f"lanes classified: {len(lanes)}")
    main_root = _main_checkout_root(root)
    for lane_root, branch in lanes:
        owned = _owned_paths_for_lane(main_root, branch)
        print(f"  {branch} ({lane_root}): owns {sorted(owned) if owned else '(none declared)'}")
    return 0


# --------------------------------------------------------------------------- #
# R2 — the pre-merge assertion (#468)                                         #
# --------------------------------------------------------------------------- #
# `git merge wt/<lane>` aborts when the main checkout's index or worktree is
# dirty with someone else's work, and the abort message names FILES rather than
# the reason, so it reads as a conflict. It happened twice: once staged-but-
# uncommitted briefs, once a lane's edit in the main checkout. In both the merge
# was half-done before the cause became clear.
#
# WHERE IT LIVES, on the will-it-be-skipped axis. A `pre-merge-commit` hook is
# the only automatic form and it is ruled out: it does NOT fire on a fast-
# forward (a hook that silently does not run is worse than no hook), and wiring
# wiring it repo-locally is a separate coordinator-controlled step. So R2 is
# an explicit subcommand the coordinator runs before merging, reusing THIS module's lane registry and the
# backstop's ownership reader. The one-word habit that closes the "remember" gap
# is a `just merge-lane <branch>` wrapper (justfile is not this file's to write;
# the report carries the line). The ambient half is already lint's backstop,
# which catches lane-owned dirt whenever lint runs; this subcommand adds the
# merge-time preconditions the backstop does not: full index/worktree cleanliness
# (a merge aborts on the coordinator's OWN uncommitted work too, which no lane
# owns), untracked-clobber, and branch identity.
#
# It reuses lint's ownership resolution (``lint.lane_owned_paths`` /
# ``_live_lane_worktrees`` / ``_dirty_paths``) — never a second reader. The
# import is lazy so the hot pre-commit hook path does not pay lint's import cost
# (constraint C: nothing may make the loop's own commits harder).

def _import_lint():
    """Lazy import of the lint module, with the repo root on sys.path.

    lane_guard.py lives in dev/, so `python3 dev/lane_guard.py` puts dev/ on
    sys.path[0], not the repo root where lint.py sits. The pre-merge path needs
    lint (the single lane-ownership reader); the hook path never calls this.
    """
    import importlib
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return importlib.import_module("lint")


def _classify_status(root: Path) -> tuple[list[str], list[str], list[str]] | None:
    """Split ``git status`` into (staged, unstaged_tracked, untracked).

    None when git cannot be asked — the caller must fail loud rather than report
    a clean tree it never measured. Uses ``--no-optional-locks`` for the same
    reason lint's ``_dirty_paths`` does: a background ``git status`` taking the
    real index.lock is a documented mitigation on this machine.

    This is merge-precondition PLUMBING, not an ownership reader: it classifies
    git's status columns, while ownership comes from lint's Lane-owns parser.
    """
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "status",
             "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    for line in out.stdout.splitlines():
        if len(line) < 4:
            continue
        x, y = line[0], line[1]
        entry = line[3:]
        if " -> " in entry:  # rename: the destination is the path that matters
            entry = entry.split(" -> ", 1)[1]
        path = entry.strip().strip('"').replace("\\", "/")
        if not path:
            continue
        if x == "?" and y == "?":
            untracked.append(path)
            continue
        if x not in (" ", "?"):  # index differs from HEAD
            staged.append(path)
        if y not in (" ", "?"):  # worktree differs from index
            unstaged.append(path)
    return staged, unstaged, untracked


def _merge_added_paths(root: Path, branch: str) -> list[str] | None:
    """Paths the merge of ``branch`` into HEAD would ADD (absent in HEAD).

    Used to detect untracked files the merge would clobber — the other merge-
    abort cause. None on git failure (caller fails loud). Read-only: ``git diff``
    writes nothing.
    """
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "diff", "--name-only",
             "--diff-filter=A", "HEAD", branch],
            capture_output=True, text=True, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [ln.strip().replace("\\", "/") for ln in out.stdout.splitlines() if ln.strip()]


def _pre_merge(root: Path, branch: str) -> int:
    """Assert the preconditions of ``git merge <branch>`` in the main checkout.

    Returns 0 = safe to merge; 1 = a precondition failed (refused, with the one
    action that clears it); 2 = could not evaluate (fail loud). Never moves work:
    it does not stash, reset, checkout or merge — eight lanes have run in this
    tree, and a helpful automatic cleanup is how a lane's uncommitted hour
    disappears.
    """
    out = sys.stdout
    err = sys.stderr

    if not is_main_checkout(root):
        err.write(
            "pre-merge: run from the MAIN CHECKOUT, not a worktree. A merge of a\n"
            "lane lands in the main tree, so that is where its preconditions hold.\n"
        )
        return 2

    lint = _import_lint()
    try:
        lanes = lint._live_lane_worktrees(root)
    except lint.LaneEnumerationError as exc:
        err.write(
            f"pre-merge: could not classify registered worktrees: {exc}; "
            f"worktrees examined={exc.examined}; lanes classified={exc.classified}; refusing\n"
        )
        return 2

    # Accept either the exact branch or the stable worktree name. The latter
    # keeps pre-merge usable after a post-dispatch branch rename.
    by_name = {Path(path).name: lane_branch for path, lane_branch in lanes}
    norm = (
        branch
        if branch in {lane_branch for _, lane_branch in lanes}
        else by_name.get(branch, branch)
    )

    classified = _classify_status(root)
    if classified is None:
        err.write(
            "pre-merge: `git status` could not be read — cannot assert the merge\n"
            "preconditions. Investigate before merging; a silent allow is the state\n"
            "this guard exists to prevent.\n"
        )
        return 2
    staged, unstaged, untracked = classified

    added = _merge_added_paths(root, norm)
    if added is None:
        # A branch git cannot resolve is almost always a typo. Fail loud naming
        # it, which is the branch-identity check's loudest form.
        err.write(
            f"pre-merge: could not diff HEAD against `{norm}` — the branch does\n"
            f"not resolve (typo? not fetched?). Aborting before the merge.\n"
        )
        return 2
    added_set = set(added)

    # Ownership, reusing lint's reader. dirty = staged + unstaged + untracked,
    # exactly the set the backstop intersects.
    dirty = lint._dirty_paths(root)
    if dirty is None:
        err.write("pre-merge: `git status` dirty-path set unreadable — refusing\n")
        return 2
    dw = root / ".dreamwork"
    findings: list[str] = []
    examined = 0
    for lane_path, lbranch in lanes:
        owned = lint.lane_owned_paths(dw, lbranch, lane_path)
        if not owned:
            continue
        examined += 1
        contested = _contested(set(dirty), set(owned))
        if contested:
            findings.append(
                f"  {', '.join(sorted(contested))} dirty in the MAIN CHECKOUT but\n"
                f"    owned by lane {lbranch} ({lane_path}); #465 — a lane editing\n"
                f"    the main tree aborts the merge. Retire a FINISHED lane's\n"
                f"    worktree (`git worktree remove {lane_path}`), or let the\n"
                f"    lane commit its work there. Do NOT commit the contested\n"
                f"    paths on master."
            )

    # Merge-blocking tracked dirt: the coordinator's OWN uncommitted work. No
    # lane owns it, so the backstop is silent on it, but a merge aborts on it
    # regardless. Remedy is commit-or-unwind — we do not offer stash/reset.
    blocking_tracked = sorted(set(staged) | set(unstaged))
    if blocking_tracked:
        findings.append(
            "  index/worktree not clean: " + ", ".join(blocking_tracked) + "\n"
            "    a merge aborts on local changes to tracked files. Commit or unwind\n"
            "    your own work in the main checkout first. (This assertion never\n"
            "    stashes, resets or checks out — it does not move work.)"
        )

    # Untracked files the merge would overwrite.
    clobber = sorted(set(untracked) & added_set)
    if clobber:
        findings.append(
            "  untracked, would be overwritten by merge of " + norm + ": "
            + ", ".join(clobber) + "\n"
            "    move or remove the untracked file(s) before merging."
        )

    if findings:
        err.write(
            f"pre-merge (#468): refusing to merge `{norm}` into the main checkout.\n"
            "One or more merge preconditions failed:\n\n"
            + "\n".join(findings)
            + "\n"
        )
        return 1

    # Branch identity: informational. A non-lane branch may be a legitimate
    # merge or a typo'd lane name; the ownership check above already covered
    # every live lane regardless.
    registered = norm in {b for _, b in lanes}
    id_note = (
        f"registered lane `{norm}`" if registered
        else f"NOTE: `{norm}` is not a registered lane worktree "
             f"(merging a non-lane branch; ownership still checked against all "
             f"{len(lanes)} live lane(s))"
    )
    out.write(
        f"pre-merge OK: safe to merge `{norm}`.\n"
        f"  {id_note}; {lanes.examined} worktree(s) examined; "
        f"{len(lanes)} lane(s) classified;\n"
        f"  {examined} of {len(lanes)} live lane(s) declare ownership;\n"
        f"  index clean (0 staged), worktree clean (0 unstaged-tracked),\n"
        f"  0 untracked-clobber, 0 lane-owned dirty paths.\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lane-containment pre-commit guard (#465). See module docstring."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="hook",
        choices=["hook", "install", "uninstall", "selftest", "pre-merge"],
        help="hook = run as a pre-commit guard (default); install/uninstall are "
        "retired in favour of the repo-local just recipes; "
        "selftest = introspect without refusing; "
        "pre-merge BRANCH = assert the preconditions of `git merge BRANCH` (#468)",
    )
    parser.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="for pre-merge: the branch to merge (wt/<name> or <name>); "
        "otherwise passed by git when invoked as a hook (ignored)",
    )
    args = parser.parse_args(argv)

    if args.mode == "install":
        sys.stderr.write(
            "lane-guard: direct install is retired; run `just enable-lane-guard` "
            "to set this repository's core.hooksPath\n"
        )
        return 2
    if args.mode == "uninstall":
        sys.stderr.write(
            "lane-guard: direct uninstall is retired; run `just disable-lane-guard` "
            "to unset this repository's core.hooksPath\n"
        )
        return 2
    if args.mode == "selftest":
        return _selftest()
    if args.mode == "pre-merge":
        branch = args.rest[0] if args.rest else ""
        if not branch:
            sys.stderr.write(
                "pre-merge: a branch argument is required "
                "(e.g. `dev/lane_guard.py pre-merge wt/foo`)\n")
            return 2
        root = repo_root(Path.cwd())
        try:
            return _pre_merge(root, branch)
        except GuardError as exc:
            sys.stderr.write(f"pre-merge: cannot evaluate ({exc}); refusing\n")
            return 2

    # mode == "hook"
    if os.environ.get(BYPASS_ENV):
        # Documented emergency escape. A hook that cannot be bypassed is a hook
        # that gets disabled; a disabled hook protects nothing.
        sys.stderr.write(
            f"lane-containment guard: BYPASSED because {BYPASS_ENV} is set\n"
        )
        return 0
    root = repo_root(Path.cwd())
    try:
        return check(root)
    except GuardError as exc:
        # Fail loud: a guard that cannot evaluate its inputs must not silently
        # allow a contested commit through.
        sys.stderr.write(f"lane-containment guard: cannot evaluate ({exc}); refusing\n")
        sys.stderr.write(
            "Investigate before using the bypass. A refused commit is recoverable;\n"
            "a silent allow is the state this guard exists to prevent.\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
