#!/usr/bin/env python3
"""session_source.py — resolve the running agent's LIVE transcript (#698).

`#665` built the `agent_session` seam: the main agent records
`{client, session_id, …}` into `status.json` at orient. A consumer that needs
the main agent's own transcript — `#691`'s recap, `#613`'s session-log view —
cannot derive that transcript's path from the target directory, because **the
session relocates**. The CLI keys transcripts by the cwd's slug
(`$CLAUDE_CONFIG_DIR/projects/<cwd-slug>/<session-uuid>.jsonl`), and the live
session writes `type: "relocated"` records whose `relocatedCwd` is a *worktree*
— so the transcript sits under a worktree slug the loop does not control and
cannot derive. Deriving instead from the target directory finds a *different,
stale* directory whose newest file is days old, and a consumer that reads it is
fluent and wrong (`#136` waiting to happen).

This module is the seam a consumer uses INSTEAD of deriving. Given the recorded
`session_id`, it finds the transcript **by uuid across every slug** (the slug is
not derivable, so it is searched), reads the last record's timestamp, and
reports one of five data-distinguishable states. It never guesses: an
unresolved state carries a `detail` that names *which* nothing it was, because
"the key is absent" and "the key names a file last written two days ago" are
different findings and must not read the same (`#136`).

WHY UUID-SEARCH, NOT DERIVATION. The session id is a self-reported truth
(`#665`, read from the one process entitled to read it); resolving a KNOWN id
to its file is a deterministic lookup, not the "newest live-mtime jsonl"
inference `#665` rejected. Inference is ambiguous the moment two sessions run;
a uuid names exactly one file wherever the session relocated it.

THE SYMLINK TRAP (`#698`, measured by `#691`). `$CLAUDE_CONFIG_DIR/projects` is
a symlink to `~/.claude-shared/projects`, and `find` WITHOUT `-L` silently
returns **nothing** against it while `ls` works — `#691` reached a wrong
conclusion on this before catching it. This module uses `pathlib.Path.glob`,
which follows the symlinked base directory (verified: `glob` finds the file
where bare `find` returns nothing), so the trap cannot recur here.

LIVENESS, NOT PRESENCE. A recorded id that resolves to a file is not enough:
`#693`'s allowlist lesson is that a value can be *set, non-empty, and exactly
wrong*, so a presence check is not a correctness check. The transcript the id
resolves to may itself be a dead session's — orient wrote the id, the session
moved, orient has not re-run — so the last record's age is checked and a stale
finding names the age rather than reading as success. `expected_session_id`
(the live process's own id, when the caller has it) is the stronger check: a
recorded id that differs from the process reading it is wrong *however fresh*
its transcript is, and that is the one case data alone cannot catch.

SCOPE. This resolves the source. It does not parse, project, digest, or model
anything — that is `#691`'s job, and it imports this.

Usage:  python3 session_source.py --target .            # resolve and print
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# `#665`'s seam owns this key; this module only READS it. Reusing the shared
# refusal reader binds this consumer to the one status.json read contract
# (#655: a hand-rolled reader passed every test its author wrote) and refuses
# rather than crashes on a file that cannot be parsed (#402).
from status_sync import _read_status

# The loop's heartbeat (`initialization.md` step 5): 4.75 min. A transcript is
# treated as stale once its last record is older than three beats — the one
# measured liveness threshold in the repo (`#691` §3.2). A consumer with a
# different model passes its own `stale_after`.
BEAT_SECONDS = 285
DEFAULT_STALE_AFTER = BEAT_SECONDS * 3

# `#691` §6: transcript records carry an ISO8601 UTC `timestamp` ending in `Z`,
# while the loop's own files are local. Every comparison here is in UTC.
STATUS_KEY = "agent_session"


@dataclass
class ResolveResult:
    """One resolution attempt. `detail` always names the finding.

    Five states, distinguishable from the data alone (`#136`: distinct
    nothings must not read the same):

      live       — found by uuid, and its last record is within `stale_after`.
      stale      — found by uuid, but the last record is older; `detail` names
                   the age. This is the dangerous one: the id resolved, the
                   file exists, and a presence check would call it success.
      absent     — no `agent_session.session_id` to resolve (the `#698` state
                   today: orient has not re-run since `#665` landed).
      missing    — an id is recorded but no `<id>.jsonl` exists under any slug.
      mismatch   — `expected_session_id` was given and differs from the
                   recorded id: the recorded transcript is not THIS process's,
                   however fresh. The one case the data alone cannot catch.
    """

    status: str
    detail: str
    path: Path | None = None
    session_id: str | None = None
    last_record_at: datetime | None = None
    age_seconds: float | None = None

    @property
    def ok(self) -> bool:
        """True only for `live` — the one state a consumer may read from."""
        return self.status == "live"


def _default_projects_root() -> Path | None:
    """The client's transcript root. For claude-code, `$CLAUDE_CONFIG_DIR/projects`.

    Returns None rather than guessing a config dir, because the wrong root is a
    silent wrong answer and `CLAUDE_CONFIG_DIR` is the only measured source.
    """
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if not cfg:
        return None
    return Path(cfg) / "projects"


def _find_transcript(session_id: str, projects_root: Path) -> list[Path]:
    """Every `<session_id>.jsonl` under any slug of `projects_root`.

    Searches across slugs because the slug is not derivable (the session
    relocates). `Path.glob` follows a symlinked `projects_root` base — the
    `find`-without-`-L` trap does not apply (`#698`).
    """
    return sorted(projects_root.glob(f"*/{session_id}.jsonl"))


def _last_timestamp(path: Path) -> datetime | None:
    """The newest `timestamp` field in the transcript, in UTC.

    Reads a bounded tail rather than the whole file: a transcript is append-only
    (`#613` verified) and grows without bound, but the last record is what liveness
    asks for. A record mid-write (a partial final line) is skipped; records
    without a `timestamp` (e.g. `type: "relocated"`) are scanned past.
    """
    size = path.stat().st_size
    chunk = min(size, 1 << 21)  # 2 MiB tail — ample for many recent records
    with open(path, "rb") as f:
        f.seek(size - chunk)
        data = f.read(chunk)
    # Drop a leading partial line; it is decoded by the loop below only if whole.
    for raw in reversed(data.splitlines()):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            continue  # a partial final write, or a non-JSON line
        ts = rec.get("timestamp")
        if isinstance(ts, str) and ts:
            return _parse_utc(ts)
    return None


def _parse_utc(ts: str) -> datetime | None:
    """Parse an ISO8601 timestamp (trailing `Z` or offset) to aware UTC."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def resolve(session_id, projects_root, *, now=None, expected_session_id=None,
            stale_after=DEFAULT_STALE_AFTER) -> ResolveResult:
    """Resolve a recorded `session_id` to its transcript and a liveness verdict.

    `session_id` may be None (absent seam). `projects_root` is the client's
    `$CLAUDE_CONFIG_DIR/projects`. `expected_session_id`, when the caller knows
    the live process's own id, enables the mismatch check — the only detection
    of a live-but-wrong transcript. All five states are returned, never raised.
    """
    now = now if now is not None else datetime.now(timezone.utc)

    if not session_id:
        detail = ("no agent_session.session_id recorded — the #665 seam is "
                  "empty (orient has not re-run since it landed)")
        if expected_session_id:
            detail += ("; the running process is %s" % expected_session_id)
        return ResolveResult(status="absent", detail=detail,
                             session_id=session_id)

    if expected_session_id and session_id != expected_session_id:
        return ResolveResult(
            status="mismatch",
            detail=("recorded session %s differs from the running process's "
                    "%s — the recorded transcript is not this process's, "
                    "however fresh" % (session_id, expected_session_id)),
            session_id=session_id)

    if projects_root is None or not Path(projects_root).is_dir():
        return ResolveResult(
            status="missing",
            detail=("no projects root to search (CLAUDE_CONFIG_DIR unset) for "
                    "session %s" % session_id),
            session_id=session_id)

    found = _find_transcript(session_id, Path(projects_root))
    if not found:
        return ResolveResult(
            status="missing",
            detail=("no <session_id>.jsonl under any slug of %s for session "
                    "%s — the slug is not derivable and the uuid was not found"
                    % (projects_root, session_id)),
            session_id=session_id)
    if len(found) > 1:
        return ResolveResult(
            status="missing",
            detail=("ambiguous: session %s matches transcripts under %d slugs "
                    "(%s); cannot pick one"
                    % (session_id, len(found),
                       ", ".join(p.parent.name for p in found))),
            session_id=session_id)

    path = found[0]
    last = _last_timestamp(path)
    if last is None:
        return ResolveResult(
            status="stale",
            detail=("transcript %s has no timestamped record in its tail — "
                    "treating as not-live" % path),
            path=path, session_id=session_id)
    age = (now - last).total_seconds()
    if age > stale_after:
        return ResolveResult(
            status="stale",
            detail=("transcript %s last written %s (%.0f min ago, older than "
                    "the %.0f-min liveness window) — this is a DEAD session's "
                    "file, not the live one"
                    % (path, last.isoformat(), age / 60, stale_after / 60)),
            path=path, session_id=session_id, last_record_at=last,
            age_seconds=age)
    return ResolveResult(
        status="live",
        detail=("live transcript %s (last record %s, %.0f min ago)"
                % (path, last.isoformat(), age / 60)),
        path=path, session_id=session_id, last_record_at=last, age_seconds=age)


def session_id_from_status(target) -> str | None:
    """The recorded `agent_session.session_id`, or None if the seam is empty.

    Reads through `status_sync._read_status` so a torn `status.json` is refused
    rather than crashed on (#402/#655). None covers three cases the consumer
    cannot tell apart from here and should not need to: no key, a key whose
    `session_id` is null (a known client with no id var), and an unreadable
    file — `resolve()` names the first; the others surface as `absent` too.
    """
    spath = Path(target) / ".dreamwork" / "status.json"
    if not spath.exists():
        return None
    status, _why = _read_status(spath)
    if status is None:
        return None
    rec = status.get(STATUS_KEY) or {}
    sid = rec.get("session_id")
    return sid.strip() if isinstance(sid, str) and sid.strip() else None


def resolve_target(target, *, now=None, projects_root=None,
                    expected_session_id=None,
                    stale_after=DEFAULT_STALE_AFTER) -> ResolveResult:
    """Read the recorded id from `<target>/.dreamwork/status.json` and resolve it."""
    if projects_root is None:
        projects_root = _default_projects_root()
    return resolve(session_id_from_status(target), projects_root,
                   now=now, expected_session_id=expected_session_id,
                   stale_after=stale_after)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Resolve the running agent's live transcript from the "
                    "agent_session seam (#698).")
    ap.add_argument("--target", default=".", help="target project directory")
    ap.add_argument("--projects-root", default=None,
                    help="client projects root (default $CLAUDE_CONFIG_DIR/projects)")
    ap.add_argument("--expected", default=None,
                    help="the running process's own session id, for the "
                         "mismatch check (default: none)")
    args = ap.parse_args(argv)
    root = Path(args.projects_root) if args.projects_root else _default_projects_root()
    res = resolve_target(args.target, projects_root=root,
                         expected_session_id=args.expected)
    print(res.status)
    print(res.detail)
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
