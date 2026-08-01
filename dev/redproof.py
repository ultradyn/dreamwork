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

A CLEAN TREE IS NOT A CLEAN BRANCH (#710)
-----------------------------------------
``check`` originally read only the working tree, and the loop mandates COMMIT
INCREMENTALLY — so the encouraged sequence *inject → commit while sabotaged →
restore → commit again* hands back a clean tree over a poisoned history, and
the merge puts the defect in master permanently, where ``bisect``, ``blame``
and ``cherry-pick`` all resurrect it. So ``check`` also scans every commit this
branch adds to its base for the recorded injected bytes. The remedy it names is
a **squash of that one branch**, not a rule against committing: the commit is
the crash-safety the loop exists to keep, and squashing every lane branch would
cost the coordinator the increments it reads deliberately.

The scan prints what it examined — commits, paths, blobs read — whatever the
verdict, because a scan of the wrong range finds nothing and is otherwise
indistinguishable from a clean branch (#590: a zero is a question about whether
you looked). An unresolvable base is a FAULT, not a zero.

THREE ZERO-STATES, NOT ONE (#136)
---------------------------------
- No registry file at all → **no evidence**: "no injections registered". A
  lane that never used the tool is not faulty, but this result must not read as
  a red-proof that examined nothing (#683 point 3).
- Registry present but unparseable → **FAULT** (exit 2): a broken channel must
  not read as a calm zero.
- Registry present and empty → **no evidence**: the tool observed no changed
  bytes, so there is no injection receipt to interpret.

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

Most importantly, file bytes cannot establish red-proof semantics. A target
named ``test_*.py`` or ``dev/capture/*.mjs`` is reported as ``test-like``;
everything else is conservatively ``other``, never ``production``. The path is
the resolved, worktree-confined target recorded by ``begin``, so a symlink or
relative spelling cannot hide a test-like target. This lexical signal is only
advisory: legitimate injections can target guard fixtures, and test files can
have other names. ``check`` therefore says explicitly that it verified
restoration and branch absence only — not that a test reached a production
seam, nor that a reported failure was discriminating (#795).

The history scan inherits all of that, and adds two of its own, both with a
test that asserts the miss so closing one fails loudly:

- **A fork point moved past the injection.** The range is
  ``merge-base(base, HEAD)..HEAD``, so if the branch is merged and then kept
  working on, the poisoned commit is behind the new merge-base and the scan
  cannot see it — while master already holds it. ``--base`` widens the range by
  hand; nothing widens it automatically.
- **An injection committed together with later edits to the same file.** The
  comparison is whole-file byte-identity, so if the lane edits the file between
  the sabotaged commit and ``restore``, the recorded bytes are not the
  committed bytes and the commit passes. (Rare, because ``restore`` copies the
  original over the file and would destroy such edits anyway.)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
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
    # removeprefix, not lstrip: lstrip takes a CHARACTER SET, so lstrip("./")
    # eats every leading '.' or '/' and mangles dotfile/dotdir paths like
    # .dreamwork/lessons.md -> dreamwork/lessons.md (#726).
    return path.replace("\\", "/").removeprefix("./")


def _worktree_path(root: Path, path: str) -> tuple[str, Path]:
    """Return a canonical repo-relative key and its resolved, confined path."""
    posix = _to_posix(path)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = (resolved_root / posix).resolve(strict=False)
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise RedproofError(
            f"path {posix!r} resolves outside the worktree ({resolved})"
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise RedproofError(f"cannot resolve path {posix!r}: {exc}") from exc
    return relative.as_posix(), resolved


def _target_kind(posix_path: str) -> str:
    """Conservative lexical signal for targets likely to be test machinery.

    The complement is deliberately ``other``, not ``production``: a filename
    cannot prove semantics, and test files need not follow either convention.
    ``posix_path`` is the resolved canonical key returned by ``_worktree_path``.
    """
    path = Path(posix_path)
    if path.name.startswith("test_") and path.suffix == ".py":
        return "test-like"
    if posix_path.startswith("dev/capture/") and path.suffix == ".mjs":
        return "test-like"
    return "other"


def _role(cwd: Path | None = None) -> str:
    """The role this redproof invocation acts under (#694).

    Threading the role through the snapshot/registry path is what separates an
    author's registry from a reviewer's. Without it, a reviewer running in the
    author's worktree would read and write the author's registry — the exact
    collision the tool exists to prevent, one level up from #652.
    """
    return _ls.lane_role()


def _snap_dir(cwd: Path | None, role: str | None = None) -> Path:
    return _ls.lane_scratch_dir(cwd, sub=SUB, role=role if role is not None
                                else _role(cwd))


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
    """The ARMED entry for a path, if any (#717: one armed injection per path).

    Restored entries with the same path are NOT returned here — restore appends
    a new entry per distinct injection, so a path can carry several restored
    records. Only an entry still in the ARMED state is a candidate for the
    next restore to consume."""
    for e in entries:
        if e.get("path") == posix_path and e.get("state") != RESTORED:
            return e
    return None


def _find_restored(entries: list[dict], posix_path: str,
                   injected_sha: str) -> dict | None:
    """A restored entry matching (path, injected_sha), for dedup (#717).

    The same sabotage bytes restored twice is the same observed state — one
    injection — so restore collapses it rather than double-counting. A
    different sha is a different injection and gets its own entry."""
    for e in entries:
        if (e.get("path") == posix_path and e.get("state") == RESTORED
                and e.get("injected_sha") == injected_sha):
            return e
    return None


def _read_wt(root: Path, posix_path: str) -> bytes:
    """Working-tree bytes of posix_path under root. Faults if unreadable."""
    _, p = _worktree_path(root, posix_path)
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
# history scan (#710)                                                          #
# --------------------------------------------------------------------------- #

# Tried in order when --base is not given. A lane branches from the repo's
# default branch. If none resolves the scan FAULTS rather than picking a range:
# a wrong range finds nothing and is indistinguishable from a clean branch.
DEFAULT_BASES = ("master", "main")


def _git(root: Path, *args: str) -> str:
    """git in ``root``; any failure is a FAULT, never a quiet empty answer."""
    try:
        proc = subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RedproofError(f"`git {' '.join(args)}` could not run: {exc}") from exc
    if proc.returncode != 0:
        raise RedproofError(
            f"`git {' '.join(args)}` failed ({proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout.decode("utf-8", "replace").strip()


def _resolve_base(root: Path, base: str | None) -> tuple[str, str]:
    """(merge-base oid, ref label) for the branch's own commits."""
    tried = [base] if base else list(DEFAULT_BASES)
    for ref in tried:
        try:
            _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        except RedproofError:
            continue
        return _git(root, "merge-base", ref, "HEAD"), ref
    raise RedproofError(
        f"no base ref resolves (tried: {', '.join(tried)}), so the history scan "
        f"has no range — and a scan with no range finds nothing and reads as a "
        f"clean branch (#671). Pass `--base <ref>`.")


def _batch_blobs(root: Path, commits: list[str],
                 paths: list[str]) -> dict[tuple[str, str], str]:
    """{(commit, path): sha1 of the bytes that commit holds for that path}.

    One ``git cat-file --batch`` pass rather than a subprocess per pair: the
    scan has to read actual bytes, and a per-commit cost is how a gate ends up
    switched off on a long branch.
    """
    specs = [(c, p) for c in commits for p in paths]
    if not specs:
        return {}
    stdin = "".join(f"{c}:{p}\n" for c, p in specs).encode()
    try:
        proc = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"],
                              input=stdin, capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RedproofError(f"`git cat-file --batch` could not run: {exc}") from exc
    if proc.returncode != 0:
        raise RedproofError(
            f"`git cat-file --batch` failed ({proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}")

    out, i, found = proc.stdout, 0, {}
    for spec in specs:
        nl = out.find(b"\n", i)
        if nl < 0:
            raise RedproofError(
                f"`git cat-file --batch` returned {len(found)} of {len(specs)} "
                f"records — the scan is incomplete and must not read as clean.")
        header = out[i:nl].decode("utf-8", "replace").split()
        i = nl + 1
        if header[-1] in ("missing", "ambiguous"):
            continue  # the path does not exist in that commit
        typ, size = header[1], int(header[2])
        payload = out[i:i + size]
        i += size + 1  # skip the record's trailing newline
        if typ == "blob":
            found[(spec[0], spec[1])] = _sha(payload)
    return found


def scan_history(cwd: Path | None, entries: list[dict],
                 base: str | None = None) -> dict:
    """Which of THIS BRANCH's own commits still hold a recorded injection.

    `check` reads the working tree, so the sequence the loop actively
    encourages — inject, COMMIT INCREMENTALLY while sabotaged, restore, commit
    again — hands back a clean tree over a poisoned history, and the merge puts
    the defect in master where bisect, blame and cherry-pick all resurrect it
    (#710).

    The comparison is byte-identity with a state the tool itself observed:
    ``restore`` records the working tree at restore time and copies the
    original back over it, so in that sequence the committed blob *is* the
    recorded injected blob. Not a heuristic and nothing to tune.

    Returns a report the caller prints IN FULL, zeroes included: a scan of the
    wrong range finds nothing and otherwise looks exactly like a clean branch,
    so the count of what was examined is part of the answer (#590).
    """
    root = _ls.worktree_root(cwd)
    live = [e for e in entries
            if e.get("state") == RESTORED and e.get("injected_sha")]
    base_oid, base_ref = _resolve_base(root, base)
    commits = [c for c in _git(root, "rev-list", f"{base_oid}..HEAD").split() if c]
    paths = sorted({e["path"] for e in live})
    blobs = _batch_blobs(root, commits, paths)

    order = {c: n for n, c in enumerate(commits)}
    hits = []
    for (commit, path), sha in blobs.items():
        for e in live:
            if e["path"] == path and sha == e["injected_sha"]:
                hits.append({"commit": commit, "path": path,
                             "hint": e.get("injected_hint"),
                             "subject": _git(root, "log", "-1", "--format=%s", commit)})
    hits.sort(key=lambda h: (order[h["commit"]], h["path"]))
    return {"base_oid": base_oid, "base_ref": base_ref, "commits": len(commits),
            "paths": len(paths), "blobs_read": len(blobs), "hits": hits}


def history_line(rep: dict) -> str:
    """What the scan examined — printed whatever the verdict, including zero."""
    if not rep["commits"]:
        return (f"history: EXAMINED NO COMMIT — 0 between {rep['base_oid'][:12]} "
                f"({rep['base_ref']}) and HEAD. Nothing of this branch is in "
                f"history yet, which is not the same as a history examined and "
                f"found clean.")
    return (f"history: examined {rep['commits']} commit(s) since "
            f"{rep['base_oid'][:12]} ({rep['base_ref']}) against {rep['paths']} "
            f"injected path(s); read {rep['blobs_read']} blob(s), "
            f"{len(rep['hits'])} holding a recorded injection.")


# --------------------------------------------------------------------------- #
# verbs                                                                        #
# --------------------------------------------------------------------------- #

def begin(cwd: Path | None, path: str) -> int:
    """Snapshot the ORIGINAL bytes of ``path`` and register an armed entry.

    Called BEFORE the sabotage. The snapshot and the registration are one act,
    so the lane cannot take the snapshot at the wrong moment (#704).
    """
    root = _ls.worktree_root(cwd)
    try:
        posix, target = _worktree_path(root, path)
        original = target.read_bytes()
    except RedproofError as exc:
        sys.stderr.write(f"begin: REFUSED — {exc}\n")
        return 2
    except FileNotFoundError:
        sys.stderr.write(f"begin: {posix!r} does not exist in the working tree\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"begin: cannot read {posix}: {exc}\n")
        return 2

    entries, _ = _read_registry(cwd)
    if _find(entries, posix) is not None:
        sys.stderr.write(
            f"begin: REFUSED — {posix!r} already has an armed snapshot; "
            "restore or forget it before beginning again\n")
        return 2
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

    A second DISTINCT injection to the same path is a separate record, not an
    overwrite of the first (#717): the count is the auditable part, and only
    the last injection per file surviving weakens the record's strongest use
    (reconstructing what was injected when a red-proof is disputed) — and now
    also blinds the #710 history scan, which matches commits against each
    recorded sha. So restore keys on (path, injected_sha): two different
    sabotages land as two entries, and the scan sees both shas. The SAME bytes
    restored twice collapse to one entry — an injection is a state the tool
    observed, and observing it twice is the same state, not two.
    """
    root = _ls.worktree_root(cwd)
    try:
        posix, _ = _worktree_path(root, path)
        entries, _ = _read_registry(cwd)
        armed = _find(entries, posix)
        if armed is None:
            sys.stderr.write(
                f"restore: {posix!r} has no armed injection — it was never "
                f"`begin`-ed, or its begin was already restored. Run "
                f"`begin {posix}` first.\n")
            return 2
        snap = Path(armed["snapshot"])
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
            # record. Drop the armed entry so check's byte-test never fires on
            # a no-op.
            entries = [e for e in entries if e is not armed]
            _write_registry(cwd, entries)
            print(f"restore: {posix!r} unchanged since begin — no injection recorded; "
                  f"entry dropped.")
            return 0

        injected_sha = _sha(injected)
        # #717: dedup the SAME observed state, append a DIFFERENT one. A path
        # may carry several restored records (one per distinct injection), so
        # the count is honest and the history scan has every injected sha.
        entry = _find_restored(entries, posix, injected_sha)
        if entry is None:
            entry = {"path": posix}
            entries.append(entry)
        entry.update({
            "injected_sha": injected_sha,
            "injected_hint": _first_changed_line(original, injected),
            "state": RESTORED,
            "restored_at": _now(),
        })
        # The armed entry is consumed: its snapshot served this restore. Drop
        # it so check does not see a begun-but-unrestored entry for a path that
        # was in fact restored (#717: append-only across injections, not within
        # one).
        entries = [e for e in entries if e is not armed]

        # Restore the original by cp, then verify byte-identity. Never git checkout.
        _, out = _worktree_path(root, posix)
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
    root = _ls.worktree_root(cwd)
    try:
        posix, _ = _worktree_path(root, path)
    except RedproofError as exc:
        sys.stderr.write(f"forget: REFUSED — {exc}\n")
        return 2
    entries, _ = _read_registry(cwd)
    before = len(entries)
    entries = [e for e in entries if e.get("path") != posix]
    if len(entries) == before:
        sys.stderr.write(f"forget: nothing registered for {posix!r}\n")
        return 1
    _write_registry(cwd, entries)
    print(f"forget: dropped entry for {posix!r} (working tree untouched)")
    return 0


def check(cwd: Path | None, *, require: int = 0, base: str | None = None) -> int:
    """Hand-off gate: refuse if a registered injection survives in tree OR history.

    Exit 0 = restoration clean, or no evidence when no injection is registered.
    Exit 1 = REFUSAL: a registered injection is live in the tree, or committed
             on this branch (#710).
    Exit 2 = FAULT: could not evaluate (#671/#136).

    The discriminating test: for every restored entry, the working tree must
    NOT equal the recorded injected bytes. A restored-then-further-edited file
    differs from the injection and passes (#683 point 1). An armed (begun but
    unrestored) entry is a refusal: the red-proof is incomplete.

    Then the same comparison against every commit this branch adds to its base,
    because a clean tree says nothing about what the branch will merge (#710).
    """
    root = _ls.worktree_root(cwd)
    role = _role(cwd)
    try:
        entries, source = _read_registry(cwd)
    except RedproofError as exc:
        sys.stderr.write(f"check: FAULT — {exc}\n")
        return 2

    if not entries:
        # Honest zero. "absent" (never used) and "empty" (ran, nothing live)
        # both provide no restoration evidence; an unparseable registry already
        # raised before we got here.
        label = "no injections registered" if source == "absent" else "registry empty"
        if require > 0:
            sys.stderr.write(
                f"check: REFUSED — {label} (role: {role}), but --require "
                f"{require} was set. A hand-off that the brief mandated "
                f"red-proofing must show at least one registered injection.\n")
            return 1
        print(f"check: no evidence — {label} (role: {role}); injection "
              f"restoration was not evaluated; production reach was not evaluated.")
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

    try:
        rep = scan_history(cwd, entries, base)
    except RedproofError as exc:
        sys.stderr.write(f"check: FAULT — {exc}\n")
        return 2
    print(history_line(rep))

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
    if rep["hits"]:
        lines = [f"  {h['commit'][:12]} {h['path']} — {h['subject']!r} "
                 f"(hint: {h['hint']!r})" for h in rep["hits"]]
        sys.stderr.write(
            f"check: REFUSED — the working tree is clean, but {len(rep['hits'])} "
            f"commit(s) on this branch still hold a recorded injection:\n"
            + "\n".join(lines) +
            "\nCommitting mid-injection is correct — COMMIT INCREMENTALLY exists "
            "because lanes get killed without warning — but the branch cannot "
            "merge as it stands: a merge makes the defect reachable from master "
            "forever, where bisect, blame and cherry-pick all resurrect it. "
            "Tell the coordinator to SQUASH this branch at merge (the fix for "
            "this branch only), or rebase the injection out yourself. #710\n")
        return 1

    restored = [e for e in entries if e.get("state") == RESTORED]
    kinds = [_target_kind(e["path"]) for e in restored]
    test_like = kinds.count("test-like")
    other = kinds.count("other")
    listed = "\n".join(
        f"  [{_target_kind(e['path'])}] {e['path']} "
        f"(sha {e.get('injected_sha', '?')[:12]}, "
        f"hint: {e.get('injected_hint', '?')!r})" for e in restored)
    print(f"check: restoration clean — {len(restored)} injection(s) registered "
          f"(role: {role}); registered bytes are restored and absent from the "
          f"working tree and from this branch's commits.")
    print(f"targets: {other} other target(s), {test_like} test-like target(s).")
    print("tool scope: red-proof semantics and production reach were NOT verified.")
    if test_like:
        print("WARNING: test-like targets are valid when test/guard tooling is "
              "the named production subject; otherwise this does not establish "
              "a production injection.")
    if listed:
        print(listed)
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
    ap.add_argument("path", nargs="?", help="repo-relative path confined to the resolved "
                    "worktree (for begin/restore/forget)")
    ap.add_argument("--require", type=int, default=0,
                    help="check: refuse if fewer than N injections are registered")
    ap.add_argument("--base", default=None,
                    help=f"check: base ref for the history scan (default: first "
                         f"of {', '.join(DEFAULT_BASES)} that resolves)")
    ap.add_argument("--cwd", default=None, help="derive for this directory")
    args = ap.parse_args(argv)
    cwd = Path(args.cwd) if args.cwd else None

    try:
        if args.verb == "check":
            return check(cwd, require=args.require, base=args.base)
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
