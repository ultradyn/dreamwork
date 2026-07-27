#!/usr/bin/env python3
"""task_origins.py — who filed each task, read from the ledger's first sight.

The ledger (`.dreamwork/tasks.md`) records `origin: **human|loop|unknown**`
on new entries (#213), but a task's origin is a fact about its ARRIVAL, not
about its current text: a later edit is documentation, never time travel.
So this module walks the ledger's own git history oldest-to-newest and
classifies every numeric id from the FIRST snapshot where it appears in a
leading bold task token — and never revisits that classification.

Reading rules, each deliberate:

- Only the leading bold token of an entry numbers it (`- **#250/#251**`
  classifies both 250 and 251 from that one entry). A `#N` in the body is
  a cross-reference and never classifies anything.
- Only that first snapshot's explicit marker speaks. `human` and `loop`
  are accepted; a missing, invalid, wrong-case, or duplicated marker is
  fail-closed to `unknown` — the truthful value, never a guess. Commit
  author, commit message, the current file, and later edits are never
  consulted.
- An id that first appears separately and earlier keeps that record even
  when a later combined entry lists it again.
- A deleted task stays in the output: first sight already happened, and
  grooming cannot un-happen it.
- A malformed snapshot cannot crash the walk; at worst its affected entry
  reads `unknown`, which is what an unreadable claim IS.

The entry and marker grammar is IMPORTED from lint.py (the #213 contract's
one copy — a second copy of one rule is how the priority-marker check
drifted, 3073055). Nothing here is re-derived.

CLI:

    python3 task_origins.py --repo <target> [--path .dreamwork/tasks.md] [--json]

stdout is JSON either way: pretty-printed by default, single-line with
`--json`. Exit status is nonzero ONLY for real repo/path/git errors (not a
git checkout, an escaping or absolute --path, git itself failing); a
missing ledger or an empty history is a truthful empty result. The output
shape:

    {
      "repo": "<abs path>",
      "path": ".dreamwork/tasks.md",
      "history_complete": true,          // false on a shallow/partial clone
      "history_note": null,              // why, when incomplete
      "tasks": [
        {"id": 300, "origin": "human", "first_commit": "<sha>",
         "first_seen": 1784900000, "title": "…"},   // sorted by id
      ]
    }

Rendering this on the dashboard is #217 and is deliberately NOT here.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lint  # the #213 entry/marker grammar — imported, never re-copied  # noqa: E402

DEFAULT_PATH = ".dreamwork/tasks.md"
GIT_TIMEOUT = 15

# `human` and `loop` are claims about who filed the task. `unknown` — the
# only other value in lint.ORIGIN_VALUES — is the absence of such a claim,
# so every unreadable case folds into it rather than being invented.
KNOWN_ORIGINS = ("human", "loop")


class TaskOriginsError(Exception):
    """A real repo/path/git error — the ONLY thing the CLI exits nonzero for."""


def _confine_path(path: str) -> str:
    """The ledger path must stay inside the repo: relative, no `..` escape.

    It becomes a `git show <rev>:<path>` argument, and an absolute or
    escaping path would read outside the history being claimed.
    """
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        raise TaskOriginsError(
            f"--path must be a relative path inside the repo, got {path!r}")
    return p.as_posix()


def _git(repo: Path, *args: str) -> str:
    """One read-only git invocation. argv list, never a shell; nothing here
    evaluates a revision expression or mutates the ledger."""
    res = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        capture_output=True, timeout=GIT_TIMEOUT)
    if res.returncode != 0:
        raise TaskOriginsError(
            res.stderr.decode("utf-8", "replace").strip()
            or f"git {' '.join(args)} exited {res.returncode}")
    return res.stdout.decode("utf-8", "replace")


def _classify(entry_text: str) -> str:
    """The origin of one entry, from that entry alone, fail-closed.

    Exactly one marker whose value is human or loop is a claim; anything
    else — none, several, an out-of-vocabulary value — is unknown. This is
    the linter's own vocabulary decision, minus the error reporting.
    """
    try:
        marks = [v.strip() for v in lint.ORIGIN_MARK.findall(entry_text)]
    except Exception:
        return "unknown"
    if len(marks) == 1 and marks[0] in KNOWN_ORIGINS:
        return marks[0]
    return "unknown"


def _title(entry_text: str) -> str:
    """The entry's first line minus its leading `- **#…**` token — enough
    context for a renderer (#217) without re-parsing the file."""
    first = entry_text.split("\n", 1)[0].strip()
    return lint.ENTRY_HEAD.sub("", first, count=1).lstrip(" —·").strip()


def task_origins(repo, path: str = DEFAULT_PATH) -> dict:
    """First-seen origin of every ledger id, oldest history first.

    Returns the JSON-serializable shape documented in the module docstring.
    Raises TaskOriginsError on a non-repo, an escaping path, or a git
    failure — and on nothing else.
    """
    repo = Path(repo).resolve()
    rel = _confine_path(path)
    if not (repo / ".git").exists():
        raise TaskOriginsError(f"{repo} is not a git checkout")

    # Commits that touched the ledger, oldest first. The list is stable
    # sorted by commit time so a chronological tie resolves in commit
    # order (parent before child) rather than by clock noise.
    log = _git(repo, "log", "--format=%H %ct", "--reverse", "--", rel)
    revs = []
    for line in log.split("\n"):
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0]:
            try:
                revs.append((parts[0], int(parts[1])))
            except ValueError:
                continue
    revs.sort(key=lambda rc: rc[1])  # stable: ties keep commit order

    # A shallow or partial clone cannot see first sight for anything filed
    # before its boundary; say so instead of claiming full coverage.
    complete = _git(repo, "rev-parse", "--is-shallow-repository").strip() != "true"
    note = None
    if not complete:
        note = ("this clone is shallow — first sightings before its "
                "boundary are invisible, so these records may describe a "
                "later edit rather than the true arrival")

    seen = {}
    for rev, ct in revs:
        try:
            text = _git(repo, "show", f"{rev}:{rel}")
        except (TaskOriginsError, subprocess.SubprocessError):
            # One unreadable revision is a hole, not a failed history —
            # the same call watch.py's ledger_series makes.
            continue
        try:
            entries = lint.ledger_entries(text)
        except Exception:
            continue  # a malformed snapshot fails closed, never the walk
        for ids, body in entries:
            origin = _classify(body)
            title = _title(body)
            for i in ids:
                if i not in seen:  # first sight is final
                    seen[i] = {"id": i, "origin": origin,
                               "first_commit": rev, "first_seen": ct,
                               "title": title}

    return {"repo": str(repo), "path": rel,
            "history_complete": complete, "history_note": note,
            "tasks": [seen[i] for i in sorted(seen)]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="First-seen human/loop/unknown origin of every task in "
                    "a dreamwork ledger, read from its git history (#216).")
    ap.add_argument("--repo", required=True,
                    help="the target repository to read")
    ap.add_argument("--path", default=DEFAULT_PATH,
                    help="ledger path inside the repo (default: %(default)s)")
    ap.add_argument("--json", action="store_true",
                    help="single-line JSON (default output is pretty-printed "
                         "JSON; both are machine-readable)")
    args = ap.parse_args(argv)
    try:
        result = task_origins(args.repo, args.path)
    except TaskOriginsError as exc:
        print(f"task_origins: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result))
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
