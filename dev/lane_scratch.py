#!/usr/bin/env python3
"""Lane-private scratch directory, DERIVED from lane identity rather than chosen (#652).

Why this exists
---------------
Every agent is told by its harness that the scratchpad under ``/tmp/claude-<uid>/``
is "session-specific, isolated". Measured 2026-07-31: that is true of a *CLI
session* and false of a *lane*. All lanes dispatched from one coordinator run as
subagents inside a single CLI process and inherit one ``CLAUDE_CODE_SESSION_ID``,
so every concurrent lane resolves to the **same** scratchpad directory (same
inode). See #652 for the measurement.

That matters because the #349 red-proof protocol (``lessons.md``) tells every
lane to snapshot a file *outside the repo* before a deliberate RED injection and
restore it with ``cp`` — never ``git checkout``. The natural home for that
snapshot is the scratchpad and the natural names are generic
(``router.js.orig``, ``style.css.bak``). Two concurrent lanes choosing the same
name means one lane's restore writes the *other* lane's bytes over its file, and
**both** lanes' ``cmp`` checks still pass, against the wrong baseline. The safety
protocol becomes a silent corruption vector.

The fix is a path the lane does not get to pick. The dispatcher gives each
launch a random ``DREAMWORK_LANE_ID`` which every later process in that lane
inherits. The worktree key remains as a readable grouping, but it is not the
privacy boundary: two launches in one worktree get different directories.

Two properties, both load-bearing
---------------------------------
1. **One stable launch identity.** ``dispatch_lane.py`` creates 128 random bits
   for every dispatch and exports them through ``DREAMWORK_LANE_ID`` before it
   execs the runner. Exec and child processes inherit that value, so separate
   ``redproof.py begin`` and ``restore`` invocations rediscover the same path;
   neither PID reuse nor a shared worktree/brief can alias two launches.
2. **A named measurement location plus a positive control.** ``measure`` lives
   under the same lane-private ``~/.cache`` root. Its path does not promise a
   filesystem capability: real disk can still have coarse timestamps, disabled
   events, or other semantics that make a particular experiment unanswerable.
   ``require-mtime-change`` runs the experiment's exact positive-control command
   and refuses a negative unless that command first advances the subject's mtime.

Usage
-----
    dev/lane_scratch.py              # print this lane's private dir, creating it
    dev/lane_scratch.py --no-create  # print without creating
    dev/lane_scratch.py snap         # print (and create) a named subdir
    dev/lane_scratch.py measure      # the one filesystem-measurement location

    S="$(dev/lane_scratch.py snap)"
    cp client/router.js "$S/router.js"      # snapshot before the injection
    ...                                     # inject, watch it go red
    cp "$S/router.js" client/router.js      # restore -- never `git checkout`
    cmp client/router.js "$S/router.js"     # prove byte-identical

    M="$(dev/lane_scratch.py measure)"
    # Set up $M/probe, then exercise the SAME mmap/write path as the real probe:
    dev/lane_scratch.py require-mtime-change "$M/probe" -- <positive-control command>
    # exit 0 is silent; 1 = UNSUPPORTED; 2 = UNDETERMINED

Residual, stated rather than hidden: processes descended from one launch share
one directory because they inherit one launch token. Parallel subagents within
that launch still need distinct names when operating on the same file.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

# Root for all lane-private scratch. A literal ``~/.cache`` rather than
# XDG_CACHE_HOME on purpose: the coordinator and lanes may run under different
# harnesses with different XDG settings, and they must agree on where a lane's
# evidence lives. Matches the existing house convention of
# ``~/.cache/agent-comms/<repo>/``.
SCRATCH_ROOT = Path.home() / ".cache" / "ud-dreamwork" / "lane-scratch"

# A key segment is one path component, so anything that could escape it or
# collide across it is folded to '-'.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

# Detached worktrees all report this as their branch, so it is never a usable
# key on its own.
_DETACHED = "HEAD"

# Length of the path digest used to separate detached worktrees.
_DIGEST_LEN = 12

# Role keying (#694): a reviewer runs in the author's own worktree, so two
# roles resolve to the same lane_key and the reviewer's snapshots can silently
# overwrite the author's evidence — the exact #652 corruption, one worktree
# over. The role adds a segment under the lane key so the two never share a
# private directory.
#
# AUTHOR maps to no segment at all: the path is identical to the pre-#694
# layout, so the four live lanes' snapshots do not move mid-flight. A role that
# is anything else gets a `role-<slug>` segment.
ROLE_ENV = "DREAMWORK_LANE_ROLE"
IDENTITY_ENV = "DREAMWORK_LANE_ID"
ROLE_AUTHOR = "author"
ROLE_REVIEWER = "reviewer"
_KNOWN_ROLES = (ROLE_AUTHOR, ROLE_REVIEWER)


def _git(root: Path, *args: str) -> str | None:
    """Run git in ``root``; None on any failure rather than an exception."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return out.strip()


def _slug(text: str) -> str:
    """Fold arbitrary text into one safe path component."""
    return _UNSAFE.sub("-", text).strip("-.") or "unnamed"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:_DIGEST_LEN]


def worktree_root(cwd: Path | None = None) -> Path:
    """Absolute root of the worktree containing ``cwd``.

    Falls back to ``cwd`` itself outside a git repo, so the helper still yields
    a usable private directory rather than raising.
    """
    here = Path(cwd or Path.cwd()).resolve()
    top = _git(here, "rev-parse", "--show-toplevel")
    return Path(top).resolve() if top else here


def lane_key(cwd: Path | None = None) -> str:
    """Key identifying this lane, derived rather than chosen.

    Branch name where there is one, because git guarantees a branch is checked
    out in at most one worktree. Detached worktrees share the branch name
    ``HEAD``, so they are separated by a digest of their absolute path, which the
    filesystem keeps unique. A branch actually *named* ``detached-...`` would
    otherwise collide with that fallback, so it gets the digest too.
    """
    root = worktree_root(cwd)
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == _DETACHED:
        return f"detached-{_digest(str(root))}"
    key = _slug(branch)
    if key.startswith("detached-"):
        return f"{key}-{_digest(str(root))}"
    return key


def lane_role(*, env: dict | None = None) -> str:
    """The role this lane is playing (#694): ``author`` or ``reviewer``.

    Comes from ``DREAMWORK_LANE_ROLE``; defaults to AUTHOR because every lane
    that exists today is an author lane, and a default that moved four live
    lanes' snapshots would be worse than the bug (#755: a refusal on a healthy
    input is worse than no check).

    That default is also the honest boundary (#702), not a silent guarantee: a
    reviewer whose dispatcher does not set the env var gets the author's
    directory back **while the code is in place and the tests pass** (#671).
    Making it loud rather than silent is the job of the role appearing on every
    path the tool prints and every ``check`` verdict redproof reports — a
    reviewer who reads ``role: author`` on its own gate output sees the
    collision it would create. The tool cannot force the dispatcher to set the
    variable; it can only refuse to hide which side it landed on. Setting it is
    the dispatcher's job (``dev/dispatch_lane.py`` owns that, out of scope here).
    """
    source = os.environ if env is None else env
    role = source.get(ROLE_ENV, ROLE_AUTHOR).strip().lower()
    return role if role in _KNOWN_ROLES else _slug(role) or ROLE_AUTHOR


def lane_identity(*, env: dict | None = None) -> str | None:
    """The stable launch token inherited by every invocation in this lane.

    Absence deliberately means the legacy layout. Lanes already alive when
    launch identity was introduced therefore keep finding their snapshots;
    newly dispatched lanes receive a cryptographically random token.
    """
    source = os.environ if env is None else env
    value = source.get(IDENTITY_ENV, "").strip()
    return value or None


def identity_segment(identity: str | None = None) -> str:
    """One collision-resistant path component for a launch identity."""
    value = identity if identity is not None else lane_identity()
    if not value:
        return ""
    return f"lane-{_slug(value)}-{_digest(value)}"


def role_segment(role: str | None = None) -> str:
    """The path segment a role adds under the lane key, or ``""`` for author.

    Author is the empty string so the path matches the pre-#694 layout exactly
    — migration by not moving. Every other role gets ``role-<slug>``, which
    cannot collide with a branch name (those never contain a slash-escaped
    ``role-`` prefix in practice, and the slug is one component either way).
    """
    r = role if role is not None else lane_role()
    if r == ROLE_AUTHOR:
        return ""
    if r.startswith("role-"):
        seg = _slug(r)
    else:
        seg = _slug(f"role-{r}")
    return seg or ""


def repo_key(cwd: Path | None = None) -> str:
    """Key identifying the repo, shared by a main checkout and its worktrees.

    Uses the *common* git dir, so ``.worktrees/lane-x`` files under the same repo
    as the main checkout instead of inventing a sibling tree per worktree.
    """
    root = worktree_root(cwd)
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common:
        return _slug(Path(common).resolve().parent.name)
    return _slug(root.name)


def lane_identity_dirs(cwd: Path | None = None) -> list[Path]:
    """Existing ``lane-*`` identity dirs under this lane's key (#895).

    A coordinator auditing a finished lane has no ``DREAMWORK_LANE_ID`` — the
    token lives only in the dispatched process's env and is gone once the lane
    exits. Its registry (if any) sits under one of these ``lane-*`` dirs.
    Enumerating them is how the coordinator's audit finds a lane's evidence
    instead of resolving an empty scratch and printing an all-clear over it
    (#895: the misread that shipped this function).

    Returns existing ``lane-*`` directories under
    ``SCRATCH_ROOT/repo_key/lane_key/``, sorted by name. The legacy
    (no-identity-segment) dir is deliberately NOT included: callers handle it
    as the zero-identity case. Empty when the lane-key dir does not exist or
    holds no identity dirs. Read-only — never creates.
    """
    base = SCRATCH_ROOT / repo_key(cwd) / lane_key(cwd)
    if not base.is_dir():
        return []
    return sorted(
        child for child in base.iterdir()
        if child.is_dir() and child.name.startswith("lane-"))


def lane_scratch_dir(cwd: Path | None = None, *, create: bool = True,
                     sub: str | None = None, role: str | None = None) -> Path:
    """This lane's private scratch directory (optionally a named subdir).

    The path is keyed on repo + worktree + launch identity + **role** (#694).
    A missing launch identity maps to the legacy path, so live lanes do not
    move when this mechanism is deployed.
    """
    path = SCRATCH_ROOT / repo_key(cwd) / lane_key(cwd)
    identity = identity_segment()
    if identity:
        path = path / identity
    seg = role_segment(role)
    if seg:
        path = path / seg
    if sub:
        for part in Path(sub).parts:
            path = path / _slug(part)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def require_mtime_change(path: Path, command: list[str]) -> int:
    """Run an exact positive control, requiring ``path``'s mtime to advance.

    Exit 0 is deliberately silent. Exit 1 means the command ran but this
    substrate did not exhibit the property, so a later negative is not
    evidence. Exit 2 means the control could not be judged at all. Keeping
    unsupported and undetermined distinct prevents both from rendering as OK.
    """
    try:
        before = path.stat().st_mtime_ns
    except OSError as exc:
        print(
            f"UNDETERMINED: cannot stat {path} before the positive control: {exc}",
            file=sys.stderr,
        )
        return 2

    if not command:
        print("UNDETERMINED: no positive-control command was supplied", file=sys.stderr)
        return 2

    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        print(f"UNDETERMINED: positive control could not run: {exc}", file=sys.stderr)
        return 2
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        print(
            f"UNDETERMINED: positive control command exited {result.returncode}{suffix}",
            file=sys.stderr,
        )
        return 2

    try:
        after = path.stat().st_mtime_ns
    except OSError as exc:
        print(
            f"UNDETERMINED: cannot stat {path} after the positive control: {exc}",
            file=sys.stderr,
        )
        return 2
    if after <= before:
        print(
            "UNSUPPORTED: positive control ran but mtime did not advance for "
            f"{path} (before={before}, after={after}); do not believe a negative "
            "measurement on this substrate",
            file=sys.stderr,
        )
        return 1
    return 0


def _mtime_control_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="lane_scratch.py require-mtime-change",
        description=(
            "Run an exact positive-control command and require the subject's "
            "mtime to advance."
        ),
    )
    ap.add_argument("path", type=Path, help="file whose mtime the control must advance")
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="command after --; it must exercise the real probe's mechanism")
    args = ap.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    return require_mtime_change(args.path, command)


def author_dir(cwd: Path | None = None, *, create: bool = False,
               sub: str | None = None) -> Path:
    """The AUTHOR's scratch directory, regardless of the caller's own role.

    A reviewer needs to READ the author's evidence (it is what made the #674
    verdict possible), so this gives it a handle to the author's directory
    without the reviewer having to know the layout. Read-only by convention:
    the reviewer writes to its OWN directory, never this one.
    """
    return lane_scratch_dir(cwd, create=create, sub=sub, role=ROLE_AUTHOR)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["require-mtime-change"]:
        return _mtime_control_main(argv[1:])
    ap = argparse.ArgumentParser(
        description="Print this lane's private scratch directory (#652). "
                    "Role-keyed (#694): a reviewer gets a separate subdir.")
    ap.add_argument("sub", nargs="?", default=None,
                    help="optional subdirectory, e.g. 'snap'")
    ap.add_argument("--no-create", action="store_true",
                    help="print the path without creating it")
    ap.add_argument("--cwd", default=None,
                    help="derive for this directory instead of the current one")
    ap.add_argument("--role", default=None,
                    help=f"override the role (env {ROLE_ENV}, default "
                         f"{ROLE_AUTHOR}); 'reviewer' keys a separate subdir")
    ap.add_argument("--author-evidence", action="store_true",
                    help="print the AUTHOR's directory (for a reviewer to "
                         "read the author's evidence), not the caller's own")
    args = ap.parse_args(argv)
    cwd = Path(args.cwd) if args.cwd else None
    if args.author_evidence:
        print(author_dir(cwd, create=not args.no_create, sub=args.sub))
        return 0
    role = args.role or lane_role()
    d = lane_scratch_dir(cwd, create=not args.no_create, sub=args.sub, role=role)
    print(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
