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

    python3 dev/redproof.py begin router.js --expectation test_router.py
                                               # pin an independent expectation
    # ...sabotage router.js; run the red test; watch it fail...
    python3 dev/redproof.py restore router.js    # record INJECTED, restore, cmp
    # ...apply the real fix (may edit router.js further)...
    python3 dev/redproof.py check                # hand-off gate

``begin`` snapshots the original to the lane-private scratch dir (#652, never
``/tmp``), and pins one or more independent expectation files by their bytes.
The expectation source must not be the injected file itself. ``restore`` reads
the *current* (injected) bytes, verifies every pinned expectation is unchanged,
records the injected sha and the first line that differs from the original,
then copies the original back and verifies byte-identity — never ``git
checkout`` (#349). ``check`` repeats the expectation-byte comparison at the
hand-off and refuses if an expectation was omitted or drifted, as well as if
any registered file still matches its recorded injection.

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

A RE-ARM MUST NOT MOVE THE REGISTRATION BOUNDARY FORWARD (#942)
---------------------------------------------------------------
The history scan bounds each record by ``begun_head``, so it cannot blame a
commit that predates the lane's registration. That boundary is correct — the
canonical direction-1 sabotage *is* the pre-fix bytes, which legitimately
existed on the branch before the tool observed them.

But the remedy this tool prints for post-rebase expectation drift is ``forget``
+ ``begin``, and ``forget`` used to ERASE the record. Re-arming then set a new
boundary at the rebased tip — after the commit still holding the injection — so
the scan reclassified it as preexisting and printed ``0 holding a recorded
injection`` over a branch that genuinely held one. Rebasing is mandatory before
hand-off, so this sat on the ordinary lane lifecycle, and every step of it was
documented advice followed correctly.

``forget`` therefore RETIRES a restored registration instead of erasing it: the
record keeps its ``injected_sha`` and its ORIGINAL ``begun_head`` and stays in
scope for the history scan alone. A lane may withdraw a claim about its own
evidence; it cannot un-commit a commit. And the scan now reports what the
boundary EXCLUDED, so "the boundary ate the range" can never again wear the
words of "I looked and found nothing".

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
RETIRED = "retired"    # forgotten as live evidence; still in HISTORY scope (#942)

# The states THIS build knows how to classify. An entry whose ``state`` is not
# in this set is UNKNOWN to this build of redproof.py — fail-closed as the
# dangerous case, but named distinctly (#950): a lane that adds a state and
# exercises it leaves the post-lane registry holding it, and the pre-merge
# gate runs an OLDER build that classifies every unknown entry as armed, so
# the lane's own check (newer tool) reads clean while the gate (older tool)
# refuses. The fail-closed direction is right and is not changed: unknown is
# still refused. What changes is that the refusal NAMES the format-skew
# possibility rather than reading identically to four genuinely-armed entries.
KNOWN_STATES = (ARMED, RESTORED, RETIRED)

# Re-arm guidance appended to every expectation-drift refusal (#910). The
# natural lane rhythm — inject, observe red, add a test, restore — edits an
# expectation file mid-injection, and that breaks the byte pin on purpose
# (#852): an expectation must not move with its subject. The refusal is
# correct; what was missing was what to do NEXT. The remedy is always a
# deliberate re-arm (forget + begin + sabotage + restore), never an automatic
# one — the human act is what makes the new expectation a claim rather than a
# side effect.
_EXPECTATION_DRIFT_REARM = (
    "Editing an expectation file mid-injection is legitimate (inject -> red "
    "-> add a test -> restore is the natural lane rhythm) and breaks this "
    "byte pin on purpose: an expectation must not move with its subject "
    "(#852). To re-arm deliberately, `forget <path>`, then `begin <path> "
    "--expectation <source>` against the new bytes, re-sabotage, and "
    "`restore`, then re-run `check`. A rebase can stale the pin even after "
    "a clean restore, so repeat that cycle after the final rebase."
)


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


def _pin_expectations(root: Path, target_posix: str,
                      declarations: list[str]) -> list[dict]:
    """Resolve and pin the independent expectation files for one injection."""
    if not declarations:
        raise RedproofError(
            f"injection of {target_posix!r} must declare at least one "
            "expectation source with --expectation; an unpinned expectation "
            "cannot be red-proof evidence")

    sources: list[dict] = []
    seen: set[str] = set()
    for declaration in declarations:
        posix, source = _worktree_path(root, declaration)
        if posix == target_posix:
            raise RedproofError(
                f"expectation source {posix!r} is the injected file; the "
                "subject and expectation must have distinct canonical paths")
        if posix in seen:
            continue
        try:
            data = source.read_bytes()
        except FileNotFoundError as exc:
            raise RedproofError(
                f"expectation source {posix!r} does not exist in the working "
                "tree") from exc
        except OSError as exc:
            raise RedproofError(
                f"cannot read expectation source {posix!r}: {exc}") from exc
        sources.append({"path": posix, "sha": _sha(data)})
        seen.add(posix)
    return sources


def _expectation_drift(root: Path, entry: dict) -> list[str]:
    """Return expectation drift descriptions, faulting on unevaluable state."""
    sources = entry.get("expectation_sources")
    if not isinstance(sources, list) or not sources:
        raise RedproofError(
            f"injection {entry.get('path', '?')!r} has no pinned expectation "
            "source; the registry cannot establish an independent expectation")
    drift: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            raise RedproofError(
                f"injection {entry.get('path', '?')!r} has a malformed "
                "expectation-source record")
        path = source.get("path")
        pinned_sha = source.get("sha")
        if not isinstance(path, str) or not isinstance(pinned_sha, str):
            raise RedproofError(
                f"injection {entry.get('path', '?')!r} has an incomplete "
                "expectation-source record")
        posix, _ = _worktree_path(root, path)
        if posix == entry.get("path"):
            drift.append(
                f"{entry.get('path', '?')!r}: expectation source {posix!r} "
                "is the injected file")
            continue
        actual = _read_wt(root, posix)
        actual_sha = _sha(actual)
        if actual_sha != pinned_sha:
            drift.append(
                f"{entry.get('path', '?')!r}: expectation source {posix!r} "
                f"changed (pinned {pinned_sha[:12]}, current {actual_sha[:12]})")
    return drift


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


def _identity_segment(lane: str | None = None) -> str:
    """Resolve one launch identity; an explicit ``--lane`` wins over env."""
    if lane is not None:
        lane = lane.strip()
        if not lane:
            raise RedproofError(
                "--lane names an empty launch identity; pass a non-empty "
                "DREAMWORK_LANE_ID value")
    return _ls.identity_segment(lane)


def _snap_dir(cwd: Path | None, role: str | None = None,
              lane: str | None = None) -> Path:
    """Resolve this invocation's red-proof dir without creating it."""
    return _redproof_dir(cwd, _identity_segment(lane),
                         role if role is not None else _role(cwd))


def _redproof_dir(cwd: Path | None, identity_seg: str, role: str) -> Path:
    """The ``redproof`` dir for an EXPLICIT identity segment + role (no create).

    Lets a coordinator audit a lane whose launch token is not in this process's
    env (#895): pass the segment ``identity_segment(<token>)`` yields, or ``""``
    for the legacy (no-identity) path. Never creates, so enumeration does not
    manufacture phantom registries.
    """
    base = _ls.SCRATCH_ROOT / _ls.repo_key(cwd) / _ls.lane_key(cwd)
    if identity_seg:
        base = base / identity_seg
    rseg = _ls.role_segment(role)
    if rseg:
        base = base / rseg
    return base / SUB


def _registry_path(cwd: Path | None, lane: str | None = None) -> Path:
    return _snap_dir(cwd, lane=lane) / "registry.json"


def _snapshot_path(cwd: Path | None, posix_path: str,
                   lane: str | None = None) -> Path:
    # One safe filename per registered path: collisions would let one entry's
    # restore clobber another's original, the exact failure snapshots prevent.
    return (_snap_dir(cwd, lane=lane)
            / (hashlib.sha1(posix_path.encode()).hexdigest() + ".orig"))


def _claim_path(snapshot: Path) -> Path:
    return Path(f"{snapshot}.armed")


def _claim_snapshot(snapshot: Path, posix_path: str) -> None:
    """Atomically claim a name so concurrent begins cannot both overwrite it."""
    claim = _claim_path(snapshot)
    try:
        fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RedproofError(
            f"snapshot name for {posix_path!r} is already armed ({claim}); "
            "restore or forget it before beginning again") from exc
    os.close(fd)


def _release_snapshot(snapshot: Path) -> None:
    _claim_path(snapshot).unlink(missing_ok=True)


class RedproofError(Exception):
    """A fault the tool cannot evaluate — callers print and exit 2 (#671)."""


def _read_registry(cwd: Path | None,
                   lane: str | None = None) -> tuple[list[dict], str]:
    """Return (entries, source_label) for THIS lane's own registry.

    Delegates to :func:`_read_registry_at` at the resolved path. An explicit
    lane wins over the environment, matching ``check``'s established rule.
    """
    return _read_registry_at(_registry_path(cwd, lane))


def _read_registry_at(rp: Path) -> tuple[list[dict], str]:
    """Return (entries, source_label). Distinguishes the three zero-states.

    source_label is one of:
      "absent"   — no registry file (calm zero; the tool was never used)
      "empty"    — registry parsed to [] (calm zero; nothing live)
      "present"  — registry held ≥1 entry
    A present-but-unparseable registry raises RedproofError (#136 fault).
    """
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


def _write_registry(cwd: Path | None, entries: list[dict],
                    lane: str | None = None) -> None:
    rp = _registry_path(cwd, lane)
    rp.parent.mkdir(parents=True, exist_ok=True)
    tmp = rp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(rp)


def _find(entries: list[dict], posix_path: str) -> dict | None:
    """The ARMED entry for a path, if any (#717: one armed injection per path).

    Restored entries with the same path are NOT returned here — restore appends
    a new entry per distinct injection, so a path can carry several restored
    records. Only an entry still in the ARMED state is a candidate for the
    next restore to consume. RETIRED records are excluded for the same reason
    and one more: `begin` refuses a path that already has an armed entry, so a
    retired record left by `forget` would block the re-arm it exists to survive
    (#942). The test is still `not in (…)` rather than `== ARMED`, so a
    malformed entry with no state reads as armed and fails closed."""
    for e in entries:
        if (e.get("path") == posix_path
                and e.get("state") not in (RESTORED, RETIRED)):
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
    so the count of what was examined is part of the answer (#590). That now
    includes what the registration boundary EXCLUDED — see ``excluded`` below.
    """
    root = _ls.worktree_root(cwd)
    # RETIRED records are in scope here and nowhere else (#942): a lane may
    # withdraw a claim about its own evidence, but it cannot un-commit a commit.
    recorded = [e for e in entries
                if e.get("state") in (RESTORED, RETIRED) and e.get("injected_sha")]
    base_oid, base_ref = _resolve_base(root, base)
    commits = [c for c in _git(root, "rev-list", f"{base_oid}..HEAD").split() if c]
    paths = sorted({e["path"] for e in recorded})
    blobs = _batch_blobs(root, commits, paths)

    # A matching blob is armed only when its commit did not already exist at
    # begin.  Use immutable reachability, never dates: author and committer
    # timestamps are freely rewritten, while a rebase gives rewritten commits
    # new object ids that cannot become ancestors of the recorded old HEAD.
    preexisting = {
        id(e): set(_git(root, "rev-list", e["begun_head"]).split())
        if e.get("begun_head") else set()
        for e in recorded
    }
    order = {c: n for n, c in enumerate(commits)}
    hits, excluded = [], []
    for (commit, path), sha in blobs.items():
        # Per (commit, path), not per record: two records can carry the same
        # bytes (a re-arm re-injects them), and one commit holding one
        # injection is one finding, not one per record that remembers it.
        matches = [e for e in recorded
                   if e["path"] == path and sha == e["injected_sha"]]
        if not matches:
            continue
        armed_by = [e for e in matches if commit not in preexisting[id(e)]]
        subject = _git(root, "log", "-1", "--format=%s", commit)
        if armed_by:
            hits.append({"commit": commit, "path": path,
                         "hint": armed_by[0].get("injected_hint"),
                         "subject": subject})
        else:
            # EVERY record of these bytes was begun at a head that already
            # contained this commit, so it predates registration. Correct — and
            # reported, because "excluded" and "not found" were one silent zero
            # and that is exactly how #942 hid a real injection.
            excluded.append({"commit": commit, "path": path,
                             "hint": matches[0].get("injected_hint"),
                             "subject": subject,
                             "boundary": matches[0].get("begun_head")})
    hits.sort(key=lambda h: (order[h["commit"]], h["path"]))
    excluded.sort(key=lambda h: (order[h["commit"]], h["path"]))
    return {"base_oid": base_oid, "base_ref": base_ref, "commits": len(commits),
            "paths": len(paths), "blobs_read": len(blobs), "hits": hits,
            "excluded": excluded, "records": len(recorded),
            "retired": sum(1 for e in recorded if e.get("state") == RETIRED)}


def history_line(rep: dict) -> str:
    """What the scan examined — printed whatever the verdict, including zero.

    THREE ZEROES, THREE SENTENCES (#868/#915/#942). "I looked and found
    nothing", "there was nothing to look for", and "I found matches and the
    boundary ruled them out" are different facts, and #942 is what it costs to
    print them the same: a re-arm moved the boundary past a real injection, the
    third case wore the first case's words, and the branch read clean.
    """
    if not rep["commits"]:
        return (f"history: EXAMINED NO COMMIT — 0 between {rep['base_oid'][:12]} "
                f"({rep['base_ref']}) and HEAD. Nothing of this branch is in "
                f"history yet, which is not the same as a history examined and "
                f"found clean.")
    if not rep["paths"]:
        return (f"history: NOTHING TO LOOK FOR — {rep['commits']} commit(s) since "
                f"{rep['base_oid'][:12]} ({rep['base_ref']}) were compared "
                f"against 0 injected path(s), because no injected bytes are "
                f"recorded. Nothing was searched for, which is not the same as "
                f"searching and finding nothing.")
    line = (f"history: examined {rep['commits']} commit(s) since "
            f"{rep['base_oid'][:12]} ({rep['base_ref']}) against {rep['paths']} "
            f"injected path(s); read {rep['blobs_read']} blob(s), "
            f"{len(rep['hits'])} holding a recorded injection.")
    if rep.get("retired"):
        line += (f" {rep['retired']} of the record(s) searched for are RETIRED "
                 f"(forgotten as live evidence, kept in history scope).")
    excluded = rep.get("excluded") or []
    if excluded:
        line += (f"\nhistory: the registration boundary EXCLUDED {len(excluded)} "
                 f"commit(s) that DO hold bytes recorded as an injection. Every "
                 f"record of those bytes was begun at a head that already "
                 f"contained the commit, so it predates this lane's "
                 f"registration and is not blamed. That is a scan which looked "
                 f"and declined to blame — not a scan that found nothing:")
        for x in excluded:
            line += (f"\n  {x['commit'][:12]} {x['path']} — {x['subject']!r} "
                     f"(hint: {x['hint']!r}; boundary "
                     f"{(x.get('boundary') or '?')[:12]})")
    return line


# --------------------------------------------------------------------------- #
# bundle staleness (#877)                                                      #
# --------------------------------------------------------------------------- #

# Testability hook: tests in fixtures without client_dist.py set this to the
# real module. Unset in production; the worktree's own copy is loaded by path.
_client_dist_override = None


def _load_client_dist(root: Path):
    """The ``client_dist`` module for this worktree, or None when absent.

    ``client_dist.py`` lives at the repo root (beside ``watch.py``), not in
    ``dev/``, so a bare ``import`` from this file's location would miss it.
    Loading by path from the worktree root keeps redproof decoupled from
    ``sys.path`` and lets a tree without a build pass through unchecked.
    """
    if _client_dist_override is not None:
        return _client_dist_override
    cd = root / "client_dist.py"
    if not cd.exists():
        return None
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("_rp_client_dist", str(cd))
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def bundle_stale_findings(root: Path, entries: list[dict]) -> list[dict]:
    """Restored build-input sources whose downstream bundle is stale (#877).

    A source restored after a sabotaged build leaves the BUNDLE holding the
    injection: the bundle was compiled from the injected bytes, and the
    restore only touched the source. ``redproof check`` certified the source
    and read clean — while a guard serving the bundle still held the defect.

    The signal reuses ``client_dist.check`` — the single staleness
    implementation, already shared by ``lint.py`` — rather than a second hash
    comparison. After a sabotaged build + source restore,
    ``client_dist.check`` reports the SOURCE as stale (the manifest was
    rebuilt against the injected source, so it disagrees with the restored
    original). The combination — a restored entry whose path is a build input
    AND appears in that stale list — is the precise condition: the bundle was
    built from bytes that disagree with the restored source.

    Returns ``[]`` when ``client_dist`` is absent (a tree without a build),
    when the dist is current, or when the staleness is on a path that is not
    a restored injection. A dist stale for an UNRELATED reason (a real edit
    to a different input) does not fire, because the restored path is not in
    the stale list.
    """
    cd = _load_client_dist(root)
    if cd is None:
        return []
    expected = cd.expected_inputs(str(root))
    if not expected:
        return []
    reading = cd.check(str(root))
    if reading.get("state") != cd.STALE:
        return []
    stale = set(reading.get("stale") or [])
    findings = []
    for e in entries:
        if e.get("state") != RESTORED:
            continue
        path = e.get("path")
        if path and path in expected and path in stale:
            findings.append({"path": path, "note": reading.get("note"),
                             "fix": reading.get("fix")})
    return findings


# --------------------------------------------------------------------------- #
# verbs                                                                        #
# --------------------------------------------------------------------------- #

def begin(cwd: Path | None, path: str,
          expectations: list[str] | tuple[str, ...] = (), *,
          lane: str | None = None) -> int:
    """Snapshot the ORIGINAL bytes of ``path`` and register an armed entry.

    Called BEFORE the sabotage. The snapshot and the registration are one act,
    so the lane cannot take the snapshot at the wrong moment (#704). At least
    one independent expectation source is required and pinned in the entry.
    """
    root = _ls.worktree_root(cwd)
    try:
        identity_dir = _snap_dir(cwd, lane=lane)
        print(f"begin: resolved identity dir {identity_dir} (role: {_role(cwd)})")
        posix, target = _worktree_path(root, path)
        original = target.read_bytes()
        expectation_sources = _pin_expectations(root, posix, list(expectations))
        begun_head = _git(root, "rev-parse", "HEAD")
    except RedproofError as exc:
        sys.stderr.write(f"begin: REFUSED — {exc}\n")
        return 2
    except FileNotFoundError:
        sys.stderr.write(f"begin: {posix!r} does not exist in the working tree\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"begin: cannot read {posix}: {exc}\n")
        return 2

    entries, _ = _read_registry(cwd, lane)
    if _find(entries, posix) is not None:
        sys.stderr.write(
            f"begin: REFUSED — {posix!r} already has an armed snapshot; "
            "restore or forget it before beginning again\n")
        return 2
    snap = _snapshot_path(cwd, posix, lane)
    snap.parent.mkdir(parents=True, exist_ok=True)
    try:
        _claim_snapshot(snap, posix)
    except RedproofError as exc:
        sys.stderr.write(f"begin: REFUSED — {exc}\n")
        return 2
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
        # Commit reachability is the registration boundary.  Unlike begun_at,
        # it cannot be forged by commit-date rewriting (#901).
        "begun_head": begun_head,
        "expectation_sources": expectation_sources,
        # cleared until restore records them:
        "injected_sha": None,
        "injected_hint": None,
        "restored_at": None,
    })
    _write_registry(cwd, entries, lane)
    print(f"begin: snapshotted original of {posix} ({len(original)} bytes) -> {snap}")
    # State the root distinction (#934): lane_scratch.py snap and redproof print
    # DIFFERENT roots for one lane (snap/ vs redproof/), and four lanes tripped
    # on a `cmp` against the wrong one. Naming the sibling here makes the
    # discrepancy STATED at the moment the path is in hand, not discovered via a
    # false `cmp`. `restore` verifies the copy internally, so a manual `cmp` is
    # redundant for users of this protocol — but anyone who runs one must aim it
    # at THIS printed path, not at a lane_scratch.py snap path.
    print(f"       red-proof root under redproof/ — NOT lane_scratch.py's snap/ "
          f"root; `restore` verifies internally, and a manual `cmp` uses THIS path")
    print(f"       pinned {len(expectation_sources)} independent expectation "
          "source(s).")
    print(f"       state=armed; sabotage it, then `restore {posix}`.")
    return 0


def restore(cwd: Path | None, path: str, *, lane: str | None = None) -> int:
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
        identity_dir = _snap_dir(cwd, lane=lane)
        print(f"restore: resolved identity dir {identity_dir} (role: {_role(cwd)})")
        posix, _ = _worktree_path(root, path)
        entries, _ = _read_registry(cwd, lane)
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

        drift = _expectation_drift(root, armed)
        if drift:
            raise RedproofError(
                "declared expectation source changed during the injection; "
                "refusing to record a red-proof:\n  " + "\n  ".join(drift)
                + "\n" + _EXPECTATION_DRIFT_REARM)

        injected = _read_wt(root, posix)

        if _sha(injected) == _sha(original):
            # begin was called but the file was never changed: no injection to
            # record. Drop the armed entry so check's byte-test never fires on
            # a no-op.
            entries = [e for e in entries if e is not armed]
            _write_registry(cwd, entries, lane)
            _release_snapshot(snap)
            print(f"restore: {posix!r} unchanged since begin — no injection recorded; "
                  f"entry dropped.")
            return 0

        injected_sha = _sha(injected)
        # #717: dedup the SAME observed state, append a DIFFERENT one. A path
        # may carry several restored records (one per distinct injection), so
        # the count is honest and the history scan has every injected sha.
        entry = _find_restored(entries, posix, injected_sha)
        if entry is None:
            entry = {
                "path": posix,
                "begun_head": armed.get("begun_head"),
                "expectation_sources": armed.get("expectation_sources"),
            }
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
        _write_registry(cwd, entries, lane)
        _release_snapshot(snap)
    except RedproofError as exc:
        sys.stderr.write(f"restore: FAULT — {exc}\n")
        return 2
    print(f"restore: {posix!r} injected state recorded (sha {entry['injected_sha'][:12]}, "
          f"hint: {entry['injected_hint']!r}); original restored & verified.")
    return 0


def forget(cwd: Path | None, path: str, *, lane: str | None = None) -> int:
    """Drop an ARMED entry; RETIRE a RESTORED one. Does not touch the WT.

    ``forget`` is the first half of the re-arm remedy this tool prints on
    expectation drift (#910), and a rebase makes that remedy routine — so this
    verb runs on the ordinary lane lifecycle, not only after a mistake.

    ERASING A RESTORED REGISTRATION WAS A HOLE (#942). The history scan bounds
    each record by the head it was begun at, which is what stops it blaming
    commits that predate the lane. Deleting the record and beginning again set
    a NEW boundary at the rebased tip — AFTER the commit still holding the
    injection — so the scan reclassified the real injection as preexisting and
    printed ``0 holding a recorded injection`` over a genuinely broken branch.
    The tool's own printed advice defeated the tool's own check.

    So a restored registration is RETIRED, not erased. It keeps its
    ``injected_sha`` and its ORIGINAL ``begun_head`` and stays in scope for the
    history scan — and for nothing else: not the working-tree test, not
    ``--require``, not the expectation pin, not the target listing. A lane may
    withdraw a claim about its own evidence; it cannot un-commit a commit.

    Retiring rather than REFUSING the forget is what keeps #910's remedy
    executable: the stale expectation pin is dropped (that is the point of the
    re-arm), the snapshot claim is released so ``begin`` can re-arm, and the
    branch fact survives. There is deliberately no ``--purge``: a hand bypass
    of a tool built to stop a failure reproduces that exact failure.
    """
    root = _ls.worktree_root(cwd)
    try:
        identity_dir = _snap_dir(cwd, lane=lane)
        print(f"forget: resolved identity dir {identity_dir} (role: {_role(cwd)})")
        posix, _ = _worktree_path(root, path)
    except RedproofError as exc:
        sys.stderr.write(f"forget: REFUSED — {exc}\n")
        return 2
    entries, _ = _read_registry(cwd, lane)
    kept: list[dict] = []
    dropped = retired_now = already_retired = 0
    for e in entries:
        if e.get("path") != posix:
            kept.append(e)
        elif e.get("state") == RETIRED:
            kept.append(e)
            already_retired += 1
        elif e.get("state") == RESTORED and e.get("injected_sha"):
            # Deliberately minimal: no expectation_sources, so a retired record
            # can never re-enter the drift population the re-arm exists to clear.
            kept.append({"path": posix, "state": RETIRED,
                         "injected_sha": e["injected_sha"],
                         "injected_hint": e.get("injected_hint"),
                         "begun_head": e.get("begun_head"),
                         "retired_at": _now()})
            retired_now += 1
        else:
            dropped += 1
    if not dropped and not retired_now:
        sys.stderr.write(
            f"forget: nothing to forget for {posix!r}"
            + (f" — {already_retired} retired record(s) remain in history scope "
               f"and cannot be dropped (#942)" if already_retired else
               " (nothing registered)") + "\n")
        return 1
    _write_registry(cwd, kept, lane)
    _release_snapshot(_snapshot_path(cwd, posix, lane))
    print(f"forget: {posix!r} — dropped {dropped} armed/unrecorded entry(ies), "
          f"RETIRED {retired_now} restored registration(s) (working tree untouched)")
    if retired_now:
        print("       A retired registration keeps its injected bytes and its "
              "ORIGINAL registration boundary and stays in scope for the history "
              "scan only. Forgetting the record cannot un-commit a commit that "
              "holds those bytes (#942).")
    return 0


def _check_scope_line(audit_sources: list[tuple[str, Path, bool]]) -> str:
    paths = "; ".join(f"{label}: {path}" for label, path, _ in audit_sources)
    return f"check: resolved identity registry path(s): {paths}"


def _check_error(scope: str, message: str) -> None:
    """Keep the discriminating error first; append the identity evidence."""
    sys.stderr.write(message.rstrip("\n") + "\n" + scope + "\n")


def check(cwd: Path | None, *, require: int = 0, base: str | None = None,
          lane: str | None = None) -> int:
    """Hand-off gate: refuse if a registered injection survives in tree OR history.

    Exit 0 = restoration clean, or no evidence when no injection is registered.
    Exit 1 = REFUSAL: a registered injection is live in the tree, or committed
             on this branch (#710).
    Exit 2 = FAULT: could not evaluate (#671/#136).

    The discriminating test: for every restored entry, the working tree must
    NOT equal the recorded injected bytes. A restored-then-further-edited file
    differs from the injection and passes (#683 point 1). An armed (begun but
    unrestored) entry is a refusal: the red-proof is incomplete. Every restored
    entry must also carry expectation sources whose bytes still match the
    begin-time pins; otherwise the expectation may have moved with the subject.

    Then the same comparison against every commit this branch adds to its base,
    because a clean tree says nothing about what the branch will merge (#710).

    Then a build-awareness check (#877): for surfaces served out of a built
    bundle, restoring the SOURCE is not enough — the bundle must be rebuilt.
    ``check`` refuses when a restored source is a ``client_dist`` build input
    and the downstream bundle is stale (the manifest was rebuilt against the
    injected source), because the bundle a guard serves may still hold the
    injection. Reuses ``client_dist.check`` — the single staleness answer —
    and only fires when the restored path itself is stale, so a dist dirty for
    an unrelated reason does not trigger a false refusal.
    """
    root = _ls.worktree_root(cwd)
    role = _role(cwd)
    own_token = _ls.lane_identity()          # env DREAMWORK_LANE_ID, or None

    # Resolution (#895). #870 keyed lane scratch on a dispatcher-generated
    # DREAMWORK_LANE_ID that is UNSET in the coordinator's shell, so a
    # coordinator's `check` used to resolve an empty scratch and print an
    # all-clear over a lane that had registered and restored injections.
    #
    # MODE A — a launch identity is known (env set, or --lane names one): audit
    #           that ONE registry exactly. This is the lane's own hand-off gate,
    #           and #870's keying is correct and unchanged here.
    # MODE B — no identity anywhere (the coordinator): ENUMERATE every identity
    #           dir under this lane's key plus the legacy path, and aggregate, so
    #           an armed injection a lane left on disk is FOUND rather than
    #           missed — and so "I could not read this lane's registry" never
    #           prints as "no injections registered" (#895, #863).
    named_seg = _identity_segment(lane) if lane is not None else None
    if own_token or named_seg is not None:
        seg = named_seg if lane is not None else _ls.identity_segment()
        audit_sources = [(f"--lane {lane}" if lane else "this lane",
                          _redproof_dir(cwd, seg, role) / "registry.json",
                          False)]
        coordinator_mode = False
    else:
        # TWO DISJOINT POPULATIONS, and they are reported as two (#942). The
        # legacy registry is NOT one of the identity dirs, so a count of both
        # said "N registry/ies ACROSS M launch-identity dir(s)" over a
        # containment that does not hold — the true reading `1 across 0` read
        # as a self-contradiction and cost a lane a landing.
        audit_sources = [("legacy (no launch identity)",
                          _redproof_dir(cwd, "", role) / "registry.json", True)]
        for d in _ls.lane_identity_dirs(cwd):
            audit_sources.append((d.name, _redproof_dir(cwd, d.name, role)
                                  / "registry.json", False))
        coordinator_mode = True

    identity_scope = _check_scope_line(audit_sources)

    entries: list[dict] = []
    legacy_found = False
    identity_registries = 0
    for label, rp, is_legacy in audit_sources:
        try:
            sub_entries, source = _read_registry_at(rp)
        except RedproofError as exc:
            _check_error(identity_scope, f"check: FAULT — {label}: {exc}")
            return 2
        if source != "absent":
            if is_legacy:
                legacy_found = True
            else:
                identity_registries += 1
        for e in sub_entries:
            e["_source"] = label      # provenance for refusal messages
            entries.append(e)
    registries_found = identity_registries + (1 if legacy_found else 0)

    identity_dirs = len(_ls.lane_identity_dirs(cwd)) if coordinator_mode else None

    if coordinator_mode and not entries and registries_found == 0:
        # The blind case (#895): the coordinator located NO registry for this
        # worktree. Three facts, three different lines (#955) — do not collapse
        # any two, in either direction:
        #
        # (1) NO REGISTRY BECAUSE NONE WAS WARRANTED. Nothing was required
        #     (--require 0) AND no launch identity ever ran here (0 identity
        #     dirs) AND nothing was registered. A doc-only lane owes no
        #     red-proof, so an absent registry is the EXPECTED state, not a
        #     fault. It must still not read as an all-clear (#895/#932): it is
        #     NOT a verification of restoration (nothing was registered to
        #     restore) and NOT a clean sweep of a population — it audited
        #     nothing, and that is stated (#868).
        # (2) NO REGISTRY THAT COULD NOT BE FOUND. Either an injection WAS
        #     required and no registry could be located (the proof cannot be
        #     verified — #895's invisible-injection case), OR a launch identity
        #     ran here but left no readable registry (one this audit cannot
        #     reach might exist). Still FAULT (#671): the moment an injection
        #     was required, or a lane provably ran, an absent registry is a
        #     question, not an answer.
        # (3) Registry found and clean is the ordinary green reached below.
        #
        # --require governs the MINIMUM count, never the VALIDITY of what is
        # there: this whole block only runs when NO registry exists, so an
        # armed or unknown-state entry (which lives IN a registry) can never
        # reach the pass below — it is refused on the normal path regardless of
        # --require. Relaxing (1) does not relax that (#955).
        if require == 0 and identity_dirs == 0:
            print(
                "check: no injection required and none registered — 0 required, "
                f"audited 0 registry/ies across 0 launch-identity dir(s) "
                f"(role: {role}). A lane that owes no red-proof registers "
                f"nothing, so an absent registry is the expected state here, "
                f"NOT a verification of restoration (nothing was registered to "
                f"restore) and NOT an all-clear over a population this audit "
                f"did not sweep. If this lane ran a red-proof under a launch "
                f"identity, pass `--lane <DREAMWORK_LANE_ID>` or inspect its "
                f"scratch by hand.")
            print(identity_scope)
            return 0
        if require > 0:
            _check_error(identity_scope,
                f"check: FAULT — {require} injection(s) were required "
                f"(--require) but no redproof registry could be located for "
                f"this worktree (audited 0 registry/ies across "
                f"{identity_dirs} launch-identity dir(s); role: {role}). A "
                f"required red-proof must leave a registry this audit can "
                f"read; its absence means the proof cannot be verified, not "
                f"that it passed. If the lane ran, pass "
                f"`--lane <DREAMWORK_LANE_ID>` or inspect its scratch by "
                f"hand.")
        else:
            # require == 0 but a launch identity ran and left no registry:
            # the lane provably ran, so an absent registry is "could not
            # find", not "none was warranted". Stay fail-closed (#895/#671).
            _check_error(identity_scope,
                f"check: FAULT — found {identity_dirs} launch-identity dir(s) "
                f"but no redproof registry in any of them (role: {role}); 0 "
                f"injections were required, yet a lane provably ran here and "
                f"this audit could read no injection registry. This is NOT an "
                f"all-clear: a registry this audit cannot reach might exist, "
                f"and an armed injection it held would not be seen. If one was "
                f"expected, pass `--lane <DREAMWORK_LANE_ID>`.")
        return 2

    # RETIRED records are history-scan evidence and nothing else (#942), so
    # every live population below is built from `active`, and only
    # `scan_history` is handed `entries`.
    retired = [e for e in entries if e.get("state") == RETIRED]
    active = [e for e in entries if e.get("state") != RETIRED]

    if not active:
        # Honest zero. "absent" (never used) and "empty" (ran, nothing live)
        # both provide no restoration evidence; an unparseable registry already
        # raised before we got here.
        if coordinator_mode:
            label = (f"legacy registry "
                     f"{'present' if legacy_found else 'absent'}; audited "
                     f"{identity_registries} registry/ies across "
                     f"{identity_dirs} launch-identity dir(s); "
                     f"no injections registered")
        elif registries_found == 0:
            label = "no injections registered"
        else:
            label = "registry empty"
        if retired:
            label += (f" as live evidence — {len(retired)} retired "
                      f"registration(s) remain in history scope")
        if require > 0:
            _check_error(identity_scope,
                f"check: REFUSED — {label} (role: {role}), but --require "
                f"{require} was set. A hand-off that the brief mandated "
                f"red-proofing must show at least one registered injection.")
            return 1
        if not retired:
            print(f"check: no evidence — {label} (role: {role}); injection "
                  f"restoration was not evaluated; production reach was not "
                  f"evaluated.")
            print(identity_scope)
            return 0
        # Retired-only: there is no restoration to certify, but there ARE
        # recorded bytes to look for in history. Fall through to the scan.

    armed: list[dict] = []
    unknown: list[dict] = []   # entries whose state THIS build cannot read (#950)
    live: list[dict] = []
    expectation_drift: list[str] = []
    for e in active:
        st = e.get("state")
        if st not in KNOWN_STATES:
            # Fail-closed AND named (#950). An old gate meeting a state a newer
            # lane wrote must refuse — never default unknown to RESTORED, which
            # would land a genuinely-armed future entry silently. It refuses as
            # the dangerous case, but its refusal is DISTINCT from a real armed
            # entry so the two never wear each other's words.
            unknown.append(e)
            continue
        if st != RESTORED:
            armed.append(e)
            continue
        try:
            wt = _read_wt(root, e["path"])
            expectation_drift.extend(_expectation_drift(root, e))
        except RedproofError as exc:
            _check_error(identity_scope, f"check: FAULT — {exc}")
            return 2
        if _sha(wt) == e.get("injected_sha"):
            live.append(e)

    if require > 0 and len(active) < require:
        _check_error(identity_scope,
            f"check: REFUSED — {len(active)} injection(s) registered, but "
            f"--require {require} was set."
            + (f" ({len(retired)} retired registration(s) are in history scope "
               f"but are not live evidence.)" if retired else ""))
        return 1

    # Unknown states are refused FIRST and distinctly (#950). They are the
    # dangerous case — fail-closed is right and unchanged — but their refusal
    # names the format-skew possibility, because that is the one the next
    # reader spends twenty minutes diagnosing. The remedy text never reads as
    # permission: an unknown entry is treated as armed and MUST be resolved.
    if unknown:
        # Distinct states first (order-stable for a deterministic message).
        states = sorted({str(e.get("state")) for e in unknown})
        st_list = ", ".join(repr(s) for s in states)
        names = ", ".join(
            f"{e['path']} (state {str(e.get('state'))!r}, from "
            f"{e.get('_source', 'this lane')})" for e in unknown)
        _check_error(identity_scope,
            f"check: REFUSED — {len(unknown)} of {len(active)} active "
            f"registration(s) are in a state this build of redproof.py cannot "
            f"read ({st_list}): {names}. This build knows only "
            f"{', '.join(repr(s) for s in KNOWN_STATES)}. An entry in an "
            f"unknown state is treated as armed (begun-but-unrestored) and "
            f"REFUSED — never as restored — so an injection written by a "
            f"future format cannot land silently. If this branch changed the "
            f"registry format, the pre-merge tool is reading post-lane data it "
            f"cannot classify: re-run the gate from a build that carries the "
            f"branch's change, or resolve the entries by hand. This message is "
            f"not permission to merge.")
        return 1

    if armed:
        names = ", ".join(
            f"{e['path']} (from {e.get('_source', 'this lane')})" for e in armed)
        _check_error(identity_scope,
            f"check: REFUSED — {len(armed)} of {len(active)} begun-but-"
            f"unrestored injection(s): {names}. An armed entry means the "
            f"red-proof never completed (begin without restore). Run `restore` "
            f"on each or `forget` a spurious begin.")
        return 1

    if expectation_drift:
        _check_error(identity_scope,
            "check: REFUSED — a registered injection has an expectation "
            "source that was not stable across the injection:\n  "
            + "\n  ".join(expectation_drift) +
            "\nThe expectation must remain byte-identical and distinct from "
            "the injected subject.\n" + _EXPECTATION_DRIFT_REARM)
        return 1

    try:
        rep = scan_history(cwd, entries, base)
    except RedproofError as exc:
        _check_error(identity_scope, f"check: FAULT — {exc}")
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
        _check_error(identity_scope,
            "check: REFUSED — hand-off blocked. A registered injection is "
            "still present in the working tree:\n" + "\n".join(lines) +
            "\nRestore it (cp from the lane-private snapshot) before committing.")
        return 1

    # #877: a restored source whose downstream bundle is stale. The bundle a
    # guard serves was built from the injected bytes; restoring only the
    # source leaves the bundle holding the defect while check read clean.
    stale_bundles = bundle_stale_findings(root, entries)
    if stale_bundles:
        lines = []
        for f in stale_bundles:
            lines.append(
                f"  {f['path']}: restored, but client/dist is STALE "
                f"({f['note']}). The bundle a guard serves was built from "
                f"bytes that disagree with the restored source, so it may "
                f"still hold the injection.")
        fix = stale_bundles[0].get("fix") or "run `just build-client`"
        _check_error(identity_scope,
            "check: REFUSED — restored source(s) with a stale downstream "
            "bundle:\n" + "\n".join(lines) +
            f"\nRebuild after restore ({fix}), then check again. #877")
        return 1

    if rep["hits"]:
        lines = [f"  {h['commit'][:12]} {h['path']} — {h['subject']!r} "
                 f"(hint: {h['hint']!r})" for h in rep["hits"]]
        _check_error(identity_scope,
            f"check: REFUSED — the working tree is clean, but {len(rep['hits'])} "
            f"commit(s) on this branch still hold a recorded injection:\n"
            + "\n".join(lines) +
            "\nCommitting mid-injection is correct — COMMIT INCREMENTALLY exists "
            "because lanes get killed without warning — but the branch cannot "
            "merge as it stands: a merge makes the defect reachable from master "
            "forever, where bisect, blame and cherry-pick all resurrect it. "
            "Tell the coordinator to SQUASH this branch at merge (the fix for "
            "this branch only), or rebase the injection out yourself. #710")
        return 1

    restored = [e for e in active if e.get("state") == RESTORED]
    if not restored:
        # Retired-only, and the scan cleared them. Distinct from "restoration
        # clean" (nothing was restored here) and from "no evidence" (bytes WERE
        # searched for, in a range this run printed).
        print(f"check: no live injection — {len(retired)} retired "
              f"registration(s) only (role: {role}); their recorded bytes are "
              f"absent from this branch's commits. Restoration was not "
              f"evaluated, because no live injection is registered.")
        print(identity_scope)
        return 0
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
    if retired:
        print(f"retired: {len(retired)} withdrawn registration(s) were also "
              f"searched for in history and found in no commit (#942).")
    print("tool scope: red-proof semantics and production reach were NOT verified.")
    if test_like:
        print("WARNING: test-like targets are valid when test/guard tooling is "
              "the named production subject; otherwise this does not establish "
              "a production injection.")
    if listed:
        print(listed)
    print(identity_scope)
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
    ap.add_argument("--expectation", action="append", default=[], metavar="PATH",
                    help="begin: independent repo-relative file holding the "
                    "expectation; repeat for multiple files")
    ap.add_argument("--require", type=int, default=0,
                    help="check: refuse if fewer than N injections are registered")
    ap.add_argument("--base", default=None,
                    help=f"check: base ref for the history scan (default: first "
                         f"of {', '.join(DEFAULT_BASES)} that resolves)")
    ap.add_argument("--lane", default=None,
                    help="resolve a NAMED launch identity for every verb; an "
                         "explicit value wins over DREAMWORK_LANE_ID. Without "
                         "one, write verbs use the environment and check "
                         "enumerates every identity dir when the environment "
                         "is absent (#895).")
    ap.add_argument("--cwd", default=None, help="derive for this directory")
    args = ap.parse_args(argv)
    cwd = Path(args.cwd) if args.cwd else None

    try:
        if args.verb == "check":
            return check(cwd, require=args.require, base=args.base, lane=args.lane)
        if args.path is None:
            ap.error(f"{args.verb} requires a path argument")
        if args.verb == "begin":
            return begin(cwd, args.path, args.expectation, lane=args.lane)
        if args.verb == "restore":
            return restore(cwd, args.path, lane=args.lane)
        if args.verb == "forget":
            return forget(cwd, args.path, lane=args.lane)
    except RedproofError as exc:
        sys.stderr.write(f"{args.verb}: FAULT — {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
