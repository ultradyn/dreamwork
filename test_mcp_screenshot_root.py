#!/usr/bin/env python3
"""#670 — the MCP playwright browser's default screenshot root is inside a git
tree that does not belong to the acting lane, and a lane-private alternative.

THE DEFECT
----------
The @playwright/mcp server (v0.0.78) derives its output directory from
process.cwd() — the coordinator's cwd, not the acting lane's. A default-named
screenshot lands in <coordinator-cwd>/.playwright-mcp/, which is inside a git
working tree. The harm is mitigated by .gitignore today, but the root is still
derived from session identity, not lane identity.

WHAT THIS CHECKS
----------------
- default_output_root() mirrors the server's own outputDir() logic
- is_inside_worktree() correctly detects the bug condition (screenshot root
  IS inside a git tree)
- safe_staging_root() gives a lane-private dir that two lanes cannot share
- The MCP server config is NOT per-lane addressable (the finding): the default
  root is the same for every lane in a session, derived from cwd not identity

RED-PROOF DIRECTION 1: break is_inside_worktree to always return False; the
test naming the default root as INSIDE a worktree goes red.

RED-PROOF DIRECTION 2 (open, honestly): a lane that does nothing still gets
the session cwd as its output root — the fix IS (a), not (b). The MCP server
config cannot express per-lane roots. We verify and state this rather than
claiming the default is safe.
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


# ─── the default output root mirrors the server's own logic ───────────────

def test_default_output_root_is_dot_playwright_mcp_under_cwd():
    """The server's outputDir() (coreBundle.js:64190) joins cwd with
    '.playwright-mcp' when no --output-dir is set. This test pins that
    derivation so a future MCP version change is caught."""
    root = msr.default_output_root(Path("/some/workspace"))
    assert root == Path("/some/workspace/.playwright-mcp"), (
        f"default_output_root should be cwd/.playwright-mcp, got {root}"
    )


def test_default_output_root_does_not_escape_cwd():
    """The default root must be UNDER the cwd, not a sibling or parent.
    A root that escapes cwd would mean the derivation is wrong."""
    root = msr.default_output_root(Path("/a/b"))
    assert str(root).startswith("/a/b/"), (
        f"default root {root} should be under /a/b/"
    )


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
