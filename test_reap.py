#!/usr/bin/env python3
"""Red-first integration tests for the checked lane-worktree reaper (#686)."""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent
CLI = REPO / "dev" / "reap.py"
SWEEP_CLI = REPO / "dev" / "reap_sweep.py"


def _load_reap():
    loader = importlib.machinery.SourceFileLoader("lane_reap", str(CLI))
    spec = importlib.util.spec_from_loader("lane_reap", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CLI), *(str(arg) for arg in args)],
        capture_output=True,
        text=True,
    )


def _run_sweep(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SWEEP_CLI), *(str(arg) for arg in args)],
        capture_output=True,
        text=True,
    )


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        stderr=subprocess.DEVNULL,
        text=True,
    ).strip()


def _write_gate_breadcrumb(root: Path, worktree: Path, pid: int) -> Path:
    breadcrumb = root / ".dreamwork" / "gate-in-flight.json"
    breadcrumb.parent.mkdir()
    breadcrumb.write_text(
        json.dumps({
            "gate_worktree": str(worktree.resolve()),
            "phase": "named-tests",
            "pid": pid,
        }) + "\n",
        encoding="utf-8",
    )
    return breadcrumb


@pytest.fixture
def lane(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / ".gitignore").write_text(
        "__pycache__/\n.dreamwork/applied.md\n.dreamwork/expedite\n"
        ".dreamwork/ledger.sqlite3\n"
        "*.tmp.*\nnode_modules/\n",
        encoding="utf-8",
    )
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "tracked.txt")
    _git(root, "commit", "-qm", "base")
    worktree = tmp_path / "lane"
    _git(root, "worktree", "add", "-q", "-b", "wt/lane", str(worktree), "master")
    return root, worktree


def test_tracked_dirty_path_refuses_and_names_what_would_be_lost(lane):
    _, worktree = lane
    (worktree / "tracked.txt").write_text("unfinished\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 1, result.stdout
    assert f"path={worktree.resolve()}" in result.stderr
    assert "tracked-dirty=1" in result.stderr
    assert "untracked=0" in result.stderr
    assert "ignored=0" in result.stderr
    assert "tracked.txt" in result.stderr


def test_index_only_change_is_tracked_dirty(lane):
    _, worktree = lane
    (worktree / "tracked.txt").write_text("staged only\n", encoding="utf-8")
    _git(worktree, "add", "tracked.txt")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert "tracked-dirty=1" in result.stderr
    assert "tracked.txt" in result.stderr


def test_brief_and_ignored_cache_do_not_fire_the_gate(lane):
    _, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert f"path={worktree.resolve()}" in result.stdout
    assert "tracked-dirty=0" in result.stdout
    # #760: untracked and ignored are split, not collapsed. BRIEF.md is the one
    # expected untracked scratch, so it is not named; the cache is ignored.
    assert "untracked=1" in result.stdout
    assert "ignored=1" in result.stdout
    assert "ignored: examined 1 file; 1 disposable, 0 NOT disposable" in result.stdout
    assert "unmerged-commits=0" in result.stdout
    assert "NOTE:" not in result.stderr


def test_non_disposable_ignored_file_refuses_removal_and_names_path(lane):
    root, worktree = lane
    evidence = worktree / ".dreamwork" / "applied.md"
    evidence.parent.mkdir()
    evidence.write_text("actor=coordinator-drain\n", encoding="utf-8")

    result = _run(worktree)

    assert result.returncode == 1
    assert "ignored=1" in result.stderr
    assert "ignored: examined 1 file; 0 disposable, 1 NOT disposable" in result.stderr
    assert "REFUSE: ignored path would be lost: .dreamwork/applied.md" in result.stderr
    assert worktree.exists()
    assert str(worktree.resolve()) in _git(root, "worktree", "list", "--porcelain")


def test_empty_ledger_is_disposable_by_exact_lifecycle_path(lane):
    _, worktree = lane
    ledger = worktree / ".dreamwork" / "ledger.sqlite3"
    ledger.parent.mkdir()
    ledger.touch()

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "ignored: examined 1 file; 1 disposable, 0 NOT disposable" in result.stdout


def test_empty_ledger_ownership_is_held_through_removal(lane, monkeypatch):
    root, worktree = lane
    ledger = worktree / ".dreamwork" / "ledger.sqlite3"
    ledger.parent.mkdir()
    ledger.touch()
    reap = _load_reap()
    real_git = reap._git
    lock_probe = (
        "import fcntl, os, sys; "
        "fd = os.open(sys.argv[1], os.O_RDWR); "
        "\ntry: fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)"
        "\nexcept BlockingIOError: raise SystemExit(75)"
    )
    observed = {}

    def probe_at_remove(cwd, *args):
        if args[:3] == ("worktree", "remove", "--force"):
            probe = subprocess.run([sys.executable, "-c", lock_probe, str(ledger)])
            observed["during_remove"] = probe.returncode
            return subprocess.CompletedProcess(args, 0, b"", b"")
        return real_git(cwd, *args)

    monkeypatch.setattr(reap, "_git", probe_at_remove)

    assert reap.reap(str(worktree)) == 0
    assert observed == {"during_remove": 75}
    assert subprocess.run([sys.executable, "-c", lock_probe, str(ledger)]).returncode == 0
    assert str(worktree.resolve()) in _git(root, "worktree", "list", "--porcelain")


def test_empty_ignored_sentinel_refuses_removal_and_names_path(lane):
    root, worktree = lane
    sentinel = worktree / ".dreamwork" / "expedite"
    sentinel.parent.mkdir()
    sentinel.touch()

    result = _run(worktree)

    assert result.returncode == 1, result
    assert "ignored: examined 1 file; 0 disposable, 1 NOT disposable" in result.stderr
    assert "REFUSE: ignored path would be lost: .dreamwork/expedite" in result.stderr
    assert worktree.exists()
    assert str(worktree.resolve()) in _git(root, "worktree", "list", "--porcelain")


def test_unforeseen_ignored_file_type_falls_through_allowlist_and_refuses(lane):
    _, worktree = lane
    (worktree / "red-proof.tmp.unforeseen").write_text("unknown kind\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert "1 NOT disposable: red-proof.tmp.unforeseen" in result.stderr
    assert "REFUSE: ignored path would be lost: red-proof.tmp.unforeseen" in result.stderr


def test_handwritten_note_inside_pycache_is_not_hidden_by_directory_name(lane):
    _, worktree = lane
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "handwritten-note.md").write_text("keep me\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert "1 NOT disposable: __pycache__/handwritten-note.md" in result.stderr
    assert (
        "REFUSE: ignored path would be lost: __pycache__/handwritten-note.md"
        in result.stderr
    )


def test_ignored_symlink_does_not_report_files_beyond_the_worktree(lane, tmp_path):
    _, worktree = lane
    outside = tmp_path / "coordinator-secret-report.md"
    outside.write_text("not in the lane\n", encoding="utf-8")
    dependencies = worktree / "node_modules"
    dependencies.mkdir()
    (dependencies / "external-report").symlink_to(outside)

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "ignored: examined 1 file; 1 disposable, 0 NOT disposable" in result.stdout
    assert "coordinator-secret-report.md" not in result.stdout


def test_untracked_deliverable_is_named_and_distinguishable_from_cache_only(lane):
    """#760 direction 1: the discriminating case the collapsed counter hid.

    A lane holding an untracked deliverable plus expected scratch must NOT read
    identically to one holding only scratch + cache. The split counters differ
    and — critically — the deliverable path is NAMED, which the count alone
    never was.
    """
    _, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    deliverable = worktree / ".dreamwork" / "lane-999-report.md"
    deliverable.parent.mkdir()
    deliverable.write_text("# deliverable about to be lost\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr  # untracked paths stay report-only
    assert "untracked=2" in result.stdout
    assert "ignored=0" in result.stdout
    # The deliverable path is named: a count alone cannot say WHICH file, and
    # that is the signal that turns a number into something actionable.
    assert ".dreamwork/lane-999-report.md" in result.stderr
    # BRIEF.md is expected scratch; it must NOT be named as unexpected.
    assert "BRIEF.md" not in result.stderr


def test_expected_scratch_and_ignored_read_identically_under_split(lane):
    """#760 direction 1 complement: the SAFE lane is still clean and unnamed.

    The scratch+cache lane must read with the SAME counters as before the fix
    (untracked=1 ignored=1), and no NOTE lines, so a coordinator's healthy
    baseline is preserved.
    """
    _, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "untracked=1" in result.stdout
    assert "ignored=1" in result.stdout
    assert "NOTE:" not in result.stderr


def test_non_worktree_is_unknown_not_clean(tmp_path):
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()

    result = _run("--check", ordinary)

    assert result.returncode == 2
    assert f"path={ordinary.resolve()}" in result.stderr
    assert "tracked-dirty=unknown" in result.stderr
    assert "untracked=unknown" in result.stderr
    assert "ignored=unknown" in result.stderr
    assert "not a registered linked worktree" in result.stderr


def test_zero_ignored_population_is_visibly_not_an_all_clear(lane):
    _, worktree = lane

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "ignored=0" in result.stdout
    assert "ignored: examined 0 files; NOT an all-clear" in result.stdout


def test_git_status_failure_is_unknown_not_clean(tmp_path, monkeypatch, capsys):
    target = tmp_path / "lane"
    target.mkdir()
    reap = _load_reap()
    monkeypatch.setattr(reap, "_registered_worktrees",
                        lambda path: [tmp_path.resolve(), path])
    monkeypatch.setattr(reap, "_status_paths", lambda path: None)

    rc = reap.reap(str(target), check_only=True)

    err = capsys.readouterr().err
    assert rc == 2
    assert "tracked-dirty=unknown" in err
    assert "untracked=unknown" in err
    assert "ignored=unknown" in err
    assert "git status failed" in err


def test_clean_branch_with_unmerged_commit_refuses(lane):
    _, worktree = lane
    (worktree / "landed.txt").write_text("committed lane output\n", encoding="utf-8")
    _git(worktree, "add", "landed.txt")
    _git(worktree, "commit", "-qm", "feat(#686): lane output")
    sha = _git(worktree, "rev-parse", "--short=12", "HEAD")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert "tracked-dirty=0" in result.stderr
    assert "untracked=0" in result.stderr
    assert "ignored=0" in result.stderr
    assert "unmerged-commits=1" in result.stderr
    assert sha in result.stderr
    assert "feat(#686): lane output" in result.stderr


def test_force_names_every_discarded_path_and_removes_worktree(lane):
    root, worktree = lane
    (worktree / "tracked.txt").write_text("unfinished\n", encoding="utf-8")
    (worktree / "BRIEF.md").write_text("scratch\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run("--force", worktree)

    assert result.returncode == 0, result.stderr
    assert "FORCE: discarding tracked path: tracked.txt" in result.stderr
    assert "FORCE: discarding untracked path: BRIEF.md" in result.stderr
    assert "FORCE: discarding ignored path: __pycache__/" in result.stderr
    assert not worktree.exists()
    assert str(worktree.resolve()) not in _git(root, "worktree", "list", "--porcelain")


def test_clean_worktree_is_removed_after_reported_check(lane):
    root, worktree = lane

    result = _run(worktree)

    assert result.returncode == 0, result.stderr
    assert "tracked-dirty=0" in result.stdout
    assert "untracked=0" in result.stdout
    assert "ignored=0" in result.stdout
    assert "unmerged-commits=0" in result.stdout
    assert "removed" in result.stdout
    assert not worktree.exists()
    assert str(worktree.resolve()) not in _git(root, "worktree", "list", "--porcelain")


@pytest.mark.parametrize("force", [False, True])
def test_live_gate_scratch_is_refused_even_with_force(lane, force):
    root, worktree = lane
    breadcrumb = _write_gate_breadcrumb(root, worktree, os.getpid())

    result = _run(*(("--force",) if force else ()), worktree)

    assert f"active landing gate breadcrumb {breadcrumb}" in result.stderr
    assert "refusing to reap in-flight gate scratch" in result.stderr
    assert result.returncode == 1
    assert worktree.exists()
    assert str(worktree.resolve()) in _git(root, "worktree", "list", "--porcelain")


def test_dead_gate_breadcrumb_leaves_abandoned_scratch_reapable(lane, tmp_path):
    root, _ = lane
    abandoned = tmp_path / ".gate-abandoned"
    _git(
        root, "worktree", "add", "-q", "-b", "wt/abandoned",
        str(abandoned), "master",
    )
    dead_pid = 2**30
    with pytest.raises(ProcessLookupError):
        os.kill(dead_pid, 0)
    _write_gate_breadcrumb(root, abandoned, dead_pid)

    result = _run(abandoned)

    assert result.returncode == 0, result.stderr
    assert "removed" in result.stdout
    assert not abandoned.exists()
    assert str(abandoned.resolve()) not in _git(root, "worktree", "list", "--porcelain")


def test_real_lane_scratch_is_removed_without_force(lane):
    """#762: the happy path must actually COMPLETE for a real lane.

    Every lane holds an untracked ``BRIEF.md`` (the coordinator writes it and
    never tracks it) and an ignored ``__pycache__/``. ``git worktree remove``
    refuses on ANY untracked file, so a tool that passes ``--force`` to git only
    when its own ``--force`` is set cannot remove a lane whose gate just PASSED.
    The existing suite proved the gate's verdict but never the outcome (#671 in
    the suite itself): this test asserts the directory is GONE and the worktree
    is deregistered — the discriminating evidence is the worktree's absence, not
    a changed exit code.
    """
    root, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run(worktree)

    assert result.returncode == 0, result.stderr
    assert "tracked-dirty=0" in result.stdout
    assert "untracked=1" in result.stdout
    assert "ignored=1" in result.stdout
    assert "unmerged-commits=0" in result.stdout
    assert "removed" in result.stdout
    # The discriminating evidence: the gate passed AND the removal completed.
    assert not worktree.exists()
    assert str(worktree.resolve()) not in _git(root, "worktree", "list", "--porcelain")


def test_running_process_cwd_refuses_then_dead_process_allows_check(lane):
    root, worktree = lane
    process = subprocess.Popen(
        ["codex", "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
        cwd=worktree,
    )
    reap = _load_reap()
    try:
        positive = reap.worktree_liveness(worktree)
        assert positive.unknown == ()
        assert process.pid in positive.pids
        result = _run(worktree)
        assert result.returncode == 1
        assert "active process cwd inside worktree at removal time" in result.stderr
        assert str(process.pid) in result.stderr
        assert worktree.exists()
    finally:
        process.terminate()
        process.wait(timeout=5)

    negative = reap.worktree_liveness(worktree)
    assert negative == reap.WorktreeLiveness((), ())
    result = _run("--check", worktree)
    assert result.returncode == 0, result.stderr
    assert str(worktree.resolve()) in _git(root, "worktree", "list", "--porcelain")


def test_periodic_sweep_reaps_only_gate_passed_fixture_and_reports_every_skip(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-qm", "base")

    paths = {}
    for name in ("clean", "dirty", "held", "live"):
        path = tmp_path / name
        _git(root, "worktree", "add", "-q", "-b", f"wt/{name}", str(path), "master")
        paths[name] = path
    (paths["dirty"] / "tracked.txt").write_text("unfinished\n", encoding="utf-8")
    holds = tmp_path / "holds.txt"
    holds.write_text("held\n", encoding="utf-8")
    process = subprocess.Popen(
        ["codex", "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
        cwd=paths["live"],
    )
    try:
        result = _run_sweep("--repo", root, "--holds", holds, "--apply")
        assert result.returncode == 0, result.stderr
        assert not paths["clean"].exists(), "gate-passing fixture was not reaped"
        assert paths["dirty"].exists(), "gate-refused fixture was removed"
        assert paths["held"].exists(), "held worktree was removed"
        assert paths["live"].exists(), "live worktree was removed"
        assert "REFUSED dirty: REFUSE: tracked path would be lost: tracked.txt" in result.stdout
        assert "HELD held:" in result.stdout
        assert f"LIVE live: active process cwd pids={process.pid}" in result.stdout
        assert "SUMMARY mode=apply examined=4 reaped=1 reapable=0 refused=1 held=1 live=1" in result.stdout
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_periodic_sweep_missing_hold_list_fails_closed_before_scan(lane, tmp_path):
    root, worktree = lane
    result = _run_sweep(
        "--repo", root, "--holds", tmp_path / "missing-holds", "--apply"
    )
    assert result.returncode == 2
    assert "REFUSE sweep: cannot read hold list" in result.stderr
    assert worktree.exists()


def test_just_recipe_routes_lane_reap_through_the_checked_tool():
    result = subprocess.run(
        ["just", "--dry-run", "reap-lane", "--check", "/tmp/lane"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "python3 dev/reap.py --check /tmp/lane" in result.stderr
