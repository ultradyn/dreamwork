"""Canonical lane-worktree roots during the in-repo drain (#846)."""

from __future__ import annotations

from pathlib import Path


WORKTREE_DIR = ".worktrees"


def worktree_roots(target: Path) -> tuple[Path, Path]:
    """New sibling root first, followed by the draining in-repo root."""
    root = target.resolve()
    return root.parent / WORKTREE_DIR, root / WORKTREE_DIR


def lane_worktree_path(target: Path, lane: str) -> Path:
    """Canonical path for a newly launched lane."""
    return worktree_roots(target)[0] / lane
