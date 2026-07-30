"""#539 — evidence-capture guards must not write screenshots/ on a plain run.

mdquote.mjs / mdtable.mjs are evidence-capture guards: each used to re-capture
COMMITTED PNGs under screenshots/ on every run. Headless rendering is byte-
unstable, so a passing run dirtied the tree — a side effect in the wrong
direction. The fix: the committed-PNG writes move behind an explicit opt-in
env flag (DW_UPDATE_EVIDENCE=1); a plain run captures only to the guard's
scratch outdir (OUT), never into screenshots/. Nothing reads the committed
PNGs (the verdicts assert against the live DOM via page.evaluate) — they are
pure evidence for the lane.

CONTRACT THIS BINDS (lexical, grep-shape per the brief):
  every `screenshots` path-token write in dev/capture/*.mjs must sit inside a
  block opened by an `if` whose condition names the evidence flag, within
  WINDOW lines above the write. A COMMENT naming the flag does NOT satisfy
  this — only an executable `if (...)` does — so removing the gate (the
  sabotage) makes the write lose its nearby flag-bearing `if` and the test
  FAILs. The playwright import path (`.../headless-browser-screenshots/...`)
  is not a match: it carries no quoted standalone `'screenshots'` token.

PRECONDITIONS (derived at runtime, asserted non-empty so the check is not
vacuous — a check over an empty subject passes by accident):
  - the committed screenshots set (`git ls-files screenshots`, .png only) is
    non-empty — these are the files a plain run must not dirty;
  - at least one dev/capture guard references the `screenshots` path token —
    else there is no write site to gate and the offenders loop is vacuous.

Red-proof (the repo's rule): cp-snapshot mdquote.mjs, drop the env gate around
its screenshots write (the `if (process.env.DW_UPDATE_EVIDENCE === '1')` → a
bare unconditional block), watch this test FAIL naming mdquote.mjs, cp-restore
byte-identical (never `git checkout`). A green red-run is a finding — if the
sabotage still passes, the check is wrong (likely binding on a comment rather
than the gate), and must be reported, not relieved.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAP = ROOT / "dev" / "capture"

ENV_FLAG = "DW_UPDATE_EVIDENCE"      # the opt-in env var
FLAG_MARKER = "UPDATE_EVIDENCE"       # substring covering the env name / a const
# a `screenshots` path component as a quoted token in a path join — the
# write-site shape (`join(..., 'screenshots', ...)`). The playwright import
# path (`.../headless-browser-screenshots/...`) does NOT match it.
SHOT_TOKEN = re.compile(r"['\"]screenshots['\"]")
# an executable `if` whose condition names the flag. A comment (`// if ...`)
# does not match — the line must start (after indent) with `if (`; that is what
# makes this bind on the GATE, not a nearby comment that names the flag.
IF_GATE = re.compile(r"^\s*if\s*\(.*" + FLAG_MARKER)
WINDOW = 10  # lines above a screenshots write that must hold its flag gate


def _committed_screenshots():
    """Committed screenshots/**/*.png, derived at runtime via git (tracked
    files only — untracked scratch excluded so a bare worktree is detected as
    vacuous, not silently passed)."""
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "screenshots"], text=True,
    )
    return [p for p in out.splitlines() if p.endswith(".png")]


def _guard_files():
    return sorted(CAP.glob("*.mjs"))


def _ungated_screenshots_writes():
    """(guard, lineno, line) for every screenshots path-token write that has
    no flag-bearing `if` gate within WINDOW lines above it."""
    offenders = []
    for g in _guard_files():
        lines = g.read_text().splitlines()
        for i, line in enumerate(lines):
            if not SHOT_TOKEN.search(line):
                continue
            if line.lstrip().startswith("//"):  # a write is executable code
                continue
            lo = max(0, i - WINDOW)
            gated = any(IF_GATE.search(lines[j]) for j in range(lo, i))
            if not gated:
                offenders.append((g.name, i + 1, line.strip()))
    return offenders


def test_committed_screenshots_nonempty():
    """Precondition: there ARE committed PNGs a plain run must not dirty.
    Empty → the tree-clean contract has no subject, so fail loud with why."""
    shots = _committed_screenshots()
    assert shots, (
        "no committed screenshots/**/*.png (git ls-files) — the tree-clean "
        "contract has no subject; vacuous until evidence is committed"
    )


def test_screenshots_writes_are_gated_by_evidence_flag():
    # precondition 1: committed evidence exists (else dirtying nothing matters)
    shots = _committed_screenshots()
    assert shots, "precondition: committed screenshots set is non-empty (else vacuous)"
    # precondition 2: at least one guard writes screenshots (else the offenders
    # loop finds no token and passes by accident — the vacuous-shrink trap)
    token_count = sum(
        1 for g in _guard_files()
        for line in g.read_text().splitlines()
        if SHOT_TOKEN.search(line) and not line.lstrip().startswith("//")
    )
    assert token_count > 0, (
        "precondition: no dev/capture guard references the screenshots path "
        "token — there is no write site to gate; the contract is vacuous"
    )
    offenders = _ungated_screenshots_writes()
    assert not offenders, (
        f"ungated screenshots/ writes (must sit inside an `if` naming "
        f"{ENV_FLAG} within {WINDOW} lines above):\n" +
        "\n".join(f"  {name}:{ln}: {code}" for name, ln, code in offenders)
    )


def test_evidence_flag_is_strict_opt_in():
    """The flag must be a strict === '1' opt-in, so an unset/plain run (the
    common case) never refreshes and a stray env value cannot satisfy it.
    Binds the env read shape against a loose/truthy gate."""
    seen = False
    for g in _guard_files():
        src = g.read_text()
        if ENV_FLAG not in src:
            continue
        seen = True
        for m in re.finditer(r"process\.env\." + ENV_FLAG, src):
            tail = src[m.start():m.start() + 80]
            assert "=== '1'" in tail or '=== "1"' in tail, (
                f"{g.name}: {ENV_FLAG} read without strict === '1' opt-in: {tail!r}")
    assert seen, (
        "precondition: no guard references the evidence flag — the opt-in "
        "contract has no subject; vacuous"
    )
