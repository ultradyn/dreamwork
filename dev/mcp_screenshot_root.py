#!/usr/bin/env python3
"""Where the shared MCP playwright browser writes screenshots, and a lane-private
alternative (#670).

THE FINDING
-----------
The ``@playwright/mcp`` server (v0.0.78) derives its output directory from
``process.cwd()`` when no ``--output-dir`` flag is set (measured in source,
``outputDir()`` at coreBundle.js:64190):

    function outputDir(options) {
        if (options.config.outputDir) return resolve(options.config.outputDir);
        const baseName = options.config.skillMode ? ".playwright-cli" : ".playwright-mcp";
        if (isSystemDirectory(options.cwd) || !isWritable(options.cwd))
            return join(tmpdir(), baseName);
        return join(options.cwd, baseName);
    }

That ``cwd`` is the **coordinator's** working directory at server launch time,
not the acting lane's — the MCP server is one per session and is shared by every
lane subagent. ``browser_take_screenshot`` resolves its ``fileName`` argument
against this directory only; there is no per-call override.

So a default-named screenshot lands in ``<coordinator-cwd>/.playwright-mcp/``,
which is inside a git working tree that does not belong to the acting lane. The
harm is currently **mitigated** by ``.gitignore`` (``.playwright-mcp/`` is
ignored, so the screenshot is invisible to ``git status``, cannot be swept by
``git add``, and does not block ``git worktree remove``), but the mitigation is
fragile — it depends on the gitignore entry surviving and on the cwd happening
to be a tree that carries it.

WHY (b) IS IMPOSSIBLE
---------------------
Per-lane output roots cannot be expressed in the MCP server config because:

1. The server is launched **once per coordinator session** and shared by all
   lane subagents — there is one ``--output-dir``, set at process startup.
2. ``browser_take_screenshot`` accepts only a ``fileName`` (a basename resolved
   against the output dir), not a path. You cannot redirect output per-call.
3. The server has no concept of "which lane is calling."

The repo does not control the server's launch — the playwright MCP comes from a
harness plugin (``~/.claude-shared/plugins/.../playwright/.mcp.json``), not from
a repo-level config. Adding a project ``.mcp.json`` with the same server name
would conflict with the plugin and risks breaking playwright entirely, so it is
not attempted.

WHAT THIS TOOL DOES
-------------------
It tells the lane three things it cannot otherwise discover:

1. **default** — where the MCP server WILL write screenshots (``cwd/.playwright-mcp/``)
2. **whether that is inside a git worktree** (the bug condition)
3. **safe** — a lane-private staging directory (same identity derivation as
   ``dev/lane_scratch.py``), where the lane can copy screenshots after taking
   them so they don't linger in a stranger's tree

Usage::

    python3 dev/mcp_screenshot_root.py           # report default + safety
    python3 dev/mcp_screenshot_root.py --safe     # lane-private staging dir
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return out.strip() or None


def default_output_root(cwd: Path | None = None) -> Path:
    """Where the MCP server writes screenshots, replicating its own logic.

    Mirrors ``outputDir()`` from ``@playwright/mcp`` coreBundle.js:64190.
    No ``--output-dir`` → ``cwd/.playwright-mcp/``.
    """
    here = Path(cwd or Path.cwd()).resolve()
    return here / ".playwright-mcp"


def _existing_ancestor(path: Path) -> Path:
    """Nearest existing ancestor of ``path`` (for git -C when path is new)."""
    p = path
    while not p.exists():
        if p.parent == p:
            return path  # fell off the filesystem; let git -C fail naturally
        p = p.parent
    return p


def is_inside_worktree(path: Path) -> bool:
    """True if ``path`` is inside a git working tree.

    Uses ``git rev-parse --is-inside-work-tree`` from ``path``'s nearest
    existing ancestor, which is the authoritative check. The output root
    (``cwd/.playwright-mcp/``) may not exist yet, so we walk up to a real
    directory before asking git.
    """
    probe = _existing_ancestor(path)
    result = _git(probe, "rev-parse", "--is-inside-work-tree")
    return result == "true"


def worktree_toplevel(path: Path) -> Path | None:
    """The worktree root containing ``path``, or None outside a worktree."""
    probe = _existing_ancestor(path)
    top = _git(probe, "rev-parse", "--show-toplevel")
    return Path(top).resolve() if top else None


def safe_staging_root(cwd: Path | None = None) -> Path:
    """A lane-private screenshot staging directory.

    Reuses ``dev/lane_scratch.py``'s identity derivation (repo + lane + role)
    so two concurrent lanes never share one directory — the same property that
    makes lane snapshots safe (#652). The lane copies screenshots here after
    taking them; the MCP server cannot write here directly (see module docstring).
    """
    here = Path(cwd or Path.cwd()).resolve()
    # Import lane_scratch from the same dev/ directory.
    dev_dir = Path(__file__).resolve().parent
    if str(dev_dir) not in sys.path:
        sys.path.insert(0, str(dev_dir))
    import lane_scratch  # noqa: E402
    return lane_scratch.lane_scratch_dir(here, create=True, sub="mcp-shots")


def report(cwd: Path | None = None) -> int:
    """Print the default output root, its worktree status, and the safe alt."""
    root = default_output_root(cwd)
    inside = is_inside_worktree(root)
    top = worktree_toplevel(root)
    safe = safe_staging_root(cwd)
    status = (
        f"INSIDE git worktree ({top}) — screenshots land in a stranger's tree"
        if inside
        else "OUTSIDE any git worktree"
    )
    print(f"default output root : {root}")
    print(f"  status           : {status}")
    print(f"  safe staging dir : {safe}")
    if inside:
        print(
            "  WARNING: copy screenshots to the safe dir after taking them; "
            "the MCP server cannot be redirected per-call (#670).",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Report the MCP playwright browser's screenshot output root "
                    "and a lane-private alternative (#670).")
    ap.add_argument("--safe", action="store_true",
                    help="print only the lane-private staging directory")
    ap.add_argument("--cwd", default=None,
                    help="derive for this directory instead of the current one")
    args = ap.parse_args(argv)
    cwd = Path(args.cwd) if args.cwd else None
    if args.safe:
        print(safe_staging_root(cwd))
        return 0
    return report(cwd)


if __name__ == "__main__":
    sys.exit(main())
