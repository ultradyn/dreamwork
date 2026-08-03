#!/usr/bin/env python3
"""rotate_inbox — archive older entries from .dreamwork/inbox.md (#1104).

Lanes die appending to inbox.md because the harness requires a Read before an
Edit, and the file grew to 3.77 MB / ~938K tokens. This tool moves older
entries to a dated archive so the live file stays small enough that a lane
can append its report without loading the whole history.

No code reads the contents of inbox.md (verified: lint.py, dev/brief.py,
dev/launch_lane.py, dev/dispatch_lane.py all treat it as a path string only;
file-formats.md:1063 states "append-only prose read by a language model").
So moving bytes to a sibling archive breaks no parser. The one real reader —
the coordinator LLM — reads via shell (tail/grep), and a pointer comment at
the top of the live file names the archive so older entries stay findable.

#1158: ``os.replace`` orphans the old inode, so an unlocked ``cat >>`` at that
instant writes to an unlinked file and loses its report. Rotation and the
standing append recipe now take the same advisory sidecar lock (#1170). The
live-lane refusal remains as a second transition condition until every writer
has adopted that recipe. Successful rotations also account for the observed
snapshot: entries-moved + entries-retained == entries-observed, and the live
file's first entry matches the pointer comment.

Usage:
    python3 dev/rotate_inbox.py status  --target <dreamwork-dir-or-repo>
    python3 dev/rotate_inbox.py rotate  --target <dreamwork-dir-or-repo> [--keep N]

Exit codes: 0 success (including "nothing to do" and "refused"), 1 argument/path
error, 2 I/O or reconciliation error.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HEADING_RE = re.compile(r"^## ", re.MULTILINE)
DEFAULT_KEEP = 50
ARCHIVE_DIR = "inbox-archive"


@contextmanager
def _inbox_lock(dw: Path):
    """Exclude appenders and rotation via ``inbox.md.lock``."""
    lock_path = dw / "inbox.md.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class ReconciliationError(RuntimeError):
    """A rotation could not account for every entry present at observation.

    Raised after the live file and archive have been written when
    moved + retained != observed, or when the live file's first entry does not
    match the heading the pointer comment claims. A rotation that cannot state
    the balance has not accounted for the observed snapshot. Locking appenders
    after observation wait until replacement and are outside this count.
    """


@dataclass(frozen=True)
class LaneProbeResult:
    """A completed fleet observation or a named failure to observe it."""

    live_lanes: int | None
    examined: int
    error: str | None = None

    @property
    def complete(self) -> bool:
        return self.error is None and self.live_lanes is not None


def _probe_failed(what: str, exc: BaseException) -> LaneProbeResult:
    return LaneProbeResult(None, 0, f"could not read {what}: {type(exc).__name__}: {exc}")


def _count_live_lanes(coordinator_root: Path) -> LaneProbeResult:
    """Count live lane runners via ``lane_liveness`` (cwd channel, #868/#1158).

    Reuses ``lane_liveness._is_lane_runner`` + ``_ancestor_pids`` +
    ``read_proc_cwd`` — NOT a fresh ``ps | grep`` (#868 trap: a coordinator once
    read ``ps | grep ccc`` returning nothing as a zero-lane fleet; a lane
    runner's command line does not contain ``ccc``). A runner is a process whose
    argv[0] basename is a known lane runner (claude/grok/codex/ccc) and whose
    cwd is inside a canonical worktree root; a lane's many descendants dedupe to
    one (by worktree directory). Self and ancestors are excluded (#729).

    The result type distinguishes an observed-empty fleet from an incomplete
    probe. A global import, root-resolution, ancestry, or ``/proc`` enumeration
    failure names the unreadable source so the caller can fail closed. Per-pid
    disappearance remains ordinary process-table churn and is skipped.
    """
    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        import lane_liveness  # noqa: E402  (repo root, lazy like dispatch_lane)
        from worktree_paths import worktree_roots  # noqa: E402
    except Exception as exc:
        return _probe_failed("lane-liveness dependencies", exc)
    try:
        roots = tuple(str(r) for r in worktree_roots(coordinator_root.resolve()))
    except Exception as exc:
        return _probe_failed("canonical worktree roots", exc)
    try:
        skip = lane_liveness._ancestor_pids()
    except Exception as exc:
        return _probe_failed("process ancestry", exc)
    examined = 0
    occupied: set[str] = set()
    try:
        entries = os.listdir("/proc")
    except OSError as exc:
        return _probe_failed("/proc directory", exc)
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in skip:
            continue
        examined += 1
        cwd = lane_liveness.read_proc_cwd(pid)
        if cwd is None or cwd.endswith(" (deleted)"):
            continue
        matched_root = next((r for r in roots if cwd == r or cwd.startswith(r + os.sep)), None)
        if matched_root is None:
            continue
        try:
            raw = Path("/proc/%d/cmdline" % pid).read_bytes()
        except OSError:
            continue
        if lane_liveness._is_lane_runner(raw):
            # Dedupe by worktree directory: the path component under the root.
            tail = cwd[len(matched_root):].lstrip(os.sep)
            lane_dir = tail.split(os.sep, 1)[0] if tail else "."
            occupied.add(matched_root + os.sep + lane_dir)
    return LaneProbeResult(len(occupied), examined)


def _test_observation_hook() -> None:
    """Synchronize the committed real-CLI race harness, when explicitly armed.

    The test passes inherited pipe descriptors. Production calls do nothing.
    This hook creates no new observation or retry; it only makes the known
    observation-to-rename window deterministic for #1170's acceptance harness.
    """
    ready = os.environ.get("ROTATE_INBOX_TEST_OBSERVED_FD")
    proceed = os.environ.get("ROTATE_INBOX_TEST_PROCEED_FD")
    if ready is None and proceed is None:
        return
    if ready is None or proceed is None:
        raise RuntimeError("both rotate-inbox test hook descriptors are required")
    os.write(int(ready), b"1")
    if os.read(int(proceed), 1) != b"1":
        raise RuntimeError("rotate-inbox test hook closed before proceed signal")


def _inbox_path(target: Path) -> Path:
    """Resolve the inbox path from a target that may be a repo root or .dreamwork."""
    target = target.resolve()
    if target.name == ".dreamwork":
        return target / "inbox.md"
    return target / ".dreamwork" / "inbox.md"


def _split_entries(text: str) -> tuple[str, list[str]]:
    """Split inbox text into (prologue, entries).

    The prologue is everything before the first ``## `` heading (old single-line
    /tmp-pointer era). Entries are the text from each ``## `` heading up to the
    next one (or EOF), each including its heading line and trailing newlines.
    """
    match = HEADING_RE.search(text)
    if not match:
        return text, []
    prologue = text[: match.start()]
    rest = text[match.start() :]
    # Split on heading starts, keeping the heading line with its body.
    parts = re.split(r"(?=^## )", rest, flags=re.MULTILINE)
    entries = [p for p in parts if p.startswith("## ")]
    return prologue, entries


def _count_headings(path: Path) -> int:
    """Count ``## `` headings in a file — the ONE counting rule (#1158).

    Used for every number in the reconciliation (archive-before, archive-after,
    live-after, observed): a different rule per side would balance by
    construction. Reads the file each call so a concurrent change is seen.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return len(HEADING_RE.findall(text))


def _first_heading(text: str) -> str:
    """The first ``## `` line of ``text`` (empty string if none)."""
    for line in text.splitlines():
        if line.startswith("## "):
            return line
    return ""


def _reconcile_balanced(observed: int, moved: int, retained: int) -> bool:
    """Whether moved + retained accounts for the observed snapshot.

    Pure so it can be tested directly: a rotation that lost an entry has
    moved + retained < observed, and this returns False. The single source of
    the balance verdict so a sabotage here reddens every snapshot-accounting
    test. Lock-serialized appends after observation are outside the inputs.
    """
    return moved + retained == observed


def _archive_path(dw: Path) -> Path:
    return dw / ARCHIVE_DIR / f"{date.today().strftime('%Y-%m')}.md"


def _pointer_line(archive_rel: str, n_moved: int, first_retained_heading: str) -> str:
    """The live file's pointer. Names the archive AND the entry it resumes at.

    The snapshot accounting verifies the live file's first ``## `` heading
    equals ``first_retained_heading``: a rotation that points at the wrong entry
    did not account for the observed snapshot even if the counts balance.
    """
    return (
        f"<!-- inbox-archive: {archive_rel} — {n_moved} older entries rotated; "
        f'live resumes at "{first_retained_heading}" '
        f"(#1104/#1158) -->\n"
    )


def rotate(dw: Path, keep: int = DEFAULT_KEEP, *, live_lane_probe=None) -> dict:
    """Rotate while holding the lock shared with the standing append recipe."""
    with _inbox_lock(dw):
        return _rotate_locked(dw, keep=keep, live_lane_probe=live_lane_probe)


def _rotate_locked(dw: Path, keep: int = DEFAULT_KEEP, *, live_lane_probe=None) -> dict:
    """Rotate older entries from inbox.md to a dated archive.

    Returns a dict whose ``action`` is one of three distinct states (#136):

    - ``'rotated'`` — entries moved; the live file now holds the recent tail.
    - ``'noop'`` — fewer entries than ``keep``; nothing to do.
    - ``'refused'`` — a live lane was detected during lock migration.

    ``live_lane_probe`` is an optional zero-arg callable returning a
    :class:`LaneProbeResult`. When it reports live lanes, rotation is REFUSED
    during the transition because already-dispatched writers may still hold the
    old unlocked recipe. The CLI wires the real detector
    (:func:`_count_live_lanes`, which reuses ``lane_liveness``); tests inject
    explicit complete or failed results. An incomplete probe also refuses and
    names what could not be read.

    Every line present at observation time is accounted for in archive + live.
    Locking appenders run after rotation and remain in the new live file. The
    live file is written atomically (temp + fsync + os.replace). On a successful
    rotation snapshot accounting is returned: ``entries_moved`` +
    ``entries_kept`` must equal ``entries_total`` (the count observed before
    rotating), and the live file's first entry must match the heading the
    pointer comment claims; a mismatch raises :class:`ReconciliationError`.
    """
    inbox = dw / "inbox.md"
    if not inbox.is_file():
        return {"action": "noop", "reason": "inbox.md absent"}

    text = inbox.read_text(encoding="utf-8", errors="replace")
    prologue, entries = _split_entries(text)
    if len(entries) <= keep:
        # Nothing to do — checked BEFORE the live-lane refusal so that a live
        # lane does not turn "nothing to rotate" into "refused" (#136: the two
        # states must not collapse; the distinction is "was there work").
        return {
            "action": "noop",
            "reason": f"{len(entries)} entries <= keep={keep}",
            "entries_total": len(entries),
        }

    # Keep the #1158 refusal during migration: a live lane may have received the
    # old unlocked recipe before #1170's standing rule reached it.
    if live_lane_probe is not None:
        try:
            probe = live_lane_probe()
        except Exception as exc:
            probe = _probe_failed("live-lane probe callback", exc)
        if not isinstance(probe, LaneProbeResult):
            probe = LaneProbeResult(
                None,
                0,
                "could not read live-lane probe result: expected "
                f"LaneProbeResult, got {type(probe).__name__}",
            )
        if not probe.complete:
            return {
                "action": "refused",
                "reason": f"live-lane probe incomplete: {probe.error}; rotation not performed",
                "probe_error": probe.error,
            }
        n_live = probe.live_lanes
        if n_live:
            return {
                "action": "refused",
                "reason": f"{n_live} live lane(s) — deferring to avoid orphaning an in-flight appender (#1158)",
                "live_lanes": n_live,
            }

    split_at = len(entries) - keep
    to_archive = entries[:split_at]
    to_keep = entries[split_at:]
    observed = len(entries)  # the count immediately before rotating (#868)

    # The first retained entry's heading — the pointer claims it and the
    # reconciliation verifies it (#1158).
    first_retained_heading = to_keep[0].splitlines()[0] if to_keep else ""

    # The prologue (pre-heading era) goes to the archive too — it is old.
    archive_text = prologue + "".join(to_archive)
    if not archive_text.endswith("\n"):
        archive_text += "\n"

    archive = _archive_path(dw)
    archive.parent.mkdir(parents=True, exist_ok=True)

    # Counting rule for the reconciliation: ONE rule (^## headings) for every
    # number (#1158 trap: a different rule per side balances by construction).
    # The archive accumulates across rotations in the same month, so the
    # entries MOVED this rotation = archive_after - archive_before.
    archive_before = _count_headings(archive) if archive.exists() else 0

    # Append to the archive if it already exists (multiple rotations same month).
    if archive.exists():
        existing = archive.read_text(encoding="utf-8", errors="replace")
        if not existing.endswith("\n"):
            existing += "\n"
        archive.write_text(existing + "\n" + archive_text, encoding="utf-8")
    else:
        archive.write_text(archive_text, encoding="utf-8")

    archive_rel = f"{ARCHIVE_DIR}/{archive.name}"
    pointer = _pointer_line(archive_rel, len(to_archive), first_retained_heading)
    live_text = pointer + "".join(to_keep)

    # Atomic write of the live file.
    inbox.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(inbox.parent), prefix=".inbox.md.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(live_text)
            f.flush()
            os.fsync(f.fileno())
        _test_observation_hook()
        os.replace(tmp, str(inbox))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    # Account for the snapshot observed before the rename. Locking appenders
    # resume only after replacement, so they remain in the new live file.
    moved = _count_headings(archive) - archive_before
    retained = _count_headings(inbox)
    live_first = _first_heading(inbox.read_text(encoding="utf-8", errors="replace"))
    balanced = _reconcile_balanced(observed, moved, retained)
    claimed_matches = (live_first == first_retained_heading) if first_retained_heading else True
    result = {
        "action": "rotated",
        "entries_total": observed,
        "entries_kept": retained,
        "entries_moved": moved,
        "reconciled": balanced and claimed_matches,
        "reconcile_observed": observed,
        "reconcile_moved": moved,
        "reconcile_retained": retained,
        "reconcile_first_matches": claimed_matches,
        "bytes_before": len(text.encode("utf-8")),
        "bytes_after": len(live_text.encode("utf-8")),
        "archive_path": str(archive),
    }
    if not balanced or not claimed_matches:
        why = "unbalanced" if not balanced else "first-entry mismatch"
        raise ReconciliationError(
            f"rotation {why}: moved={moved} + retained={retained} "
            f"!= observed={observed}" if not balanced
            else f"rotation first-entry mismatch: pointer claims "
            f"{first_retained_heading!r}, live starts at {live_first!r}"
        )
    return result


def status(dw: Path) -> dict:
    """Report inbox.md size and entry count without modifying anything."""
    inbox = dw / "inbox.md"
    if not inbox.is_file():
        return {"exists": False}
    text = inbox.read_text(encoding="utf-8", errors="replace")
    _, entries = _split_entries(text)
    return {
        "exists": True,
        "bytes": len(text.encode("utf-8")),
        "entries": len(entries),
        "path": str(inbox),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "verb", choices=["status", "rotate"], help="status: report; rotate: archive"
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="repo root or .dreamwork directory",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"entries to keep in the live file (default {DEFAULT_KEEP})",
    )
    args = parser.parse_args(argv)

    inbox = _inbox_path(args.target)
    dw = inbox.parent

    if args.verb == "status":
        info = status(dw)
        if not info.get("exists"):
            print(f"inbox.md absent at {dw}")
            return 0
        print(
            f"inbox.md: {info['bytes']} bytes ({info['bytes'] // 1024}KB), "
            f"{info['entries']} entries — {info['path']}"
        )
        return 0

    if args.verb == "rotate":
        # Wire the live-lane detector at the CLI boundary (#1158). Programmatic
        # callers / tests inject ``live_lane_probe`` directly; the guard is a
        # property of how the coordinator invokes the tool.
        coordinator_root = dw.parent
        try:
            result = rotate(
                dw,
                keep=args.keep,
                live_lane_probe=lambda: _count_live_lanes(coordinator_root),
            )
        except ReconciliationError as exc:
            print(f"error: reconciliation failed: {exc}", file=sys.stderr)
            return 2
        action = result.get("action")
        if action == "noop":
            print(f"noop: {result.get('reason', 'nothing to do')}")
            return 0
        if action == "refused":
            # Distinct from noop (#136): there was work, but a live lane made it
            # unsafe. Exit 0 so the coordinator's cadence loop is not alarmed,
            # but the message names the refusal and the count.
            print(f"refused: {result.get('reason', 'live lane detected')} (#1158)")
            return 0
        print(
            f"rotated: {result['entries_moved']} entries -> "
            f"{result['archive_path']}; live file {result['entries_kept']} entries, "
            f"{result['bytes_before']} -> {result['bytes_after']} bytes; "
            f"lock held; locking appenders resume after replacement; "
            f"observed-snapshot accounted: moved={result['reconcile_moved']} + retained="
            f"{result['reconcile_retained']} = observed="
            f"{result['reconcile_observed']}"
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
