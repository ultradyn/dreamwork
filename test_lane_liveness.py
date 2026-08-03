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


_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Dreamwork Test",
    "GIT_AUTHOR_EMAIL": "dreamwork@example.invalid",
    "GIT_COMMITTER_NAME": "Dreamwork Test",
    "GIT_COMMITTER_EMAIL": "dreamwork@example.invalid",
}


def _git_subject(tmp_path, *, lane="cx-finished"):
    """A REAL git repo + linked worktree at base, matching fleet layout (#1155 P1 #3).

    Unlike ``_subject`` (which mkdirs plain directories), this creates a git
    repository with an initial commit and a linked worktree at HEAD — the
    shape a dispatched lane actually has. The worktree is on a NAMED BRANCH
    (``-b lane``, matching ``dev/launch_lane.py:611``); round 2 used
    ``--detach``, which lint's own backstop calls an ERROR
    (``test_lint.py:8278``). The identity is ``BRIEF.md`` — the coordinator-
    written per-lane file that is in the live-progress scratch exclusion set,
    so it does not inflate progress the way a test-only ``.{lane}-identity``
    file would (#1155 round 3).

    The worktree's branch is at base (zero commits ahead of master), so the
    default wedge probe's git check sees no progress, which is the on-disk
    evidence a real wedged lane leaves.
    """
    env = os.environ | _GIT_ENV
    target = tmp_path / "project"
    target.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(target), *args], check=True,
            capture_output=True, text=True, env=env)

    git("init", "-q", "-b", "master")
    # Match the REAL repo's .gitignore and tracked layout (#1155 round 4 P2b):
    # the root .gitignore lists __pycache__/ but NOT *.pyc (verified against the
    # real file). .dreamwork/lane.lock and .dreamwork/status.json ARE gitignored
    # (lane-local state); .dreamwork/ itself is TRACKED (it holds deliverables —
    # docs/, reports/, etc. — just like the real repo). So a worktree at base
    # has .dreamwork/ tracked, lane.lock ignored, and only genuinely new files
    # under .dreamwork/ (a plan, a doc) appear as ?? — the deliverables the
    # probe must count as progress (#1155 round 4 P1).
    (target / ".gitignore").write_text(
        "__pycache__/\n.dreamwork/lane.lock\n.dreamwork/status.json\n")
    (target / "tracked").write_text("fixture\n")
    (target / ".dreamwork").mkdir(parents=True)
    (target / ".dreamwork" / ".gitkeep").touch()
    git("add", ".gitignore", "tracked", ".dreamwork/.gitkeep")
    git("commit", "-q", "-m", "fixture")
    worktree = tmp_path / ".worktrees" / lane
    git("worktree", "add", "-q", "-b", lane, str(worktree), "HEAD")
    identity = worktree / "BRIEF.md"
    identity.touch()
    (worktree / ".dreamwork").mkdir(parents=True, exist_ok=True)
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
    # untracked (??). The real .gitignore lists __pycache__/ but NOT *.pyc
    # (#1155 round 4 P2b). Without __pycache__/, __pycache__/*.pyc would be
    # untracked here and the "discount ignored churn" path would never fire.
    (worktree / ".gitignore").write_text(
        "__pycache__/\n.dreamwork/lane.lock\n")
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


# ── #1113: the cwd channel reads the SHARED classifier ──────────────────#
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


# ── #1155: LIVE-side liveness — is a live runner actually able to work? ─
#
# "finished" splits by the WORK a dead lane left behind (#1154). The LIVE side
# was left open: "is a runner alive" is answered, "is it able to work" is not,
# so a permission-wedged lane (live pid, blocked, zero commits) is
# indistinguishable from a computing one in the fleet count. The brief's three
# measured Cases are the discrimination test, and B/C are the false positives
# that matter — they are what would make a stall signal untrustworthy and so
# ignored. Each case is constructed as a FIXTURE (fake process table + fake
# worktree), never a real lane — four lanes are live doing real work.

class TestLiveLaneStates:
    """#1155: classify_live_lane is the pure state machine. Inputs are measured
    signals; tests inject numbers, never a real process."""

    def test_wedge_marker_with_high_cpu_is_working_not_wedged(self):
        """#1155 P1 #1: a rejected call proves a rejection happened, not that
        the runner never recovered — and 120 CPU-seconds is positive evidence
        it did. CPU at/above floor wins over the marker, so this lane reads
        WORKING, not WEDGED. The old test asserted WEDGED here and encoded the
        dangerous false verdict as a requirement."""
        verdict = lane_liveness.classify_live_lane(
            "glm-recovered", cpu_seconds=120.0, elapsed_seconds=300.0,
            wedge_marker="auto-rejecting external_directory")
        assert verdict.state == lane_liveness.LIVE_WORKING, \
            "a lane with 120s CPU and a marker was not classified working " \
            "(CPU must win over marker, #1155 P1 #1): %r" % (verdict,)

    def test_wedge_marker_with_low_cpu_is_wedged(self):
        """The complement: a marker paired with LOW CPU (below floor) and
        sufficient age → WEDGED. The marker is positive wedge evidence; the
        low CPU confirms the runner is blocked, not computing."""
        verdict = lane_liveness.classify_live_lane(
            "glm-wedged", cpu_seconds=0.1, elapsed_seconds=600.0,
            wedge_marker="auto-rejecting external_directory")
        assert verdict.state == lane_liveness.LIVE_WEDGED, \
            "a lane with low CPU and a positive marker was not classified " \
            "wedged: %r" % (verdict,)

    def test_cpu_above_floor_is_working(self):
        """Case C shape: 31s CPU, no marker → working."""
        verdict = lane_liveness.classify_live_lane(
            "glm-1066label", cpu_seconds=31.0, elapsed_seconds=540.0,
            wedge_marker=None)
        assert verdict.state == lane_liveness.LIVE_WORKING, \
            "a lane with 31s CPU read as not-working: %r" % (verdict,)

    def test_young_lane_with_no_signal_is_not_yet_observed(self):
        """30 seconds after dispatch: NOT wedged, NOT working — not yet
        observed. #1155: a lane 30s after dispatch is not yet observed working."""
        verdict = lane_liveness.classify_live_lane(
            "cx-just-dispatched", cpu_seconds=0.5, elapsed_seconds=30.0,
            wedge_marker=None)
        assert verdict.state == lane_liveness.LIVE_NOT_YET, \
            "a 30s-old lane read as something other than not-yet-observed: " \
            "%r" % (verdict,)

    def test_young_lane_with_marker_is_still_wedged(self):
        """Youth is not innocence: a marker found under the age floor (with
        low CPU) is still wedged — the marker check (step 2) precedes the age
        check (step 3) in classify_live_lane. CPU is checked first (step 1),
        but 0.0 < floor so it does not clear."""
        verdict = lane_liveness.classify_live_lane(
            "cx-quick-wedge", cpu_seconds=0.0, elapsed_seconds=10.0,
            wedge_marker="auto-rejecting external_directory")
        assert verdict.state == lane_liveness.LIVE_WEDGED

    def test_old_low_cpu_no_marker_is_unknown(self):
        """The honest stall signature: old enough to have produced CPU that
        produced almost none, no recognised marker. NOT wedged (no positive
        evidence), NOT working (no CPU) — unknown, and that must be sayable
        rather than folded into wedged (#136)."""
        verdict = lane_liveness.classify_live_lane(
            "glm-wedge-no-log", cpu_seconds=0.1, elapsed_seconds=600.0,
            wedge_marker=None)
        assert verdict.state == lane_liveness.LIVE_UNKNOWN, \
            "old+low-cpu+no-marker read as a confident state instead of " \
            "unknown: %r" % (verdict,)

    def test_no_signal_is_unknown_not_working(self):
        """A missing /proc reads unknown, never as a zero-CPU 'working' (#136)."""
        verdict = lane_liveness.classify_live_lane(
            "glm-gone", cpu_seconds=None, elapsed_seconds=None,
            wedge_marker=None)
        assert verdict.state == lane_liveness.LIVE_UNKNOWN

    def test_unknown_age_is_unknown_not_not_yet_observed(self):
        """#1155 P1 #2 / #136: when /proc/uptime is unreadable, the age is
        ABSENT (None), not zero. A low-CPU lane with absent age must read
        UNKNOWN ('cannot tell'), not not-yet-observed (which requires a real
        young elapsed < floor). The old code returned elapsed=0, folding
        'cannot tell' into 'not yet observed' — the exact #136 collapse."""
        verdict = lane_liveness.classify_live_lane(
            "glm-no-uptime", cpu_seconds=0.1, elapsed_seconds=None,
            wedge_marker=None)
        assert verdict.state == lane_liveness.LIVE_UNKNOWN, \
            "a lane with absent age (elapsed=None) was not classified " \
            "unknown — age must not collapse into not-yet-observed (#136): " \
            "%r" % (verdict,)


class TestLiveLaneCasesABC:
    """The three measured Cases as REAL fixtures (#1155 P1 #3), each exercising
    the PRODUCTION path — no injected wedge_probe, just like tick_line.py.

    Case A — five wedged lanes: real git worktree at base, 0 CPU, old → WEDGED.
    Case B — glm-1153ident: 0 commits at 11 min, accumulating CPU → WORKING.
    Case C — glm-1066label: 0-byte transcript, 31s CPU → WORKING.

    B and C are the false positives: a classifier that called either wedged
    would make the signal untrustworthy. All three, or it proves nothing.
    The default probe (the one the tick uses) must return WEDGED for A and
    NOT-wedged for B and C in the same run, unmodified.

    DISCRIMINATION DISCLOSURE (#1155 round 4, updating round 3's). Which tests
    FAIL under the always-None probe defect (stubbed _default_wedge_probe →
    None), verified by re-running the mutation this round:

      - test_case_a_wedged_via_production_path: FAILS (WEDGED→UNKNOWN). ✓
      - test_case_a_dreamwork_docs_deliverable_is_unknown_not_wedged: PASSES
        (UNKNOWN either way — it tests NOT-wedged, and always-None gives
        UNKNOWN too). NOT a discriminating test for the too-narrow direction.
      - test_case_a_untracked_deliverable_is_unknown_not_wedged: same — PASSES
        under always-None. NOT discriminating for too-narrow.
      - test_scratch_only_untracked_still_reads_wedged: FAILS (WEDGED→UNKNOWN
        — it tests the too-NARROW direction; always-None gives UNKNOWN, not
        WEDGED, so it DOES fail under too-narrow). NOT discriminating for
        too-BROAD: it has ONLY scratch, so mutating the predicate to return
        True for EVERY path leaves it green (#1155 round 4 P2a).
      - test_scratch_plus_deliverable_is_not_wedged: the too-BROAD
        discriminator — FAILS under the "every path is scratch" mutation
        (the deliverable is swallowed → WEDGED). This is the test the P1
        shipped without.
      - B and C: PASS (return early on high CPU before examining git).

    The probe's git-check discrimination (too-narrow) rests on
    test_case_a_wedged_via_production_path and test_scratch_only_untracked_
    still_reads_wedged. The exclusion's not-too-broad discrimination rests
    on test_scratch_plus_deliverable_is_not_wedged. The .dreamwork/docs/
    subtree regression is test_case_a_dreamwork_docs_deliverable_is_unknown_
    not_wedged.

    pid_matches_lane BLIND SPOT (#651): every test in this class patches
    pid_matches_lane to lambda True/False, so deleting the production
    function fails setup but a BROKEN implementation stays green. The
    identity check is exercised honestly by TestCwdRunnerChannel (which
    injects read_cwd/read_cmdline so the cwd channel runs the real
    is_lane_runner path) — this class delegates live/dead to the patch so
    it can focus on the PROGRESS state machine. The blind spot is stated
    here rather than left implicit.
    """

    def test_case_a_wedged_via_production_path(self, tmp_path, monkeypatch):
        """Case A: a REAL git worktree at base (zero commits, clean tree).
        Live pid, 0.1s CPU, 600s elapsed. The DEFAULT probe (no injection)
        checks the worktree, finds no git progress, and returns a wedge
        marker. classify_live_lane: CPU below floor, marker present → WEDGED.

        THIS IS THE PRODUCTION-PATH TEST. It calls inspect_lanes the way
        tick_line.py does — no wedge_probe argument. If the default probe
        wiring is deleted (restored to always-None), this test fails with
        UNKNOWN instead of WEDGED."""
        target, worktree, identity = _git_subject(tmp_path, lane="glm-wedged")
        _write_lock(worktree, identity, pid=1101)
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1101"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0))
        verdict = inspection.live_liveness
        assert len(verdict) == 1, "expected one live-liveness verdict: %r" % (
            verdict,)
        assert verdict[0].lane == "glm-wedged"
        assert verdict[0].state == lane_liveness.LIVE_WEDGED, \
            "Case A (real git worktree at base, 0 cpu) was not classified " \
            "wedged via the production path: %r" % (verdict[0],)

    def test_case_b_zero_commits_via_production_path(self, tmp_path,
                                                     monkeypatch):
        """Case B: REAL git worktree at base (zero commits, clean tree).
        Indistinguishable from Case A by git state alone. BUT 25s CPU at 11min
        → the default probe sees CPU ≥ floor → returns None → classify_live_lane
        reads WORKING (step 1: CPU wins). Same probe, same run, not wedged.

        NOT A DISCRIMINATING PROBE TEST (#1155 round 3). B and C return early
        on high CPU at _default_wedge_probe step 2 (cpu_seconds >= floor →
        return None), so they never examine git and stay green under the
        always-None defect. The false-positive protection for a no-commits
        lane with high CPU rests on the classifier test
        test_wedge_marker_with_high_cpu_is_working_not_wedged, and the probe's
        git-check discrimination is closed by the P1 regression test
        (old + low CPU + untracked deliverable → UNKNOWN) below.

        THIS IS THE DIRECTION-2 ANCHOR. The injected defect (classify on 'no
        commits' without checking CPU) would call THIS lane wedged and flag a
        working lane for destruction."""
        target, worktree, identity = _git_subject(
            tmp_path, lane="glm-1153ident")
        _write_lock(worktree, identity, pid=1102)
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1102"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (25.0, 660.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_WORKING, \
            "Case B (0 commits, 25s CPU) was NOT classified working — this " \
            "is the false positive that would kill a real lane: %r" % (
                verdict[0],)

    def test_case_c_zero_byte_transcript_via_production_path(self, tmp_path,
                                                             monkeypatch):
        """Case C: REAL git worktree at base, zero commits, with a zero-byte
        transcript file (like a real opencode runner that writes at completion).
        31s CPU → the default probe sees CPU ≥ floor → None → WORKING.
        Same probe, same run, not wedged.

        NOT A DISCRIMINATING PROBE TEST: same early-return on high CPU as
        Case B — see that test's docstring for the full statement."""
        target, worktree, identity = _git_subject(
            tmp_path, lane="glm-1066label")
        _write_lock(worktree, identity, pid=1103)
        (worktree / ".dreamwork" / "transcript.jsonl").touch()  # zero-byte
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1103"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (31.0, 540.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_WORKING, \
            "Case C (0-byte transcript, 31s CPU) was NOT classified " \
            "working: %r" % (verdict[0],)

    def test_case_a_non_git_worktree_is_unknown_not_wedged(self, tmp_path,
                                                           monkeypatch):
        """A lane whose worktree is NOT a git repo (or where git fails): the
        default probe CANNOT check progress → returns None → classify_live_lane
        reads UNKNOWN ('cannot tell'). The probe degrades to no-marker on
        error, never asserts a wedge it cannot verify (#651)."""
        target, worktree, identity = _subject(tmp_path, lane="glm-no-git")
        _write_lock(worktree, identity, pid=1104)
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1104"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_UNKNOWN, \
            "a non-git worktree read as wedged — the probe must degrade to " \
            "cannot-tell when it cannot check progress (#651): %r" % (
                verdict[0],)

    def test_case_a_with_progress_is_unknown_not_wedged(self, tmp_path,
                                                        monkeypatch):
        """A lane whose worktree HAS git progress (dirty tracked files) with
        low CPU: the default probe finds progress → returns None → UNKNOWN.
        The probe does not assert a wedge when the lane made progress, even
        if CPU is low (it might be a slow worker between operations)."""
        target, worktree, identity = _git_subject(
            tmp_path, lane="glm-progress")
        _write_lock(worktree, identity, pid=1105)
        # Dirty a tracked file — the runner modified code (progress).
        (worktree / "tracked").write_text("modified\n")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1105"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_UNKNOWN, \
            "a worktree with progress read as wedged: %r" % (verdict[0],)

    def test_case_a_untracked_deliverable_is_unknown_not_wedged(self, tmp_path,
                                                                monkeypatch):
        """#1155 round 3 P1 — THE REGRESSION TEST. Old + low CPU + an untracked
        DELIVERABLE (new_module.py, uncommitted) must classify UNKNOWN, never
        WEDGED. Through the PRODUCTION path with no injected probe, the way
        round 2's Case A test does.

        A lane that has written a file and not yet committed is the NORMAL
        state of a lane mid-increment. Classifying it WEDGED would point the
        destructive reaping tool at precisely the lane whose work exists only
        in the working tree (#702 / #760: reap separates untracked from
        ignored for exactly this reason).

        If the discarding of ?? entries in _worktree_has_progress regresses,
        this test fails: the probe sees no progress, returns a wedge marker,
        and the lane classifies WEDGED instead of UNKNOWN. The file name
        (new_module.py) appears in no assertion message — the failure is the
        state mismatch — but the fixture creates it so the production path
        reaches the git-check branch the regression breaks."""
        target, worktree, identity = _git_subject(
            tmp_path, lane="glm-untracked-work")
        _write_lock(worktree, identity, pid=1106)
        # An untracked deliverable — real work the runner has not committed.
        (worktree / "new_module.py").write_text("real work\n")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1106"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_UNKNOWN, \
            "a lane with an untracked deliverable (new_module.py) was " \
            "classified WEDGED — this is the data-loss hazard: the lane " \
            "holds uncommitted work and the probe pointed the reaper at " \
            "it: %r" % (verdict[0],)

    def test_scratch_only_untracked_still_reads_wedged(self, tmp_path,
                                                       monkeypatch):
        """BOUNDARY (not-too-narrow direction): the scratch exclusion does not
        swallow ALL untracked files. A lane whose only untracked entries are
        scratch (BRIEF.md, .pytest_cache/) has NO progress → WEDGED (old, low
        CPU). This tests the too-NARROW direction: if the exclusion is removed
        entirely, this lane would read UNKNOWN (a false non-wedged). It CANNOT
        detect too-BROAD — see test_scratch_plus_deliverable_is_not_wedged for
        that direction (#1155 round 4 P2a: a test named for a bound must be
        red when the bound is violated in the direction it names)."""
        target, worktree, identity = _git_subject(
            tmp_path, lane="glm-scratch-only")
        _write_lock(worktree, identity, pid=1107)
        # Scratch the real fleet produces: .pytest_cache (not gitignored).
        # BRIEF.md is already created by the fixture as the identity file.
        # .dreamwork/ is tracked in the fixture (matching the real repo), so
        # it does not appear as ?? — only genuinely new files under it do.
        (worktree / ".pytest_cache").mkdir()
        (worktree / ".pytest_cache" / "v.json").write_text("{}")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1107"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_WEDGED, \
            "a lane with ONLY scratch untracked was not classified wedged " \
            "— the exclusion list is too narrow or missing, so scratch " \
            "looks like progress: %r" % (
                verdict[0],)

    def test_case_a_dreamwork_docs_deliverable_is_unknown_not_wedged(
            self, tmp_path, monkeypatch):
        """#1155 round 4 P1 — THE .dreamwork/docs/ REGRESSION. A real named-
        branch worktree whose only untracked path is under .dreamwork/docs/
        must classify UNKNOWN through the production path with NO injected
        probe (#1155 round 4: the reviewer built this case and got WEDGED).

        Round 3's blanket .dreamwork entry in _LIVE_PROGRESS_UNTRACKED_SCRATCH
        declared ALL .dreamwork paths scratch. The top-level-component match
        at _is_live_progress_scratch therefore discarded .dreamwork/docs/**,
        so a lane whose whole increment was a plan or design doc under
        .dreamwork/docs/ read as having no git progress → WEDGED → the
        data-loss hazard. .dreamwork/docs/ is a tracked deliverable subtree
        (design docs, plans, audits); this loop dispatches lanes to write
        there regularly.

        The fixture matches the reviewer's exact construction: .dreamwork/ is
        tracked (via .gitkeep, as in the real repo), so only NEW files under
        it appear as ?? — not the directory itself. The sole untracked path
        is .dreamwork/docs/plans/new-plan.md."""
        target, worktree, identity = _git_subject(
            tmp_path, lane="glm-docs-work")
        _write_lock(worktree, identity, pid=1109)
        # An untracked deliverable under .dreamwork/docs/ — the lane's
        # increment (a plan, a design doc). .dreamwork/ is tracked in the
        # fixture (matching the real repo), so this new path is the only ??
        # beyond BRIEF.md (scratch).
        docs_plans = worktree / ".dreamwork" / "docs" / "plans"
        docs_plans.mkdir(parents=True)
        (docs_plans / "new-plan.md").write_text("# a plan\n")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1109"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_UNKNOWN, \
            "a lane whose only work is under .dreamwork/docs/ was classified " \
            "WEDGED — this is the data-loss hazard: .dreamwork/docs/ holds " \
            "tracked deliverables (plans, design docs) and a lane writing " \
            "there is doing work, not wedged: %r" % (verdict[0],)

    def test_scratch_plus_deliverable_is_not_wedged(self, tmp_path,
                                                     monkeypatch):
        """BOUNDARY (not-too-broad direction) — #1155 round 4 P2a: a test
        whose name asserts a bound must be RED when the bound is violated in
        the direction it names.

        Round 3's test_scratch_only_untracked_still_reads_wedged COULD NOT
        detect too-broad: it had ONLY scratch, so mutating _is_live_progress_
        scratch to return True for EVERY path left it green (every path WAS
        scratch). This test mixes scratch (.pytest_cache/) with a deliverable
        (new_module.py): under the normal predicate the deliverable provides
        progress → UNKNOWN; under the maximally over-broad mutation
        (every path is scratch) the deliverable is swallowed → no progress →
        WEDGED → this test fails. That is the discrimination the P1 shipped
        without."""
        target, worktree, identity = _git_subject(
            tmp_path, lane="glm-mixed")
        _write_lock(worktree, identity, pid=1110)
        # Scratch + a deliverable: .pytest_cache (scratch) and new_module.py
        # (work). The deliverable must survive the exclusion and provide
        # progress; if the predicate is too broad, it is swallowed.
        (worktree / ".pytest_cache").mkdir()
        (worktree / ".pytest_cache" / "v.json").write_text("{}")
        (worktree / "new_module.py").write_text("real work\n")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # NO wedge_probe
            target, process_entries=["1110"],
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0))
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_UNKNOWN, \
            "a lane with a deliverable (new_module.py) alongside scratch " \
            "was classified WEDGED — the scratch exclusion is too broad: " \
            "%r" % (verdict[0],)

    def test_injected_probe_that_raises_degrades_to_unknown(self, tmp_path,
                                                            monkeypatch):
        """#1155 P2b: a probe that raises must leave the lane unclassified
        (UNKNOWN), not propagate the exception. The TypeError fallback path
        (backward-compat f(worktree, pid) probes) previously let the fallback
        call's exception escape because only the keyword-form call was inside
        the try/except. This test injects a probe that raises RuntimeError
        from the fallback form and asserts no exception escapes inspect_lanes."""
        target, worktree, identity = _subject(tmp_path, lane="glm-probe-boom")
        _write_lock(worktree, identity, pid=1108)

        def exploding_probe(_wt, _pid):
            raise RuntimeError("probe broken")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(  # no exception escapes
            target, process_entries=["1108"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda _pid: (0.1, 600.0),
            wedge_probe=exploding_probe)
        verdict = inspection.live_liveness
        assert verdict[0].state == lane_liveness.LIVE_UNKNOWN, \
            "a probe that raised did not degrade to unknown: %r" % (
                verdict[0],)

    def test_default_cpu_probe_reads_proc(self, tmp_path, monkeypatch):
        """When read_cpu is not injected, inspect_lanes uses read_proc_cpu on
        the real /proc. For the test's own pid (alive), that returns a real
        (cpu, elapsed) tuple — proving the live default is wired, not a stub.
        We assert it does not raise and returns a verdict (the value depends
        on the test runner's own CPU, so we bind the shape not the number)."""
        target, worktree, identity = _subject(tmp_path, lane="cx-default-cpu")
        _write_lock(worktree, identity, pid=os.getpid())
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=[str(os.getpid())],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"",
            wedge_probe=lambda _wt, _pid: None)
        verdict = inspection.live_liveness
        assert len(verdict) == 1
        assert verdict[0].state in (
            lane_liveness.LIVE_WORKING, lane_liveness.LIVE_NOT_YET), \
            "default CPU probe on the live test pid produced an unexpected " \
            "verdict: %r" % (verdict[0],)


class TestLiveLivenessCwdChannel:
    """A cwd-only (hand-dispatched) lane gets the same live-liveness verdict
    as a lock-confirmed lane — the dimension is dispatch-route-invariant,
    like the cwd channel itself (#1084)."""

    def test_cwd_only_lane_classified_by_cpu(self, tmp_path, monkeypatch):
        target, worktree, _identity = _subject(tmp_path, lane="glm-hand")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["1201"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"ccc\x00-y\x00@glm52\x00",
            read_cwd=lambda _pid: str(worktree),
            read_cpu=lambda _pid: (0.2, 400.0),
            wedge_probe=lambda _wt, _pid: "auto-rejecting external_directory",
            skip_pids=set())
        assert inspection.cwd_live == ("glm-hand",)
        verdict = inspection.live_liveness
        assert len(verdict) == 1
        assert verdict[0].lane == "glm-hand"
        assert verdict[0].state == lane_liveness.LIVE_WEDGED, \
            "cwd-only lane was not given a live-liveness verdict: %r" % (
                verdict,)

    def test_busy_runner_vetoes_wedged_in_either_proc_order(
            self, tmp_path, monkeypatch):
        """All cwd runners are relevant to the lane verdict. PID 701 is idle
        while its nested PID 702 is busy; reversing /proc enumeration must
        not change the state, and the busy runner must veto WEDGED."""
        target, worktree, identity = _subject(tmp_path, lane="glm-nested")
        _write_lock(worktree, identity, pid=701)
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        cpu = {701: (0.1, 600.0), 702: (25.0, 600.0)}

        def state_for(order):
            inspection = lane_liveness.inspect_lanes(
                target, process_entries=[str(pid) for pid in order],
                registered_worktrees=(worktree,),
                read_cmdline=lambda _pid: b"ccc\x00-y\x00@glm52\x00",
                read_cwd=lambda _pid: str(worktree),
                read_cpu=lambda pid: cpu[pid],
                wedge_probe=lambda _wt, _pid: "permission-wedge",
                skip_pids=set())
            assert inspection.live == ("glm-nested",)
            assert inspection.cwd_live == ()
            assert len(inspection.live_liveness) == 1
            return inspection.live_liveness[0].state

        forward = state_for((701, 702))
        reverse = state_for((702, 701))
        assert forward == reverse == lane_liveness.LIVE_WORKING, \
            "same lane with PID 701=0.1s CPU and PID 702=25.0s CPU produced " \
            "states forward=%s reverse=%s; both runners must be consulted " \
            "and busy PID 702 must veto WEDGED" % (forward, reverse)

    def test_unreadable_runner_prevents_wedged(self, tmp_path, monkeypatch):
        """A runner that vanishes between enumeration and its CPU read is
        UNKNOWN, not an idle process that can help authorise WEDGED."""
        target, worktree, _identity = _subject(tmp_path, lane="glm-vanished")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        cpu = {701: (0.1, 600.0), 702: None}
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["701", "702"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"ccc\x00-y\x00@glm52\x00",
            read_cwd=lambda _pid: str(worktree),
            read_cpu=lambda pid: cpu[pid],
            wedge_probe=lambda _wt, _pid, *, cpu_s=None, **_kw: (
                "permission-wedge" if cpu_s is not None else None),
            skip_pids=set())
        verdict = inspection.live_liveness[0]
        assert verdict.state == lane_liveness.LIVE_UNKNOWN
        assert "pid 702" in verdict.reason
        assert "consulted 2/2 relevant processes" in verdict.reason

    def test_all_idle_runners_can_still_be_wedged(self, tmp_path, monkeypatch):
        """The conservative reduction does not make WEDGED unreachable: all
        relevant runners may still independently supply wedge evidence."""
        target, worktree, _identity = _subject(tmp_path, lane="glm-all-idle")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["701", "702"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"ccc\x00-y\x00@glm52\x00",
            read_cwd=lambda _pid: str(worktree),
            read_cpu=lambda _pid: (0.1, 600.0),
            wedge_probe=lambda _wt, _pid: "permission-wedge",
            skip_pids=set())
        verdict = inspection.live_liveness[0]
        assert verdict.state == lane_liveness.LIVE_WEDGED
        assert "all 2/2 relevant processes classified wedged" in verdict.reason


class TestLiveLivenessDenominator:
    """#868: the verdict set is the denominator. A tick that names 2 wedged of
    3 live must also say the third was classified — a stall count over an
    unknown population is the defect this loop keeps finding."""

    def test_every_live_lane_gets_a_verdict(self, tmp_path, monkeypatch):
        target = tmp_path / "project"
        target.mkdir()
        wt_a = tmp_path / ".worktrees" / "glm-a"
        wt_b = tmp_path / ".worktrees" / "cx-b"
        wt_c = tmp_path / ".worktrees" / "glm-c"
        for wt in (wt_a, wt_b, wt_c):
            (wt / ".dreamwork").mkdir(parents=True)
        _write_lock(wt_a, wt_a / "brief.md", pid=1, lane="glm-a")
        _write_lock(wt_b, wt_b / "brief.md", pid=2, lane="cx-b")
        _write_lock(wt_c, wt_c / "brief.md", pid=3, lane="glm-c")
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: True)
        cpus = {1: (0.1, 600.0), 2: (30.0, 400.0), 3: (0.5, 40.0)}
        markers = {1: "auto-rejecting external_directory"}
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["1", "2", "3"],
            registered_worktrees=(wt_a, wt_b, wt_c),
            read_cmdline=lambda _pid: b"",
            read_cpu=lambda pid: cpus.get(pid),
            wedge_probe=lambda _wt, pid: markers.get(pid))
        verdicts = {v.lane: v.state for v in inspection.live_liveness}
        # The denominator: all three live lanes are classified, not just the
        # wedged one — a wedged count of 1 over a live set of 3 states the
        # other two, and "unknown" is one of them.
        assert set(verdicts) == {"glm-a", "cx-b", "glm-c"}, \
            "not every live lane got a verdict (denominator unknown): %r" % (
                verdicts,)
        assert verdicts["glm-a"] == lane_liveness.LIVE_WEDGED
        assert verdicts["cx-b"] == lane_liveness.LIVE_WORKING
        assert verdicts["glm-c"] == lane_liveness.LIVE_NOT_YET


class TestLiveLivenessDoesNotInflateFinished:
    """The live-liveness verdicts are ONLY for live lanes. A finished lane
    (dead pid) gets no live-liveness entry — its dimension is #1154's work
    classifier, not this one. The two dimensions must not cross."""

    def test_finished_lane_has_no_live_liveness(self, tmp_path, monkeypatch):
        target, worktree, identity = _subject(tmp_path, lane="cx-finished")
        _write_lock(worktree, identity)
        monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_a: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["101"],
            registered_worktrees=(worktree,),
            read_cmdline=lambda _pid: b"",
            work_classifier=lambda _wt: None)
        assert inspection.finished, "precondition: lane is finished"
        assert inspection.live_liveness == (), \
            "a finished lane got a live-liveness verdict: %r" % (
                inspection.live_liveness,)
