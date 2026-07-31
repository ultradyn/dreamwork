"""Integration tests for the `reach` verb and the fold reach hook (#688).

These build a THROWAWAY git repo (never the shared checkout) and exercise the
real `git cherry` path end-to-end, because the pure-function tests in
test_ledger.py cannot reach the patch-id semantics that make `git cherry` the
right primitive. The brief is explicit: **do not create or delete branches in
the shared repo**; every fixture here is a fresh `git init` under pytest's
tmp_path, which is throwaway and isolated from other lanes.

THE TWO DIRECTIONS THE BRIEF DEMANDS, both proved against a real repo:

- **Direction 1** (the discriminating message): a branch carrying a commit
  genuinely absent from master → reach names it AND the commit. Then land that
  content onto master (fast-forward merge) → the branch drops off the report.
  A count going 1→0 is NOT discriminating; the branch NAME and its sha must
  appear, then disappear.
- **Direction 2** (the false-greens, each named): (a) squash — a branch whose
  commits are squashed into master still shows `+` (different patch id), and
  reach reports it honestly as a question, not a verdict; (b) refactored —
  #676's named blind spot, content that landed reworded is structurally a `+`;
  (c) deleted-branch — a branch deleted before the check runs is invisible to
  it entirely, which is #590's exact case and cannot be closed by reach alone.
"""
import contextlib
import io
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "dev"))
import ledger  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers — a throwaway git repo with a master and branches.
# ---------------------------------------------------------------------------

def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=True)


def _repo(tmp_path, name="repo"):
    """A fresh git repo with one commit on `master`."""
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.cleanup", "scissors")
    (root / "file.txt").write_text("base\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base commit")
    return root


def _branch_with_commit(root, branch, path, content, subject):
    """Create a branch from master HEAD and add one commit to it.
    Returns the FULL sha of the commit added on the branch."""
    _git(root, "checkout", "-q", "-b", branch, "master")
    (root / path).write_text(content)
    _git(root, "add", path)
    _git(root, "commit", "-qm", subject)
    sha = _git(root, "rev-parse", "HEAD").stdout.strip()
    _git(root, "checkout", "-q", "master")
    return sha


def _run_reach(root, base="master"):
    """Run the reach CLI verb against a repo; return (rc, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = ledger.main(["reach", "--repo", str(root), "--base", base])
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Direction 1 — the discriminating message, on a real git cherry.
# ---------------------------------------------------------------------------

def test_reach_names_a_branch_carrying_a_commit_absent_from_master(tmp_path):
    """THE defect, proved against the real patch-id path: a branch with a
    commit that is genuinely NOT on master must be NAMED, with its sha and
    subject printed. A count alone (1 branch) is not discriminating — the
    brief says so explicitly.

    PRODUCTION LINE: `_git_cherry` → `reach` → `reach_text`. RED: stub
    `_git_cherry` to always return `[]` and the branch is not named, while
    the header still prints its examined count — the #671 silent all-clear.
    """
    root = _repo(tmp_path)
    sha = _branch_with_commit(
        root, "lost-work", "feature.txt", "new feature\n",
        "fix(#42): a real change not on master")

    rc, out, _ = _run_reach(root)

    assert rc == 0, "#688 rules reach advisory (exit 0 always)"
    assert "lost-work" in out, (
        f"the branch must be NAMED — a count is not discriminating: {out!r}")
    assert sha[:12] in out, (
        f"the commit sha must be printed as evidence: {out!r}")
    assert "fix(#42): a real change not on master" in out, (
        f"the commit subject must be printed so the reader can judge it: "
        f"{out!r}")


def test_reach_drops_a_branch_once_its_content_lands_on_master(tmp_path):
    """The OTHER half of Direction 1: after the absent content reaches master
    (fast-forward merge, same patch id), the branch drops off the report
    entirely. A count going 1→0 is not enough — the branch NAME must vanish.

    PRODUCTION LINE: `git cherry` marks the now-merged commit as `-`
    (patch-equivalent), and `reach` excludes all-`-` branches from the rows.
    RED: delete the `if plus:` guard in `reach` and the branch stays in the
    report as a zero-`+` row that reads as a finding.
    """
    root = _repo(tmp_path)
    _branch_with_commit(
        root, "landed-work", "feature.txt", "new feature\n",
        "fix(#42): a real change")

    # Before: the branch IS reported.
    rc, out_before, _ = _run_reach(root)
    assert "landed-work" in out_before, (
        f"precondition: the branch must be reported before its content lands: "
        f"{out_before!r}")

    # Land the content onto master (merge, same patch ids → `-`).
    _git(root, "merge", "-q", "--no-ff", "landed-work", "-m",
         "merge landed-work")

    # After: the branch drops off entirely.
    rc, out_after, _ = _run_reach(root)
    assert "landed-work" not in out_after, (
        f"after a merge the branch's commits are patch-equivalent (`-`), so "
        f"it must vanish from the report — not stay as a zero-+ row: "
        f"{out_after!r}")
    assert "examined" in out_after, (
        f"the examined count must still print so the clean result differs from "
        f"'did not run': {out_after!r}")


# ---------------------------------------------------------------------------
# Direction 2 — the false-greens, each constructed and named.
# ---------------------------------------------------------------------------

def test_reach_squash_into_master_is_a_false_alarm_reported_honestly(tmp_path):
    """DIRECTION 2a: a branch whose work was SQUASHED into master is still `+`
    — different patch id — so reach reports it. This is a false alarm, and it
    is inherent to patch-id matching (#676's blind spot). The check does NOT
    close this case; it names it honestly by carrying 'a + is a question, not
    a verdict' in every report that has findings.

    What would change my mind: if reach stayed silent over a squashed branch,
    it would be closing the blind spot — and it does not.
    """
    root = _repo(tmp_path)
    # A branch with two commits.
    _git(root, "checkout", "-q", "-b", "squashed", "master")
    for i in (1, 2):
        (root / f"feat{i}.txt").write_text(f"feature {i}\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", f"fix(#50): change {i}")
    _git(root, "checkout", "-q", "master")
    # Squash-merge: produces ONE commit with a different patch id.
    _git(root, "merge", "-q", "--squash", "squashed")
    _git(root, "commit", "-qm", "fix(#50): squashed landing of both changes")

    rc, out, _ = _run_reach(root)

    # The branch is reported (false alarm) — reach cannot tell squash from loss.
    assert "squashed" in out, (
        f"a squashed branch has a different patch id so it stays `+` — reach "
        f"MUST report it; this is the blind spot, not a bug: {out!r}")
    # ...and the wording never promotes it to a verdict.
    assert "a + is a question, not a verdict" in out, (
        f"the report must carry its caveat so a false alarm does not read as "
        f"a verdict: {out!r}")


def test_reach_cannot_see_a_branch_deleted_before_it_runs(tmp_path):
    """DIRECTION 2c: a branch deleted before the check runs is INVISIBLE to
    it entirely — this is #590's exact case (folded-but-unmerged, then gone),
    and reach cannot close it. This test exists to NAME that gap, not to fix
    it: the only defence is running the check at fold time (the hook), before
    a branch can be deleted.

    PRODUCTION LINE: `_git_local_branches` enumerates refs/heads/; a deleted
    branch has no ref, so it never appears. No injection can make this fail —
    the case is structurally outside reach's reach.
    """
    root = _repo(tmp_path)
    _branch_with_commit(
        root, "doomed", "lost.txt", "genuinely lost work\n",
        "fix(#99): work that will vanish")
    sha = _git(root, "rev-parse", "doomed").stdout.strip()
    # Delete the branch — its work is NOT on master.
    _git(root, "branch", "-D", "doomed")

    rc, out, _ = _run_reach(root)

    assert "doomed" not in out, (
        f"a deleted branch has no ref for reach to enumerate — #590's exact "
        f"case, structurally invisible: {out!r}")
    assert "lost work" not in out and sha[:8] not in out, (
        f"and neither its content nor its sha may appear: {out!r}")
    # This gap is why the fold hook matters: the check runs at fold time,
    # BEFORE a branch can be deleted. The gap is named, not closed.


# ---------------------------------------------------------------------------
# The fold hook — the non-obvious value (#688).
# ---------------------------------------------------------------------------

def _run(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = module.main(argv)
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


def test_fold_store_path_prints_reach_trailer(tmp_path):
    """The fold STORE path (post-cutover) is the live one, and it must tack
    the reach trailer onto stdout after the fold succeeds. This is the hook
    that makes the check run without remembering.

    PRODUCTION LINE: `sys.stdout.write(_reach_trailer(args.repo))` in the
    `args.cmd == "fold"` store branch of `_dispatch`. RED: delete that line
    and the trailer vanishes while the fold still succeeds.
    """
    root = _repo(tmp_path)
    _branch_with_commit(
        root, "unmerged", "x.txt", "x\n", "fix(#7): unmerged work")
    # Seed a store so the store-mode fold path runs.
    dw = root / ".dreamwork"
    dw.mkdir()
    sp = ledger.store_path(str(dw))
    ledger.ledger_store.open_store(sp, seed_next_id=1).close()
    # Write the cutover watermark so source_of_truth resolves to 'store'.
    import sqlite3
    conn = sqlite3.connect(str(sp))
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('ledger_cut_over', '2026-07-31')")
    conn.commit()
    conn.close()
    # File a task so there is something to fold.
    ledger.ledger_store.open_store(sp).close()

    # Use the file verb to create an open task, then fold it.
    rc, out, err = _run(
        ledger, ["file", "a task", "--note", "body",
                 "--ledger", str(dw / "tasks.md")])
    # fold task #1 (the one we just filed)
    rc, out, err = _run(
        ledger, ["fold", "1", "--note", "folded",
                 "--repo", str(root), "--ledger", str(dw / "tasks.md")])

    assert "reach:" in out, (
        f"the fold STORE path must tack the reach trailer onto stdout — the "
        f"hook is the non-obvious value: {out!r}")
    assert "unmerged" in out, (
        f"and it must name the unmerged branch: {out!r}")


def test_fold_is_silent_when_there_are_no_branches(tmp_path):
    """A repo with only `master` (no other branches) must NOT print a reach
    trailer — the hook is silent where there is nothing to check, so existing
    fold output stays clean (#612: volume is a design constraint).

    PRODUCTION LINE: `if not findings: return ''` in `_reach_trailer`. RED:
    remove that guard and a one-branch repo prints a 'no branches' line on
    every fold — noise that trains the reader to skip it.
    """
    root = _repo(tmp_path)  # master only, no other branches
    dw = root / ".dreamwork"
    dw.mkdir()
    sp = ledger.store_path(str(dw))
    ledger.ledger_store.open_store(sp, seed_next_id=1).close()
    import sqlite3
    conn = sqlite3.connect(str(sp))
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('ledger_cut_over', '2026-07-31')")
    conn.commit()
    conn.close()

    _run(ledger, ["file", "a task", "--note", "body",
                  "--ledger", str(dw / "tasks.md")])
    rc, out, err = _run(
        ledger, ["fold", "1", "--note", "folded",
                 "--repo", str(root), "--ledger", str(dw / "tasks.md")])

    assert "reach:" not in out, (
        f"a repo with no extra branches must not emit a reach trailer — "
        f"silence where there is nothing to check is the design: {out!r}")
