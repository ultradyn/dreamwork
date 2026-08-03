"""Tests for strict lane-lock classification in :mod:`lane_liveness`."""

import json
import os
import subprocess
from pathlib import Path

import pytest

import lane_liveness
import lane_runner_identity


def _subject(tmp_path, *, lane="cx-finished"):
    target = tmp_path / "project"
    target.mkdir()
    worktree = tmp_path / ".worktrees" / lane
    (worktree / ".dreamwork").mkdir(parents=True)
    identity = worktree / "brief.md"
    return target, worktree, identity


def _inspect(target, worktree):
    return lane_liveness.inspect_lanes(
        target, process_entries=["101"],
        registered_worktrees=(worktree,), read_cmdline=lambda _pid: b"")


def _write_lock(worktree, identity, **updates):
    record = {
        "pid": 4242,
        "task": 987,
        "lane": worktree.name,
        "identity": str(identity),
    }
    record.update(updates)
    (worktree / ".dreamwork" / "lane.lock").write_text(json.dumps(record))
    return record


def test_lockless_worktree_is_settled_not_finished(tmp_path):
    target, worktree, _identity = _subject(tmp_path, lane="cx-settled")

    inspection = _inspect(target, worktree)

    assert inspection.worktree_only == ("cx-settled",)
    assert inspection.finished == ()


def test_only_breadcrumb_named_gate_scratch_is_not_worktree_only(tmp_path):
    target, idle, _identity = _subject(tmp_path, lane="cx-idle")
    live_gate = idle.parent / ".gate-live"
    live_gate.mkdir()
    abandoned_gate = idle.parent / ".gate-abandoned"
    abandoned_gate.mkdir()
    (target / ".dreamwork").mkdir()
    (target / ".dreamwork" / "gate-in-flight.json").write_text(json.dumps({
        "gate_worktree": str(live_gate),
    }))

    inspection = lane_liveness.inspect_lanes(
        target, process_entries=["101"],
        registered_worktrees=(live_gate, abandoned_gate, idle),
        read_cmdline=lambda _pid: b"")

    assert inspection.worktree_only == (".gate-abandoned", "cx-idle"), \
        "breadcrumb-named gate scratch was advertised as idle: %r" % \
        (inspection.worktree_only,)


def test_gate_breadcrumb_is_read_from_main_checkout_when_invoked_in_lane(
        tmp_path):
    main = tmp_path / "project"
    main.mkdir()
    env = os.environ | {
        "GIT_AUTHOR_NAME": "Dreamwork Test",
        "GIT_AUTHOR_EMAIL": "dreamwork@example.invalid",
        "GIT_COMMITTER_NAME": "Dreamwork Test",
        "GIT_COMMITTER_EMAIL": "dreamwork@example.invalid",
    }

    def git(*args):
        subprocess.run(
            ["git", "-C", str(main), *args], check=True,
            capture_output=True, text=True, env=env)

    git("init", "-q")
    (main / "tracked").write_text("fixture\n")
    git("add", "tracked")
    git("commit", "-q", "-m", "fixture")
    root = tmp_path / ".worktrees"
    live_gate = root / ".gate-live"
    idle = root / "cx-idle"
    git("worktree", "add", "-q", "--detach", str(live_gate), "HEAD")
    git("worktree", "add", "-q", "--detach", str(idle), "HEAD")
    (main / ".dreamwork").mkdir()
    (main / ".dreamwork" / "gate-in-flight.json").write_text(json.dumps({
        "gate_worktree": str(live_gate),
    }))

    inspection = lane_liveness.inspect_lanes(
        idle, process_entries=["101"], read_cmdline=lambda _pid: b"")

    assert inspection.worktree_only == ("cx-idle",), \
        "probe ignored the main-owned gate breadcrumb: %r" % \
        (inspection.worktree_only,)


def test_dead_runner_is_finished_with_its_lock_record(tmp_path, monkeypatch):
    target, worktree, identity = _subject(tmp_path)
    record = _write_lock(worktree, identity)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    expected = lane_liveness.FinishedLane(
        lane="cx-finished", task=987, pid=4242, identity=str(identity))
    assert (inspection.worktree_only == () and
            inspection.finished == (expected,)), \
        "cx-finished task #987 landed in wrong bucket: " \
        "worktree_only=%r finished=%r" % (
            inspection.worktree_only, inspection.finished)
    assert inspection.finished[0].pid == record["pid"]


def test_live_runner_stays_live_not_finished(tmp_path, monkeypatch):
    target, worktree, identity = _subject(tmp_path, lane="cx-live")
    _write_lock(worktree, identity)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: True)

    inspection = _inspect(target, worktree)

    assert inspection.live == ("cx-live",)
    assert inspection.finished == ()


@pytest.mark.parametrize("fault", [
    "unreadable", "invalid-json", "missing-key", "wrong-lane", "outside",
])
def test_lock_faults_remain_liveness_unknown(tmp_path, monkeypatch, fault):
    target, worktree, identity = _subject(tmp_path)
    lock = worktree / ".dreamwork" / "lane.lock"
    if fault == "unreadable":
        lock.mkdir()
    elif fault == "invalid-json":
        lock.write_text("{")
    elif fault == "missing-key":
        _write_lock(worktree, identity)
        record = json.loads(lock.read_text())
        del record["task"]
        lock.write_text(json.dumps(record))
    elif fault == "wrong-lane":
        _write_lock(worktree, identity, lane="cx-someone-else")
    else:
        _write_lock(worktree, tmp_path / "outside" / "brief.md")
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    with pytest.raises(lane_liveness.LivenessUnknown):
        _inspect(target, worktree)


def test_recreated_worktree_with_old_lock_looks_finished(tmp_path, monkeypatch):
    """Open false-green: same path/name cannot prove worktree continuity."""
    target, worktree, identity = _subject(tmp_path, lane="cx-recreated")
    _write_lock(worktree, identity, task=111)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    assert inspection.finished[0].task == 111


def test_pid_reuse_can_make_a_dead_lane_look_live(tmp_path, monkeypatch):
    """Open false-green: an unrelated same-cwd process can reuse the pid."""
    target, worktree, identity = _subject(tmp_path, lane="cx-pid-reused")
    _write_lock(worktree, identity, task=222)
    probe = lane_liveness.pid_matches_lane
    monkeypatch.setattr(
        lane_liveness, "pid_matches_lane",
        lambda pid, brief: probe(
            pid, brief, is_pid_alive=lambda _pid: True,
            proc_cwd=lambda _pid: str(Path(brief).parent)))

    inspection = _inspect(target, worktree)

    assert inspection.live == ("cx-pid-reused",)
    assert inspection.finished == ()


def test_valid_dead_lock_is_finished_without_git_or_scratch_evidence(
        tmp_path, monkeypatch):
    """The never-started shape remains actionable without claiming commits."""
    target, worktree, identity = _subject(tmp_path, lane="cx-never-started")
    _write_lock(worktree, identity, task=333)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    assert inspection.finished[0].lane == "cx-never-started"


def test_stale_lock_on_settled_branch_looks_finished(tmp_path, monkeypatch):
    """Open false-green: lock age is not represented in the record."""
    target, worktree, identity = _subject(tmp_path, lane="cx-stale-lock")
    _write_lock(worktree, identity, task=444)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    assert inspection.finished[0].lane == "cx-stale-lock"


# ── #1154: the work a finished lane left behind ─────────────────────────
#
# "finished" is one word for a lane whose runner is gone. The states that
# collapse into it (#136) are: reported-and-complete; died-with-nothing;
# died-holding-work (commits on the branch OR a dirty tracked tree OR an
# untracked deliverable). Only the third is dangerous, and it is the one no
# signal named. These tests build REAL git fixtures for the three tree states
# and assert the classifier decides each — never a hand-built record, because
# the classifier's whole job is to read the tree reap.py reads.


def _git_repo(worktree, *, branch="lane"):
    """A real git worktree the way a lane sits: master at the seed, the lane
    on a FEATURE BRANCH checked out ahead of it — so ``git cherry master HEAD``
    sees the lane's commits the way it does in a real fleet worktree."""
    env = os.environ | {
        "GIT_AUTHOR_NAME": "Dreamwork Test",
        "GIT_AUTHOR_EMAIL": "dreamwork@example.invalid",
        "GIT_COMMITTER_NAME": "Dreamwork Test",
        "GIT_COMMITTER_EMAIL": "dreamwork@example.invalid",
    }

    def git(*args):
        subprocess.run(
            ["git", "-C", str(worktree), *args], check=True,
            capture_output=True, text=True, env=env)

    git("init", "-q", "-b", "master")
    # Match the real repo's per-lane churn patterns so ignored entries read
    # ignored (!! / disposable) the way they do in a fleet worktree, not as
    # untracked (??). Without this, __pycache__/*.pyc would be untracked here
    # and the "discount ignored churn" path would never be exercised.
    (worktree / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.dreamwork/lane.lock\n")
    (worktree / "seed.txt").write_text("seed\n")
    git("add", ".gitignore", "seed.txt")
    git("commit", "-q", "-m", "seed")
    git("checkout", "-q", "-b", branch)
    return env


def _finished_with(worktree, identity, *, monkeypatch, work):
    """inspect_lanes classification for one dead-locked lane."""
    target = worktree.parent.parent / "project"
    _write_lock(worktree, identity)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
    return lane_liveness.inspect_lanes(
        target, process_entries=["101"],
        registered_worktrees=(worktree,), read_cmdline=lambda _pid: b"",
        work_classifier=lambda _wt: work)


class TestFinishedWorkSplit:
    """#1154: finished must split by the WORK the dead lane left behind."""

    def test_clean_no_commits_is_not_holding_work(self, tmp_path, monkeypatch):
        """State: died with nothing — clean tree, no commits. Disposable."""
        target, worktree, identity = _subject(tmp_path, lane="cx-clean")
        _git_repo(worktree)
        inspection = _finished_with(
            worktree, identity, monkeypatch=monkeypatch,
            work=lane_liveness.classify_finished_work(worktree))

        fl = inspection.finished[0]
        assert fl.work is not None
        assert not fl.work.holding_work, \
            "a clean tree with no commits read as holding work: %r" % (fl.work,)
        assert fl.work.tracked_dirty == 0
        assert fl.work.untracked == 0
        assert fl.work.unmerged == 0

    def test_clean_with_commits_is_holding_work(self, tmp_path, monkeypatch):
        """State: died holding work on the BRANCH — clean tree, unmerged
        commits (the cx-1060label6 shape: 8 commits, clean tree)."""
        target, worktree, identity = _subject(tmp_path, lane="cx-commits")
        env = _git_repo(worktree)
        # Add a commit the base (master) does not hold. master is the seed
        # commit; a second commit is one ahead — exactly "unmerged".
        (worktree / "fix.txt").write_text("fix\n")
        subprocess.run(
            ["git", "-C", str(worktree), "add", "fix.txt"], check=True,
            capture_output=True, text=True, env=env)
        subprocess.run(
            ["git", "-C", str(worktree), "commit", "-q", "-m",
             "fix(#900): real work"], check=True,
            capture_output=True, text=True, env=env)
        inspection = _finished_with(
            worktree, identity, monkeypatch=monkeypatch,
            work=lane_liveness.classify_finished_work(worktree))

        fl = inspection.finished[0]
        assert fl.work.holding_work, \
            "a branch one commit ahead of master read as disposable: %r" % (
                fl.work,)
        assert fl.work.unmerged == 1, \
            "unmerged count did not see the commit ahead of master: %r" % (
                fl.work,)
        assert fl.work.tracked_dirty == 0

    def test_tracked_dirty_zero_commits_is_holding_work(self, tmp_path,
                                                        monkeypatch):
        """State: died holding work in the TREE — tracked-dirty, zero commits
        (the cx-1140ingest shape: 448 insertions, zero commits). This is the
        case commit-count alone cannot see."""
        target, worktree, identity = _subject(tmp_path, lane="cx-dirty")
        _git_repo(worktree)
        # tracked-dirty: modify a tracked file the lane owns.
        (worktree / "seed.txt").write_text("changed by a killed lane\n")
        inspection = _finished_with(
            worktree, identity, monkeypatch=monkeypatch,
            work=lane_liveness.classify_finished_work(worktree))

        fl = inspection.finished[0]
        assert fl.work.holding_work, \
            "a tracked-dirty tree with zero commits read as disposable — " \
            "the exact conflation that nearly cost 448 lines: %r" % (fl.work,)
        assert fl.work.tracked_dirty == 1
        assert fl.work.unmerged == 0

    def test_only_ignored_churn_is_not_holding_work(self, tmp_path,
                                                    monkeypatch):
        """Direction-2 anchor: __pycache__ and lane.lock are present in every
        lane. A classifier that counts ignored churn as work would cry wolf on
        every finished lane. The split must discount them."""
        target, worktree, identity = _subject(tmp_path, lane="cx-churn")
        _git_repo(worktree)
        (worktree / "__pycache__").mkdir()
        (worktree / "__pycache__" / "junk.cpython-314.pyc").write_text("cache")
        # lane.lock lives under .dreamwork and is gitignored; emulate a second
        # ignored file that is NOT disposable so the ignored count is non-zero
        # and the test proves the disposable ones are what get discounted.
        inspection = _finished_with(
            worktree, identity, monkeypatch=monkeypatch,
            work=lane_liveness.classify_finished_work(worktree))

        fl = inspection.finished[0]
        assert not fl.work.holding_work, \
            "ignored churn (__pycache__/*.pyc) read as holding work: %r" % (
                fl.work,)

    def test_untracked_deliverable_is_holding_work(self, tmp_path,
                                                    monkeypatch):
        """A new untracked file beyond BRIEF.md is a deliverable the lane
        forgot to commit — work that reaping would destroy."""
        target, worktree, identity = _subject(tmp_path, lane="cx-untracked")
        _git_repo(worktree)
        (worktree / "new_module.py").write_text("real work\n")
        inspection = _finished_with(
            worktree, identity, monkeypatch=monkeypatch,
            work=lane_liveness.classify_finished_work(worktree))

        fl = inspection.finished[0]
        assert fl.work.holding_work, \
            "an untracked deliverable read as disposable: %r" % (fl.work,)
        assert fl.work.untracked == 1

    def test_brief_md_alone_is_not_holding_work(self, tmp_path, monkeypatch):
        """BRIEF.md is written into every worktree and never tracked; it must
        not inflate the untracked count into a holding-work verdict."""
        target, worktree, identity = _subject(tmp_path, lane="cx-brief")
        _git_repo(worktree)
        (worktree / "BRIEF.md").write_text("# a brief\n")
        inspection = _finished_with(
            worktree, identity, monkeypatch=monkeypatch,
            work=lane_liveness.classify_finished_work(worktree))

        fl = inspection.finished[0]
        assert not fl.work.holding_work, \
            "BRIEF.md (expected per-lane scratch) read as holding work: %r" % (
                fl.work,)
        assert fl.work.untracked == 0

    def test_non_git_worktree_classifies_none(self, tmp_path):
        """A worktree with no git repo degrades to None, not a false clean."""
        worktree = tmp_path / "nogit"
        worktree.mkdir()
        assert lane_liveness.classify_finished_work(worktree) is None



class TestCwdRunnerChannel:
    """The dispatch-route-invariant channel (#1084).

    A hand-dispatched lane (every follow-up round) has no lane.lock, so the
    lock channel is blind to it. The cwd channel names it live when a known
    RUNNER process holds the worktree as its cwd — a measurement that cannot
    vary with dispatch route. These tests inject ``read_cwd`` and
    ``read_cmdline`` so the cwd scan is exercised without real processes.
    """

    def test_lockless_worktree_with_live_runner_is_cwd_live(
            self, tmp_path, monkeypatch):
        """THE CASE THAT IS BROKEN TODAY: no lock, live runner in the worktree."""
        target, worktree, _identity = _subject(tmp_path, lane="glm-hand")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["501"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"ccc\x00-y\x00@glm52\x00",
            read_cwd=lambda _pid: str(worktree),
            skip_pids=set())
        assert inspection.cwd_live == ("glm-hand",), \
            "cwd channel missed glm-hand: a hand-dispatched lane with a live " \
            "runner and no lock was not detected by cwd: %r" % (inspection,)
        assert inspection.worktree_only == (), \
            "a worktree with a live runner was reported as idle: %r" % (
                inspection,)

    def test_non_runner_in_worktree_cwd_is_not_live(
            self, tmp_path, monkeypatch):
        """#671: a shell/editor sharing the worktree cwd is not a lane runner."""
        target, worktree, _identity = _subject(tmp_path, lane="glm-idle")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["502"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"zsh\x00-c\x00sleep 9999\x00",
            read_cwd=lambda _pid: str(worktree),
            skip_pids=set())
        assert inspection.cwd_live == (), \
            "a non-runner process (zsh) was counted as a live lane: %r" % (
                inspection,)
        assert inspection.worktree_only == ("glm-idle",)

    def test_many_processes_in_one_worktree_count_one_lane(
            self, tmp_path, monkeypatch):
        """#837: ccc spawns grok; both share the cwd. The set dedupes to one
        lane per worktree, so the fleet number is a lane count not a process
        count."""
        target, worktree, _identity = _subject(tmp_path, lane="glm-dup")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        cwds = {601: str(worktree), 602: str(worktree), 603: str(worktree)}
        cmdlines = {
            601: b"ccc\x00-y\x00@glm52\x00",
            602: b"grok\x00--yolo\x00",
            603: b"zsh\x00-c\x00echo hi\x00",
        }
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["601", "602", "603"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda pid: cmdlines.get(pid, b""),
            read_cwd=lambda pid: cwds.get(pid),
            skip_pids=set())
        assert inspection.cwd_live == ("glm-dup",), \
            "multiple processes in one worktree did not dedupe to one " \
            "lane: %r" % (inspection,)

    def test_deleted_cwd_is_not_a_live_runner(
            self, tmp_path, monkeypatch):
        """#719: a process whose worktree was removed carries ' (deleted)'."""
        target, worktree, _identity = _subject(tmp_path, lane="glm-phantom")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["701"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"ccc\x00-y\x00@glm52\x00",
            read_cwd=lambda _pid: str(worktree) + " (deleted)",
            skip_pids=set())
        assert inspection.cwd_live == (), \
            "a deleted-cwd phantom was counted as a live runner: %r" % (
                inspection,)

    def test_stale_lock_with_live_runner_is_cwd_live_not_finished(
            self, tmp_path, monkeypatch):
        """A re-armed lane has a stale lock (dead pid) but a new live runner
        by cwd. The cwd channel finds it live; the stale lock does not make
        it 'finished'."""
        target, worktree, identity = _subject(tmp_path, lane="glm-rearmed")
        _write_lock(worktree, identity, task=555)
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["801"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"grok\x00--yolo\x00",
            read_cwd=lambda _pid: str(worktree),
            skip_pids=set())
        assert inspection.cwd_live == ("glm-rearmed",), \
            "re-armed lane with live cwd runner not detected: %r" % (
                inspection,)
        assert inspection.finished == (), \
            "a re-armed lane with a live runner was reported as " \
            "finished: %r" % (inspection,)

    def test_lock_live_and_cwd_only_both_named(self, tmp_path, monkeypatch):
        """Both dispatch routes on one tick: one lock-confirmed, one cwd-only."""
        target = tmp_path / "project"
        target.mkdir()
        locked = tmp_path / ".worktrees" / "cx-locked"
        (locked / ".dreamwork").mkdir(parents=True)
        identity = locked / "brief.md"
        (locked / ".dreamwork" / "lane.lock").write_text(json.dumps({
            "pid": 4242, "task": 999, "lane": "cx-locked",
            "identity": str(identity),
        }))
        hand = tmp_path / ".worktrees" / "glm-hand"
        (hand / ".dreamwork").mkdir(parents=True)
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        cwds = {901: str(locked), 902: str(hand)}
        cmdlines = {
            901: b"ccc\x00-y\x00@glm52\x00",
            902: b"grok\x00--yolo\x00",
        }
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["901", "902"],
            registered_worktrees=(locked, hand),
            read_cmdline=lambda pid: cmdlines.get(pid, b""),
            read_cwd=lambda pid: cwds.get(pid),
            skip_pids=set())
        assert inspection.live == ("cx-locked",)
        assert inspection.cwd_live == ("glm-hand",)


# ── #1113: the cwd channel reads the SHARED classifier ──────────────────
#
# The tick's fleet count uses lane_liveness._is_lane_runner, which must be the
# SAME function status_sync uses — not a copy. The mutation test below
# exercises this through inspect_lanes's cwd channel (the #1084 dispatch-route
# invariant), not by calling the function in isolation: it mutates the shared
# constant and asserts the cwd channel's runner classification flips.

class TestCwdChannelSharesClassifier:
    """#1113: the cwd channel's runner test is the shared classifier."""

    def test_mutating_shared_runners_flips_cwd_classification(
            self, tmp_path, monkeypatch):
        # A process whose argv[0] is "codex" (a known runner) holding a
        # worktree cwd should be classified as a cwd-live lane. Removing
        # "codex" from the shared constant must make the cwd channel drop it
        # — proving lane_liveness reads the shared source, not its own copy.
        target = tmp_path / "project"
        target.mkdir()
        worktree = tmp_path / ".worktrees" / "glm-codex-hand"
        (worktree / ".dreamwork").mkdir(parents=True)

        cmdline = b"codex\x00--yolo\x00glm-codex-hand\x00"
        cwd = str(worktree)

        # BASELINE: the cwd channel sees "codex" as a runner → cwd_live.
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["501"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: cmdline,
            read_cwd=lambda _pid: cwd,
            skip_pids=set())
        assert inspection.cwd_live == ("glm-codex-hand",), \
            "baseline: codex is a known runner; the cwd channel must see it"

        # THE MUTATION: remove "codex" from the shared constant. If
        # lane_liveness shares the classifier, the cwd channel must now see
        # this process as a non-runner (head/grep/tail class) and drop it.
        monkeypatch.setattr(
            lane_runner_identity, "LANE_RUNNERS",
            tuple(n for n in lane_runner_identity.LANE_RUNNERS
                  if n != "codex"))

        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["501"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: cmdline,
            read_cwd=lambda _pid: cwd,
            skip_pids=set())
        assert inspection.cwd_live == (), \
            "after removing codex: the cwd channel must drop the lane — " \
            "if it stayed, lane_liveness has its own copy (#1113)"
