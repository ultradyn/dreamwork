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

The entry and marker grammar is IMPORTED from ledger_parse.py (#352 — the
one copy of the #213 contract that lint.py and watch.py also import; a
second copy of one rule is how the priority-marker check drifted,
3073055). Nothing here is re-derived.

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
      "history_complete": true,          // false on a shallow clone
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

import ledger_parse  # the #213 entry/marker grammar — imported, never re-copied  # noqa: E402
from ledger_parse import source_of_truth  # noqa: E402 — #294 inc 7 dispatch

DEFAULT_PATH = ".dreamwork/tasks.md"
GIT_TIMEOUT = 15


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

    The rule itself is ledger_parse.classify_origin (#352); the try/except
    is this walk's own promise that a malformed snapshot fails closed
    rather than crashing the history.
    """
    try:
        return ledger_parse.classify_origin(entry_text)
    except Exception:
        return "unknown"


def _title(entry_text: str) -> str:
    """The entry's first line minus its leading `- **#…**` token — enough
    context for a renderer (#217) without re-parsing the file."""
    first = entry_text.split("\n", 1)[0].strip()
    return ledger_parse.ENTRY_HEAD.sub("", first, count=1).lstrip(" —·").strip()


def _store_origins(dreamwork_dir):
    """First-seen origins from the store's task table (#294 inc 7).

    The post-cutover projection of the git-history walk: the store's
    ``task.origin`` column is the parsed origin (set once at import, never
    revisited — same first-sight semantics). The first-sight epoch and sha
    come from the earliest ``task_event`` row per task.
    """
    import sqlite3
    from datetime import datetime
    db = ledger_parse.store_path(dreamwork_dir)
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        task_rows = conn.execute(
            "SELECT id, origin FROM task ORDER BY id").fetchall()
        event_rows = conn.execute(
            "SELECT task_id, MIN(at), detail FROM task_event "
            "WHERE from_state IS NULL GROUP BY task_id").fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    # First-sight sha + epoch from the earliest event per task.
    import re
    first = {}
    for tid, at, detail in event_rows:
        sha = ""
        m = re.search(r"\(([0-9a-f]{7,40})\)", detail or "")
        if m:
            sha = m.group(1)
        try:
            epoch = int(datetime.fromisoformat(at).timestamp())
        except (ValueError, TypeError, OSError):
            epoch = 0
        first[int(tid)] = (sha, epoch)
    tasks = []
    for tid, origin in task_rows:
        sha, epoch = first.get(int(tid), ("", 0))
        tasks.append({"id": int(tid),
                      "origin": origin if origin in ("human", "loop") else "unknown",
                      "first_commit": sha, "first_seen": epoch,
                      "title": ""})
    return tasks


def task_origins(repo, path: str = DEFAULT_PATH) -> dict:
    """First-seen origin of every ledger id, oldest history first.

    Returns the JSON-serializable shape documented in the module docstring.
    Raises TaskOriginsError on a non-repo, an escaping path, or a git
    failure — and on nothing else.
    """
    repo = Path(repo).resolve()
    rel = _confine_path(path)

    # #294 inc 7: dispatch on source_of_truth. The store's task.origin is
    # the parsed first-sight origin (set once at import); the git walk stays
    # for pre-cutover. A missing store is fail-closed to markdown.
    dw_dir = str(repo / Path(path).parent)
    if source_of_truth(dw_dir) == "store":
        tasks = _store_origins(dw_dir)
        if tasks is not None:
            return {"repo": str(repo), "path": rel,
                    "history_complete": True, "history_note": None,
                    "tasks": tasks}

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

    # A shallow clone cannot see first sight for anything filed before its
    # boundary; say so instead of claiming full coverage.
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
            entries = ledger_parse.ledger_entries(text)
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
