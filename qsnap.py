#!/usr/bin/env python3
"""Out-of-band content snapshotter for `.dreamwork/questions.md` (#632).

WHY THIS EXISTS, AND WHY IT IS NOT PART OF THE WRITE PATH.

On 2026-07-31 a write rewrote `questions.md` from 63 answered entries to 51 —
the twelve OLDEST, contiguous, with no archive file written anywhere. Nothing
refused it and nothing said so; `git diff` was the only witness, and only
because a commit happened to sit twelve minutes earlier.

Git is not a sufficient net for the case that matters. The dangerous sequence
is: he types an answer, it lands, THEN the bug fires. Restoring from the last
commit at that point reverts *his answer* — it trades one loss for another.
The net has to preserve content he has never committed, which means it has to
observe the file itself rather than the repo.

FOUR PROPERTIES, EACH LOAD-BEARING.

· OUT OF PROCESS. It coordinates with the writer not at all — no lock, no
  import, no hook, and above all no restart of the running server. A guard
  that required the suspect process to cooperate could not have been armed
  while the suspect process was the thing we were still diagnosing.
· CONTENT-ADDRESSED. Snapshots are keyed by sha256 of the bytes, so an
  unchanged file costs nothing and a flapping file cannot fill the store with
  duplicates. It also makes a partial read harmless: it is simply one more
  distinct content, not a corruption of the record.
· IT NEVER REFUSES. It cannot: it is downstream of a write that already
  happened. That is the deliberate trade — a write-path assertion could block
  a legitimate fold (which genuinely does move entries between sections),
  whereas an observer that only ever preserves and reports has no false
  positive that costs anything. It SHOUTS instead of refusing.
· IT WRITES OUTSIDE THE REPO. The store lives under the user cache, so no
  snapshot ever appears in `git status` and no tracked file is touched.

The answered-entry count in the index is what turns a backup into a detector:
a DROP between two consecutive observed contents is exactly the #632
signature, and it is written to `alerts.log` the moment it is seen.
"""

import argparse
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

# A top-level `- **` bullet is an ENTRY; everything else is body. The parser
# in watch.py agrees, but this file deliberately does not import it: the
# snapshotter must keep running when watch.py is the thing that is broken, and
# a 266KB import with module-level state is not a dependency a net should have.
ENTRY_RE = re.compile(r"^- \*\*", re.MULTILINE)
ANSWERED_RE = re.compile(r"^## Answered\s*$", re.MULTILINE)

DEFAULT_STORE = os.path.expanduser("~/.cache/dreamwork/qsnap")


def answered_count(text):
    """Number of top-level entries below the `## Answered` heading.

    Returns 0 when there is no such heading, which is the honest reading of a
    file that has no answered section — not an error, and not a reason to
    refuse to snapshot. A file we cannot parse is still a file worth keeping.
    """
    m = ANSWERED_RE.search(text or "")
    if not m:
        return 0
    return len(ENTRY_RE.findall(text[m.end():]))


def open_count(text):
    """Entries above `## Answered` — the counterpart, for the fold case.

    A legitimate fold moves an entry from Open to Answered: answered goes UP
    and open goes DOWN. Recording both is what lets a reader tell that apart
    from a deletion, where answered goes down and open does not move.
    """
    m = ANSWERED_RE.search(text or "")
    head = text[:m.start()] if m else (text or "")
    return len(ENTRY_RE.findall(head))


def read_bytes(path):
    """File bytes, or None if it is absent or unreadable right now.

    None means "nothing to judge this tick" and the caller skips — the same
    discipline `_sources_mtime` uses in watch.py, and for the same reason: a
    rename window briefly unlinks the target, and treating that as "the file
    became empty" would record a phantom loss and cry wolf.
    """
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Store:
    """Content-addressed snapshot directory with an append-only index."""

    def __init__(self, root, keep=400, max_bytes=256 * 1024 * 1024):
        self.root = root
        self.snaps = os.path.join(root, "snaps")
        self.index = os.path.join(root, "index.log")
        self.alerts = os.path.join(root, "alerts.log")
        self.keep = keep
        self.max_bytes = max_bytes
        os.makedirs(self.snaps, exist_ok=True)

    def _append(self, path, line):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def record(self, data, sha, prev, why="poll", stable=True):
        """Persist one distinct content and return the index record.

        `prev` is the previous record (or None). The alert is raised HERE
        rather than by a separate scanner because the moment of observation is
        the only moment at which both contents are known to be adjacent — a
        later scan over the store cannot tell a missed intermediate state from
        a real jump.
        """
        text = data.decode("utf-8", "replace")
        rec = {
            "t": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "sha": sha[:16],
            "bytes": len(data),
            "answered": answered_count(text),
            "open": open_count(text),
            "why": why,
            "stable": stable,
        }
        name = f"{rec['t'].replace(':', '')}-{rec['sha'][:12]}.md.gz"
        blob = os.path.join(self.snaps, name)
        if not os.path.exists(blob):
            tmp = blob + ".tmp"
            with gzip.open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, blob)
        rec["file"] = name
        drop = None
        if prev is not None:
            drop = prev["answered"] - rec["answered"]
        if drop:
            rec["answered_delta"] = -drop
        self._append(self.index, _fmt(rec))
        # Only a DROP alerts, and only on a content we read stably. A fold
        # raises `answered`; a partial read can lower it spuriously, which is
        # what `stable` exists to filter — an alert nobody trusts is worse
        # than no alert, because the next real one gets ignored too.
        if drop and drop > 0 and stable:
            self._append(self.alerts, _fmt({
                "t": rec["t"],
                "ALERT": "answered-entry count DROPPED",
                "from": prev["answered"], "to": rec["answered"],
                "lost": drop,
                "open_from": prev["open"], "open_to": rec["open"],
                "prev_file": prev.get("file"), "file": name,
                "hint": ("a fold RAISES answered; a drop with open unchanged "
                         "is the #632 signature"),
            }))
        self.prune()
        return rec

    def prune(self):
        """Keep the newest `keep` snapshots and stay under `max_bytes`.

        Newest-first deletion is wrong for a safety net, so this deletes the
        OLDEST — the store's purpose is to make the recent past recoverable,
        and the recent past is what a cap must therefore protect.

        ORDERED BY MTIME, NOT BY NAME, and the test is what found that. Names
        carry a one-SECOND timestamp, so several snapshots taken inside the
        same second sort by the sha that follows it — which is to say, at
        random. The burst case is not hypothetical and is the worst one
        available: his answer landing and a damaging rewrite arriving in the
        same second is exactly the sequence this net exists for, and a
        name-sorted prune could have evicted the good copy of the pair.
        """
        try:
            entries = []
            for n in os.listdir(self.snaps):
                if not n.endswith(".md.gz"):
                    continue
                try:
                    entries.append((os.path.getmtime(os.path.join(self.snaps, n)), n))
                except OSError:
                    continue
        except OSError:
            return
        names = [n for _, n in sorted(entries)]
        doomed = names[:max(0, len(names) - self.keep)]
        kept = names[len(doomed):]
        total = 0
        for n in reversed(kept):
            try:
                total += os.path.getsize(os.path.join(self.snaps, n))
            except OSError:
                continue
            if total > self.max_bytes:
                doomed.append(n)
        for n in doomed:
            try:
                os.unlink(os.path.join(self.snaps, n))
            except OSError:
                pass


def _fmt(rec):
    import json
    return json.dumps(rec, ensure_ascii=False, sort_keys=True)


def _inotify(path):
    """Yield a wake per write to `path`, or return if inotify is unavailable.

    Watches the DIRECTORY, not the file: `atomic_write_text` replaces the
    target via `os.replace`, so an inode-level watch would follow the old
    inode into oblivion and see nothing ever again. `moved_to` is the event
    that atomic write produces; `close_write` catches an in-place editor.
    """
    directory = os.path.dirname(path) or "."
    base = os.path.basename(path)
    if not shutil.which("inotifywait"):
        return
    proc = subprocess.Popen(
        ["inotifywait", "-m", "-q", "-e", "close_write", "-e", "moved_to",
         "--format", "%f", directory],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        for line in proc.stdout:
            if line.strip() == base:
                yield "inotify"
    finally:
        proc.terminate()


def snapshot_once(path, store, state, why="poll", settle=0.20):
    """Observe the file once; record it if the content is new.

    Returns the record, or None when nothing changed. The double read is the
    `stable` determination: a writer doing a non-atomic in-place rewrite can
    be caught mid-flight, and a mid-flight read has a legitimately lower
    entry count. We still STORE it (it is real bytes that existed), we just
    decline to raise the alarm on it.
    """
    data = read_bytes(path)
    if data is None:
        return None
    sha = digest(data)
    if sha == state.get("sha"):
        return None
    time.sleep(settle)
    again = read_bytes(path)
    stable = again is not None and digest(again) == sha
    rec = store.record(data, sha, state.get("rec"), why=why, stable=stable)
    state["sha"] = sha
    state["rec"] = rec
    return rec


def run(path, store, interval=1.0, once=False, deadline=None):
    """Poll + inotify wake loop. The poll is the BACKSTOP, not the mechanism.

    inotify alone is not enough: it dies silently if the watch is dropped
    (directory replaced, limit exhausted), and this net has to keep working
    through exactly the kind of day where something unexpected is already
    happening. A 1s poll that costs one `stat` and one hash is a price worth
    paying to make the net's liveness independent of a subprocess.
    """
    state = {}
    snapshot_once(path, store, state, why="baseline")
    if once:
        return state
    import threading
    wake = threading.Event()

    def pump():
        for why in _inotify(path):
            state["why"] = why
            wake.set()

    threading.Thread(target=pump, daemon=True).start()
    while deadline is None or time.time() < deadline:
        wake.wait(timeout=interval)
        why = state.pop("why", "poll")
        wake.clear()
        snapshot_once(path, store, state, why=why)
    return state


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--file", required=True, help="file to snapshot")
    p.add_argument("--store", default=DEFAULT_STORE, help="snapshot dir")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--keep", type=int, default=400)
    p.add_argument("--max-mb", type=float, default=256.0)
    p.add_argument("--once", action="store_true",
                   help="take one baseline snapshot and exit")
    args = p.parse_args(argv)
    store = Store(args.store, keep=args.keep,
                  max_bytes=int(args.max_mb * 1024 * 1024))
    run(os.path.abspath(args.file), store, interval=args.interval,
        once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
