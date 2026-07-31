#!/usr/bin/env python3
"""Red-proof injection registry + hand-off gate (#683).

The loop mandates direction-1 red-proofing for every lane: inject a defect,
watch the discriminating red, restore by ``cp`` from a lane-private snapshot,
verify with ``cmp``. **Nothing verifies the restore actually happened** before
the lane commits and hands off. A lane that injects, gets distracted writing
its report, and commits has shipped the deliberate defect with a green-looking
report attached — because the report describes the restore the lane *believes*
it did. The failure is silent and lands in master (#349 is the near-miss that
proves the exposure is real).

This tool turns the discipline into a check. It owns BOTH halves so the
snapshot is taken at registration time as ONE act (the #704 fix): the lane
cannot snapshot two files together and then lose later edits to the second,
because the tool snapshots each file individually at ``begin`` time, and
``restore`` reads the injected state straight from the working tree rather
than from a lane-chosen moment.

THE CHECK IS NOT "THE FILE MATCHES ITS SNAPSHOT"
------------------------------------------------
A lane's real fix very often touches the same file it injected into, so
"identical to the original snapshot" would refuse every correct hand-off. The
check is **"no registered injection is still present in the working tree"**:
``restore`` records the *injected* bytes (as a sha + a one-line hint), and at
hand-off ``check`` refuses if the working tree still matches that injected
state. A file that was restored (to the original, or edited further by the
real fix) differs from the recorded injection and passes; a file that was
never restored matches and is refused.

THE PROTOCOL
------------
Replace the manual ``cp`` snapshot / ``cp`` restore with the tool's verbs::

    python3 dev/redproof.py begin router.js      # snapshot ORIGINAL (one act)
    # ...sabotage router.js; run the red test; watch it fail...
    python3 dev/redproof.py restore router.js    # record INJECTED, restore, cmp
    # ...apply the real fix (may edit router.js further)...
    python3 dev/redproof.py check                # hand-off gate

``begin`` snapshots the original to the lane-private scratch dir (#652, never
``/tmp``). ``restore`` reads the *current* (injected) bytes, records their sha
and the first line that differs from the original, then copies the original
back and verifies byte-identity — never ``git checkout`` (#349). ``check``
refuses the hand-off if any registered file still matches its recorded
injection, naming the path and the injected content so the refusal has a
referent.

THREE ZERO-STATES, NOT ONE (#136)
---------------------------------
- No registry file at all → **calm zero**: "no injections registered". A lane
  that never used the tool is not faulty; the tool is opt-in (#683 point 3).
- Registry present but unparseable → **FAULT** (exit 2): a broken channel must
  not read as a calm zero.
- Registry present and empty → **calm zero**: the discipline ran and nothing
  is live.

FAIL CLOSED (#671)
------------------
A check that cannot evaluate its inputs must not read as passing. A missing
snapshot for a registered entry, an unreadable working-tree file, or an
unparseable registry are all FAULT (exit 2), never a silent pass.

WHAT IT CANNOT CATCH (direction 2)
----------------------------------
A lane that never calls ``begin`` is invisible to the tool (point 3). The
check is opt-in by design: it cannot detect an injection it was never told
about, and requiring ≥1 registration would refuse a genuinely clean hand-off
that simply had no red-proof step. The byte-sha check also passes if a lane
restores and then re-applies a *different* sabotage than the one recorded —
see the report's direction-2 section. Both are named, not hidden.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

# lane_scratch.py lives in dev/ next to this file; when run as
# `python3 dev/redproof.py`, dev/ is sys.path[0] so this import resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane_scratch as _ls  # noqa: E402

# Testability hook: an explicit override for the scratch root lets a CLI
# subprocess (which cannot see an in-process monkeypatch) land its registry in
# an isolated dir. Unset in production; the derived lane-private path is used.
_env_root = os.environ.get("REDPROOF_SCRATCH_ROOT")
if _env_root:
    _ls.SCRATCH_ROOT = Path(_env_root)

# Subdirectory under the lane-private scratch root for snapshots + registry.
SUB = "redproof"

# Registry entry states.
ARMED = "armed"        # begun (original snapshotted), not yet restored
RESTORED = "restored"  # restore ran; injected_sha recorded


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _to_posix(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _snap_dir(cwd: Path | None) -> Path:
    return _ls.lane_scratch_dir(cwd, sub=SUB)


def _registry_path(cwd: Path | None) -> Path:
    return _snap_dir(cwd) / "registry.json"


def _snapshot_path(cwd: Path | None, posix_path: str) -> Path:
    # One safe filename per registered path: collisions would let one entry's
    # restore clobber another's original, the exact failure snapshots prevent.
    return _snap_dir(cwd) / (hashlib.sha1(posix_path.encode()).hexdigest() + ".orig")


class RedproofError(Exception):
    """A fault the tool cannot evaluate — callers print and exit 2 (#671)."""


def _read_registry(cwd: Path | None) -> tuple[list[dict], str]:
    """Return (entries, source_label). Distinguishes the three zero-states.

    source_label is one of:
      "absent"   — no registry file (calm zero; the tool was never used)
      "empty"    — registry parsed to [] (calm zero; nothing live)
      "present"  — registry held ≥1 entry
    A present-but-unparseable registry raises RedproofError (#136 fault).
    """
    rp = _registry_path(cwd)
    if not rp.exists():
        return [], "absent"
    try:
        text = rp.read_text(encoding="utf-8")
    except OSError as exc:
        raise RedproofError(f"registry exists but is unreadable: {rp} ({exc})") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RedproofError(
            f"registry is present but unparseable — a broken channel must not "
            f"read as a calm zero (#136): {rp} ({exc.msg!r} near pos {exc.pos})"
        ) from exc
    if not isinstance(data, list):
        raise RedproofError(f"registry root is {type(data).__name__}, not a list: {rp}")
    if not data:
        return [], "empty"
    return data, "present"


def _write_registry(cwd: Path | None, entries: list[dict]) -> None:
    rp = _registry_path(cwd)
    rp.parent.mkdir(parents=True, exist_ok=True)
    tmp = rp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(rp)


def _find(entries: list[dict], posix_path: str) -> dict | None:
    for e in entries:
        if e.get("path") == posix_path:
            return e
    return None


def _read_wt(root: Path, posix_path: str) -> bytes:
    """Working-tree bytes of posix_path under root. Faults if unreadable."""
    p = root / posix_path
    try:
        return p.read_bytes()
    except FileNotFoundError as exc:
        # A registered file that no longer exists is a fault, not calm: the
        # entry's injection cannot be evaluated. (#671)
        raise RedproofError(
            f"registered path {posix_path!r} is absent from the working tree — "
            f"cannot evaluate its injection; refusing rather than guessing"
        ) from exc
    except OSError as exc:
        raise RedproofError(f"could not read {p}: {exc}") from exc


def _first_changed_line(original: bytes, injected: bytes) -> str:
    """The first line that differs between original and injected.

    A concrete referent for the refusal message: 'still matches its recorded
    injection' names a sha, but a one-line hint lets a reader recognise the
    sabotage without re-deriving it. Falls back to a length note if no line
    boundary differs (pure byte edits inside one line).
    """
    import difflib
    a = original.decode("utf-8", "replace").splitlines()
    b = injected.decode("utf-8", "replace").splitlines()
    for i in range(max(len(a), len(b))):
        la = a[i] if i < len(a) else "<missing>"
        lb = b[i] if i < len(b) else "<added>"
        if la != lb:
            return lb.strip()[:120]
    return f"(no line differs; {len(injected)} bytes vs {len(original)})"


# --------------------------------------------------------------------------- #
# verbs                                                                        #
# --------------------------------------------------------------------------- #

def begin(cwd: Path | None, path: str) -> int:
    """Snapshot the ORIGINAL bytes of ``path`` and register an armed entry.

    Called BEFORE the sabotage. The snapshot and the registration are one act,
    so the lane cannot take the snapshot at the wrong moment (#704).
    """
    root = _ls.worktree_root(cwd)
    posix = _to_posix(path)
    try:
        original = (root / posix).read_bytes()
    except FileNotFoundError:
        sys.stderr.write(f"begin: {posix!r} does not exist in the working tree\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"begin: cannot read {posix}: {exc}\n")
        return 2

    entries, _ = _read_registry(cwd)
    snap = _snapshot_path(cwd, posix)
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes(original)
    entry = _find(entries, posix)
    if entry is None:
        entry = {"path": posix}
        entries.append(entry)
    entry.update({
        "original_sha": _sha(original),
        "snapshot": str(snap),
        "state": ARMED,
        "begun_at": _now(),
        # cleared until restore records them:
        "injected_sha": None,
        "injected_hint": None,
        "restored_at": None,
    })
    _write_registry(cwd, entries)
    print(f"begin: snapshotted original of {posix} ({len(original)} bytes) -> {snap}")
    print(f"       state=armed; sabotage it, then `restore {posix}`.")
    return 0


def restore(cwd: Path | None, path: str) -> int:
    """Record the INJECTED state, restore the ORIGINAL, verify byte-identity.

    Called AFTER the sabotage (and the red test). Reads the current (injected)
    bytes — the one moment both states exist — records their sha + a one-line
    hint, then copies the original back from the lane-private snapshot and
    verifies with a byte compare. Never ``git checkout`` (#349).
    """
    root = _ls.worktree_root(cwd)
    posix = _to_posix(path)
    try:
        entries, _ = _read_registry(cwd)
        entry = _find(entries, posix)
        if entry is None:
            sys.stderr.write(
                f"restore: {posix!r} was never `begin`-ed — nothing to restore. "
                f"(No injection is registered for it.)\n")
            return 2
        if entry.get("state") == RESTORED:
            sys.stderr.write(f"restore: {posix!r} is already restored.\n")
            return 1
        snap = Path(entry["snapshot"])
        if not snap.exists():
            raise RedproofError(
                f"original snapshot for {posix!r} is missing ({snap}) — cannot "
                f"restore; refusing rather than guessing (#671/#349)")
        try:
            original = snap.read_bytes()
        except OSError as exc:
            raise RedproofError(f"snapshot {snap} unreadable: {exc}") from exc

        injected = _read_wt(root, posix)

        if _sha(injected) == _sha(original):
            # begin was called but the file was never changed: no injection to
            # record. Drop the entry so check's byte-test never fires on a no-op.
            entries = [e for e in entries if e.get("path") != posix]
            _write_registry(cwd, entries)
            print(f"restore: {posix!r} unchanged since begin — no injection recorded; "
                  f"entry dropped.")
            return 0

        entry["injected_sha"] = _sha(injected)
        entry["injected_hint"] = _first_changed_line(original, injected)
        entry["state"] = RESTORED
        entry["restored_at"] = _now()

        # Restore the original by cp, then verify byte-identity. Never git checkout.
        out = root / posix
        shutil.copyfile(str(snap), str(out))
        restored = out.read_bytes()
        if restored != original:
            raise RedproofError(
                f"restore of {posix!r} did not reproduce the snapshot byte-for-byte "
                f"after cp — investigate before continuing")
        _write_registry(cwd, entries)
    except RedproofError as exc:
        sys.stderr.write(f"restore: FAULT — {exc}\n")
        return 2
    print(f"restore: {posix!r} injected state recorded (sha {entry['injected_sha'][:12]}, "
          f"hint: {entry['injected_hint']!r}); original restored & verified.")
    return 0


def forget(cwd: Path | None, path: str) -> int:
    """Drop a registered entry (e.g. a spurious begin). Does not touch the WT."""
    posix = _to_posix(path)
    entries, _ = _read_registry(cwd)
    before = len(entries)
    entries = [e for e in entries if e.get("path") != posix]
    if len(entries) == before:
        sys.stderr.write(f"forget: nothing registered for {posix!r}\n")
        return 1
    _write_registry(cwd, entries)
    print(f"forget: dropped entry for {posix!r} (working tree untouched)")
    return 0


def check(cwd: Path | None, *, require: int = 0) -> int:
    """Hand-off gate: refuse if any registered injection is still present.

    Exit 0 = clean hand-off (or calm zero: no injections registered).
    Exit 1 = REFUSAL: a registered injection is still live in the working tree.
    Exit 2 = FAULT: could not evaluate (#671/#136).

    The discriminating test: for every restored entry, the working tree must
    NOT equal the recorded injected bytes. A restored-then-further-edited file
    differs from the injection and passes (#683 point 1). An armed (begun but
    unrestored) entry is a refusal: the red-proof is incomplete.
    """
    root = _ls.worktree_root(cwd)
    try:
        entries, source = _read_registry(cwd)
    except RedproofError as exc:
        sys.stderr.write(f"check: FAULT — {exc}\n")
        return 2

    if not entries:
        # Calm zero. "absent" (never used) and "empty" (ran, nothing live) are
        # both calm; an unparseable registry already raised before we got here.
        label = "no injections registered" if source == "absent" else "registry empty"
        if require > 0:
            sys.stderr.write(
                f"check: REFUSED — {label}, but --require {require} was set. "
                f"A hand-off that the brief mandated red-proofing must show at "
                f"least one registered injection.\n")
            return 1
        print(f"check: calm — {label} (opt-in discipline; nothing to evaluate).")
        return 0

    armed: list[dict] = []
    live: list[dict] = []
    for e in entries:
        if e.get("state") != RESTORED:
            armed.append(e)
            continue
        try:
            wt = _read_wt(root, e["path"])
        except RedproofError as exc:
            sys.stderr.write(f"check: FAULT — {exc}\n")
            return 2
        if _sha(wt) == e.get("injected_sha"):
            live.append(e)

    if require > 0 and len(entries) < require:
        sys.stderr.write(
            f"check: REFUSED — {len(entries)} injection(s) registered, but "
            f"--require {require} was set.\n")
        return 1

    if armed:
        names = ", ".join(e["path"] for e in armed)
        sys.stderr.write(
            f"check: REFUSED — {len(armed)} begun-but-unrestored injection(s): "
            f"{names}. An armed entry means the red-proof never completed "
            f"(begin without restore). Run `restore` on each or `forget` a "
            f"spurious begin.\n")
        return 1
    if live:
        lines = []
        for e in live:
            lines.append(
                f"  {e['path']}: working tree STILL MATCHES its recorded "
                f"injection (sha {e.get('injected_sha', '?')[:12]}, "
                f"hint: {e.get('injected_hint', '?')!r}). The restore that the "
                f"report describes did not take — #683.")
        sys.stderr.write(
            "check: REFUSED — hand-off blocked. A registered injection is "
            "still present in the working tree:\n" + "\n".join(lines) +
            "\nRestore it (cp from the lane-private snapshot) before committing.\n")
        return 1

    print(f"check: clean — {len(entries)} injection(s) registered, all restored "
          f"and absent from the working tree.")
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="redproof.py",
        description="Red-proof injection registry + hand-off gate (#683). "
                    "Turns the red-proof restore discipline into a check.")
    ap.add_argument("verb", choices=["begin", "restore", "forget", "check"],
                    help="begin PATH = snapshot original; "
                         "restore PATH = record injected + restore original; "
                         "forget PATH = drop an entry; "
                         "check = hand-off gate")
    ap.add_argument("path", nargs="?", help="repo-relative path (for begin/restore/forget)")
    ap.add_argument("--require", type=int, default=0,
                    help="check: refuse if fewer than N injections are registered")
    ap.add_argument("--cwd", default=None, help="derive for this directory")
    args = ap.parse_args(argv)
    cwd = Path(args.cwd) if args.cwd else None

    try:
        if args.verb == "check":
            return check(cwd, require=args.require)
        if args.path is None:
            ap.error(f"{args.verb} requires a path argument")
        if args.verb == "begin":
            return begin(cwd, args.path)
        if args.verb == "restore":
            return restore(cwd, args.path)
        if args.verb == "forget":
            return forget(cwd, args.path)
    except RedproofError as exc:
        sys.stderr.write(f"{args.verb}: FAULT — {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
