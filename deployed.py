#!/usr/bin/env python3
"""deployed — which revision is a target's dashboard actually serving, and how far behind is it?

    python3 deployed.py [--target DIR] [--repo DIR]

`just deploy` snapshots `git show HEAD:watch.py` to a file outside the repo,
so the running server cannot be changed by an agent editing the tree. That
is the right property and it has one cost: **the running code's identity is
not recorded anywhere.** A fix can be committed and undeployed while the
human is looking at the page, which is indistinguishable from broken and
has already cost one tracing cycle (#129).

This answers it by comparing BYTES — the snapshot against each revision of
`watch.py` — rather than trusting a recorded claim. That choice is
deliberate. A sidecar file naming the deployed sha would be cheaper and
would be a *proxy*: it says what someone believed they deployed, and this
repo learned on #155 that a proxy check eventually gets believed as the
thing it proxies. The bytes cannot be wrong.

WHY IT IS A MODULE AND NOT THREE LINES OF SHELL. It was three lines of
shell first, and it produced three different wrong answers in a row — "five
commits behind", then "matches no commit at all", then the truth (two). The
shell mangled `$r:watch.py` into `$r` + `tch.py`, and `2>/dev/null` hid the
fatal on every iteration, so the comparison ran zero times and reported "no
match" with total confidence. Hence the rule this module is built around:

    **A comparison that could not run must never look like a comparison
    that ran and found nothing.**

Every failure below is its own named state, and none of them is `None`
meaning "no match".

Never takes `.git/index.lock`: read-only plumbing with `--no-optional-locks`
throughout. His CLAUDE.md carries an active mitigation about that lock and
this must not become the thing that reintroduces it.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

DEPLOY_DIR = Path("~/.cache/dreamwork/deployed").expanduser()

# States. Each is a distinct answer to "what is running?", and the point of
# separating them is that only ONE of them means "I compared and they
# differ" — the others mean "I could not compare", which is a different
# thing to tell a human.
CURRENT = "current"           # serving HEAD's watch.py
BEHIND = "behind"             # serving an older revision, and we know which
NEVER = "never deployed"      # no snapshot on disk
UNTRACKED = "untracked"       # snapshot matches no revision — a dirty-tree deploy
NO_REPO = "no repo"           # target is not a git checkout of the dashboard
ERROR = "error"               # git itself failed; explicitly NOT "no match"


def git(repo: Path, *args: str, binary: bool = False):
    """Read-only git. Raises on failure — a caller must not mistake a broken
    invocation for an empty result, which is the whole bug this file exists
    for."""
    out = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        capture_output=True, check=True,
    )
    return out.stdout if binary else out.stdout.decode("utf-8", "replace")


def snapshot_for(target: Path) -> Path:
    """Where `just deploy` puts this target's snapshot. Mirrors the recipe:
    `$dir/$(basename "$PWD")-watch.py`."""
    return DEPLOY_DIR / f"{target.name}-watch.py"


def served_siblings(src: bytes) -> list:
    """The files, besides watch.py, whose bytes reach the browser at `src`'s
    revision — its module-level `DATA_SIBLINGS` literal.

    #397 is why this exists. Until the client was extracted, `watch.py`'s
    bytes WERE the dashboard: css and js lived in string literals inside it,
    so comparing that one file answered "is he looking at current code"
    completely. Afterwards the same comparison answers it for 5,181 lines of
    Python and stays silent about 10,500 lines of css and js — a normal UI
    commit now leaves watch.py byte-identical, and this module would have
    called that `current` while the dashboard served the old page. That is
    precisely the #129 failure this file was written to end, reopened by a
    refactor rather than by a proxy.

    Parsed per-revision, never from HEAD, for the same reason the byte
    comparison is per-revision: a pre-extraction revision declares only
    `vendor/morphdom.min.js` and must be judged by what IT served, not by
    what HEAD serves. A revision with no literal (or an unparseable one)
    yields none, which degrades to the old watch.py-only comparison rather
    than to a false match.
    """
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "DATA_SIBLINGS"
                   for t in node.targets):
            continue
        try:
            val = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return []
        if isinstance(val, (tuple, list)):
            return sorted(p for p in val if isinstance(p, str))
        return []
    return []


def report(target: Path, repo: Path, path: str = "watch.py") -> dict:
    """What is running for `target`, against `repo`'s history of `path`."""
    target, repo = Path(target).resolve(), Path(repo).resolve()
    snap = snapshot_for(target)
    out = {"target": str(target), "snapshot": str(snap), "path": path,
           "paths": [path], "state": None, "rev": None, "missing": [],
           "note": None}

    if not snap.exists():
        out["state"] = NEVER
        out["note"] = f"no snapshot at {snap} — this target has never been deployed"
        return out

    # History FIRST, and its emptiness is checked before anything else is
    # read. A repo that simply does not track `path` is an ordinary state
    # (a target whose dashboard lives elsewhere), and asking `git show
    # HEAD:<path>` about it raises — which would report a normal target as
    # a broken one.
    try:
        revs = git(repo, "log", "--format=%H", "--", path).split()
    except (subprocess.CalledProcessError, OSError) as exc:
        out["state"] = NO_REPO if not (repo / ".git").exists() else ERROR
        out["note"] = f"could not read the history of {path} in {repo}: {exc}"
        return out

    if not revs:
        out["state"] = NO_REPO
        out["note"] = f"{path} has no history in {repo}"
        return out

    try:
        head_blob = git(repo, "show", f"HEAD:{path}", binary=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        out["state"] = ERROR
        out["note"] = f"could not read {path} at HEAD in {repo}: {exc}"
        return out

    # Now that HEAD is readable, widen the candidate list to every path whose
    # bytes reach the browser. The FIRST query above stays scoped to `path`
    # on purpose — its job is the "does this repo carry the dashboard at all"
    # guard, and asking it about client/ would make a repo that tracks the
    # assets but not watch.py look like a dashboard checkout.
    #
    # Without this widening the fix above would be half-applied: `matches`
    # would correctly reject a stale client, but a client-only commit would
    # not be among the revisions offered to it, so the deploy would fall
    # through every candidate and be reported UNTRACKED — "deployed from an
    # uncommitted tree" — which is a confident lie rather than a silent one.
    tracked_paths = [path] + served_siblings(head_blob)
    out["paths"] = tracked_paths
    try:
        revs = git(repo, "log", "--format=%H", "--", *tracked_paths).split()
    except (subprocess.CalledProcessError, OSError) as exc:
        out["state"] = ERROR
        out["note"] = f"could not read the history of the dashboard: {exc}"
        return out

    blob = snap.read_bytes()

    def deployed_sibling(rel: str):
        """The deployed copy of a served sibling — `ship_siblings` puts it
        beside the snapshot, at the same repo-relative path."""
        try:
            return (snap.parent / rel).read_bytes()
        except OSError:
            return None

    def matches(rev: str, src: bytes) -> bool:
        """Does the DEPLOYED dashboard equal `rev` — watch.py AND everything
        `rev` serves alongside it? A missing deployed sibling is a mismatch,
        never a skip: the alternative is reporting `current` for a deploy
        that has no stylesheet."""
        if src != blob:
            return False
        for rel in served_siblings(src):
            want = deployed_sibling(rel)
            if want is None:
                return False
            try:
                if git(repo, "show", f"{rev}:{rel}", binary=True) != want:
                    return False
            except subprocess.CalledProcessError:
                return False
        return True

    if matches("HEAD", head_blob):
        out["state"] = CURRENT
        out["rev"] = git(repo, "rev-parse", "--short", "HEAD").strip()
        return out

    for rev in revs:
        try:
            if matches(rev, git(repo, "show", f"{rev}:{path}", binary=True)):
                break
        except subprocess.CalledProcessError:
            continue
    else:
        # Every revision was read and none matched. This is the ONLY path
        # that may say "no match", and it is reached only after the loop
        # genuinely ran.
        out["state"] = UNTRACKED
        out["note"] = (f"the running {path} matches none of {len(revs)} revisions — "
                       "deployed from an uncommitted tree, so what is serving him "
                       "exists nowhere in history")
        return out

    out["state"] = BEHIND
    out["rev"] = git(repo, "rev-parse", "--short", rev).strip()
    # Name what he cannot see across the WHOLE dashboard, not just watch.py:
    # listing only watch.py commits here would report "BEHIND by 0 commits"
    # for a deploy that is behind purely on css, which reads as a bug in the
    # reporter rather than as the stale deploy it is.
    out["missing"] = [
        line.split(" ", 1) for line in
        git(repo, "log", "--format=%h %s", f"{rev}..HEAD",
            "--", *tracked_paths).splitlines()
    ]
    return out


def render(r: dict) -> str:
    state = r["state"]
    # "watch.py commits" was accurate when watch.py WAS the dashboard. Since
    # #397 most UI commits touch only client/, so naming the file here would
    # tell him the one thing that is no longer the question.
    unit = "dashboard" if len(r.get("paths") or []) > 1 else r["path"]
    if state == CURRENT:
        return f"current ({r['rev']}) — serving HEAD's {unit}"
    if state == BEHIND:
        n = len(r["missing"])
        head = f"BEHIND by {n} {unit} commit{'s' if n != 1 else ''} (serving {r['rev']})"
        return "\n".join([head] + [f"  missing  {h}  {s}" for h, s in r["missing"]])
    return f"{state} — {r['note']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="deployed",
        description="Which revision is a target's dashboard actually serving?")
    ap.add_argument("--target", default=".", help="target project directory")
    ap.add_argument("--repo", default=None,
                    help="repo holding the dashboard's history (default: the skill dir)")
    ap.add_argument("--path", default="watch.py")
    args = ap.parse_args(argv)

    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parent
    r = report(Path(args.target), repo, args.path)
    print(render(r))
    # Only a genuine mismatch is worth a non-zero exit; "never deployed" is
    # a normal state and must not fail anyone's gate.
    return 1 if r["state"] in (BEHIND, UNTRACKED) else 0


if __name__ == "__main__":
    sys.exit(main())
