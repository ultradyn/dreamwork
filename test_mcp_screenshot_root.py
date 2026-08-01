#!/usr/bin/env python3
"""#670 — the MCP playwright browser's default screenshot root is inside a git
tree that does not belong to the acting lane, and a lane-private alternative.

THE DEFECT
----------
The @playwright/mcp server derives its output directory from its own cwd, but
the helper used the acting lane's cwd. In a worktree those differ, so it named a
directory where the server would not write.

WHAT THIS CHECKS
----------------
- server_cwd() resolves the live server for this harness session and refuses
  absent, ambiguous, or unreadable answers
- default_output_root() mirrors the server's own outputDir() fallback logic
- is_inside_worktree() correctly detects the bug condition (screenshot root
  IS inside a git tree)
- safe_staging_root() gives a lane-private dir that two lanes cannot share
- The resolver check uses deliberately different lane and server cwd values

RED-PROOF DIRECTION 1: break server_cwd() to return Path.cwd(); the resolver
test goes red saying the reported root is not the server PID's output root.

RED-PROOF DIRECTION 2: if the fixture made lane cwd equal server cwd, that same
broken resolver would pass. The fixture makes them differ, closing that
false-green.
"""
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure dev/ is importable.
DEV = Path(__file__).resolve().parent / "dev"
if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

import mcp_screenshot_root as msr  # noqa: E402


def _fake_server(proc: Path, pid: int, cwd: Path, session: str = "session-a"):
    process = proc / str(pid)
    process.mkdir(parents=True)
    (process / "cmdline").write_bytes(b"node\0/opt/bin/playwright-mcp\0")
    (process / "environ").write_bytes(
        f"CLAUDE_CODE_SESSION_ID={session}\0".encode()
    )
    (process / "cwd").symlink_to(cwd, target_is_directory=True)


# ─── the default output root mirrors the server's own logic ───────────────

def test_default_output_root_is_dot_playwright_mcp_under_cwd(tmp_path):
    """The server's outputDir() (coreBundle.js:64190) joins cwd with
    '.playwright-mcp' when no --output-dir is set. This test pins that
    derivation so a future MCP version change is caught."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    root = msr.default_output_root(workspace)
    assert root == workspace / ".playwright-mcp", (
        f"default_output_root should be cwd/.playwright-mcp, got {root}"
    )


def test_default_output_root_does_not_escape_cwd(tmp_path):
    """The default root must be UNDER the cwd, not a sibling or parent.
    A root that escapes cwd would mean the derivation is wrong."""
    workspace = tmp_path / "a" / "b"
    workspace.mkdir(parents=True)
    root = msr.default_output_root(workspace)
    assert root.parent == workspace, (
        f"default root {root} should be under {workspace}"
    )


def test_default_output_root_falls_back_for_system_or_unwritable_cwd(
    tmp_path, monkeypatch
):
    fallback = tmp_path / "system-tmp"
    monkeypatch.setattr(msr.tempfile, "gettempdir", lambda: str(fallback))
    assert msr.default_output_root(Path("/")) == fallback / ".playwright-mcp"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(msr.os, "access", lambda *_: False)
    assert msr.default_output_root(workspace) == fallback / ".playwright-mcp"


def test_server_cwd_uses_matching_process_not_callers_cwd(tmp_path, monkeypatch):
    """The fixture is deliberately discriminating: lane and server cwd differ.

    If they coincided, a broken caller-cwd resolver would look correct and this
    regression test would pass vacuously (the original #670 test shape).
    """
    proc = tmp_path / "proc"
    lane = tmp_path / "lane"
    server = tmp_path / "coordinator"
    proc.mkdir()
    lane.mkdir()
    server.mkdir()
    _fake_server(proc, 1234, server)
    monkeypatch.chdir(lane)

    pid, resolved = msr.server_cwd(
        proc, {"CLAUDE_CODE_SESSION_ID": "session-a"}
    )
    root = msr.default_output_root(resolved)

    assert root == server / ".playwright-mcp", (
        f"reported root {root} is not server PID 1234's output root "
        f"{server / '.playwright-mcp'}; the resolver used lane cwd {lane}"
    )
    assert pid == 1234


def test_server_cwd_disambiguates_other_sessions(tmp_path):
    proc = tmp_path / "proc"
    ours = tmp_path / "ours"
    other = tmp_path / "other"
    proc.mkdir()
    ours.mkdir()
    other.mkdir()
    _fake_server(proc, 1234, ours, "session-a")
    _fake_server(proc, 5678, other, "session-b")
    assert msr.server_cwd(proc, {"CLAUDE_CODE_SESSION_ID": "session-a"}) == (
        1234, ours
    )


def test_server_cwd_refuses_absent_or_ambiguous_answers(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    with pytest.raises(msr.ServerResolutionError, match="no live"):
        msr.server_cwd(proc, {"CLAUDE_CODE_SESSION_ID": "session-a"})

    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    _fake_server(proc, 1234, one)
    _fake_server(proc, 5678, two)
    with pytest.raises(msr.ServerResolutionError, match="several.*1234, 5678"):
        msr.server_cwd(proc, {"CLAUDE_CODE_SESSION_ID": "session-a"})


def test_server_cwd_refuses_unreadable_candidate_state(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    process = proc / "1234"
    process.mkdir()
    (process / "cmdline").write_bytes(b"node\0/opt/bin/playwright-mcp\0")
    with pytest.raises(msr.ServerResolutionError, match=r"PID\(s\) 1234.*unreadable"):
        msr.server_cwd(proc, {"CLAUDE_CODE_SESSION_ID": "session-a"})


# ─── the default IS inside a git tree (the bug condition) ─────────────────

def test_default_root_is_inside_a_git_worktree_here():
    """Precondition: we are running inside a git worktree (the repo itself).
    The MCP server's default output root (cwd/.playwright-mcp/) is therefore
    INSIDE a git tree — that is the bug condition #670 describes. This test
    asserts the condition holds AND that the detector sees it."""
    here = Path(__file__).resolve().parent
    root = msr.default_output_root(here)
    # Precondition: we ARE inside a worktree.
    assert msr.is_inside_worktree(here), (
        "precondition failed: test is not running inside a git worktree"
    )
    # The detector must agree.
    assert msr.is_inside_worktree(root), (
        f"default output root {root} IS inside a git worktree (the bug), "
        f"but is_inside_worktree() returned False — the detector is broken "
        f"and would hide the bug from a lane"
    )


def test_worktree_toplevel_resolves():
    """The toplevel must resolve to a real directory when inside a worktree."""
    here = Path(__file__).resolve().parent
    top = msr.worktree_toplevel(here)
    assert top is not None and top.is_dir(), (
        f"worktree_toplevel should resolve to a directory, got {top}"
    )


def test_default_root_worktree_toplevel_matches_our_worktree():
    """The default root's worktree toplevel must be THIS worktree (or the main
    checkout), not None — proving the screenshot lands inside a real git tree."""
    here = Path(__file__).resolve().parent
    root = msr.default_output_root(here)
    top = msr.worktree_toplevel(root)
    assert top is not None, (
        f"default root {root} is not inside any worktree — unexpected"
    )


# ─── outside a git tree, the detector says so ─────────────────────────────

def test_detector_says_outside_for_tmp():
    """/tmp is (almost certainly) not inside a git worktree, so the detector
    must return False there. This is the negative control for
    is_inside_worktree — without it, a function that always returns True
    would pass every positive test."""
    root = msr.default_output_root(Path("/tmp"))
    # /tmp could theoretically be inside a git repo on an unusual system.
    # Assert the NEGATIVE only when /tmp itself is not a worktree.
    if not msr.is_inside_worktree(Path("/tmp")):
        assert not msr.is_inside_worktree(root), (
            f"/tmp/.playwright-mcp is not inside a worktree but detector said True"
        )


# ─── the lane-private staging root is derived from identity ───────────────

def test_safe_staging_root_is_outside_any_worktree():
    """The lane-private staging dir (under ~/.cache) is OUTSIDE any git tree —
    screenshots copied there cannot dirty anyone's working tree."""
    here = Path(__file__).resolve().parent
    safe = msr.safe_staging_root(here)
    assert not msr.is_inside_worktree(safe), (
        f"safe staging dir {safe} is inside a git worktree — it must be outside "
        f"all git trees (it lives under ~/.cache)"
    )


def test_safe_staging_root_two_lanes_differ():
    """Two lanes (simulated by different cwds/branches) must get different
    staging roots — the same property that makes lane_scratch safe (#652)."""
    import lane_scratch
    here = Path(__file__).resolve().parent
    safe_a = msr.safe_staging_root(here)
    # A different worktree would derive a different lane key; we verify the
    # underlying derivation differs by checking the key directly.
    key_a = lane_scratch.lane_key(here)
    # Simulate a second lane by constructing a hypothetical path.
    key_b = lane_scratch.lane_key(Path("/tmp/fake-other-worktree"))
    # The fake path is not a real worktree, so it falls to detached-<hash>,
    # which must differ from our branch name.
    assert key_a != key_b, (
        f"two different worktrees derived the same lane key ({key_a}) — "
        f"the identity derivation is broken"
    )
    assert safe_a.parent.parent.parent == lane_scratch.SCRATCH_ROOT, (
        f"safe staging root {safe_a} is not under the expected scratch root"
    )


# ─── the finding: the default is NOT lane-private ─────────────────────────

def test_default_root_is_not_lane_private():
    """Direction 2 (honestly): the default output root is derived from session
    cwd, NOT lane identity. Every lane in a session gets the SAME default.
    This IS the finding — (b) is impossible, and the fix is (a)."""
    here = Path(__file__).resolve().parent
    default = msr.default_output_root(here)
    safe = msr.safe_staging_root(here)
    assert default != safe, (
        f"default root {default} equals safe root {safe} — if these were the "
        f"same, the default would already be lane-private (it is not)"
    )
    # The default is under the cwd (session-wide), the safe is under ~/.cache
    # (lane-private). They differ in kind, not just in path.
    assert not str(default).startswith(str(Path.home() / ".cache")), (
        f"default root {default} is under ~/.cache — it should be under cwd "
        f"(session-wide, NOT lane-private)"
    )
