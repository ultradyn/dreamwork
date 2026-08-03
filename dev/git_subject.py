#!/usr/bin/env python3
"""Identify the worktree and branch a Git mutation would address."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence


class SubjectState(str, Enum):
    MATCH = "match"
    DIFFERENT = "different"
    NOT_WORK_TREE = "not-work-tree"
    UNDETERMINABLE = "undeterminable"


@dataclass(frozen=True)
class SubjectObservation:
    state: SubjectState
    intended_root: Path | None
    intended_branch: str | None
    actual_root: Path | None
    actual_branch: str | None
    reason: str

    @property
    def ok(self) -> bool:
        return self.state is SubjectState.MATCH

    def describe(self) -> str:
        return (
            f"status={self.state.value} reason={self.reason}; "
            f"intended-root={self.intended_root or '-'} "
            f"intended-branch={self.intended_branch or '-'}; "
            f"actual-root={self.actual_root or '-'} "
            f"actual-branch={self.actual_branch or '-'}"
        )


def _absolute(path: str | os.PathLike[str], *, label: str) -> Path:
    value = os.fspath(path)
    if not os.path.isabs(value):
        raise ValueError(f"{label} must be absolute, so it cannot inherit ambient cwd")
    # abspath removes trailing separators and dot segments without following
    # the symlink that may itself be the caller's stable path contract.
    return Path(os.path.abspath(value))


def _git(
    cwd: Path, args: Sequence[str], *, git: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [git, "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def inspect_subject(
    *,
    command_cwd: str | os.PathLike[str],
    intended_root: str | os.PathLike[str] | None = None,
    intended_branch: str | None = None,
    git: str = "git",
) -> SubjectObservation:
    """Inspect Git's actual subject and compare it with an explicit intention."""
    if intended_root is None and intended_branch is None:
        raise ValueError("an intended repo root, branch, or both is required")
    cwd = _absolute(command_cwd, label="command cwd")
    expected_root = (
        _absolute(intended_root, label="intended root")
        if intended_root is not None else None
    )

    def observation(state: SubjectState, reason: str, *, root=None, branch=None):
        return SubjectObservation(
            state, expected_root, intended_branch, root, branch, reason)

    try:
        inside = _git(cwd, ("rev-parse", "--is-inside-work-tree"), git=git)
    except OSError as exc:
        return observation(SubjectState.UNDETERMINABLE, f"could not execute git: {exc}")
    if inside.returncode:
        stderr = inside.stderr.lower()
        if "not a git repository" in stderr:
            return observation(SubjectState.NOT_WORK_TREE, "git reports no work tree")
        return observation(
            SubjectState.UNDETERMINABLE,
            f"git could not determine work-tree status (exit {inside.returncode})",
        )
    inside_value = inside.stdout.strip().lower()
    if inside_value == "false":
        return observation(SubjectState.NOT_WORK_TREE, "git reports no work tree")
    if inside_value != "true":
        return observation(
            SubjectState.UNDETERMINABLE,
            f"git returned unreadable work-tree status {inside.stdout.strip()!r}",
        )

    try:
        top = _git(cwd, ("rev-parse", "--show-toplevel"), git=git)
        branch = _git(cwd, ("branch", "--show-current"), git=git)
        residue = _git(cwd, ("config", "--local", "--get", "core.worktree"), git=git)
    except OSError as exc:
        return observation(SubjectState.UNDETERMINABLE, f"could not execute git: {exc}")
    if top.returncode or not top.stdout.strip():
        return observation(
            SubjectState.UNDETERMINABLE,
            f"git could not resolve the worktree root (exit {top.returncode})",
        )
    actual_root = _absolute(top.stdout.strip(), label="git worktree root")
    if branch.returncode:
        return observation(
            SubjectState.UNDETERMINABLE,
            f"git could not resolve the current branch (exit {branch.returncode})",
            root=actual_root,
        )
    actual_branch = branch.stdout.strip() or None
    if residue.returncode not in (0, 1):
        return observation(
            SubjectState.UNDETERMINABLE,
            f"git could not read local core.worktree (exit {residue.returncode})",
            root=actual_root,
            branch=actual_branch,
        )
    if residue.returncode == 0 and residue.stdout.strip():
        return observation(
            SubjectState.DIFFERENT,
            f"local core.worktree residue is set to {residue.stdout.strip()!r}",
            root=actual_root,
            branch=actual_branch,
        )

    if expected_root is not None:
        try:
            same_root = os.path.samefile(expected_root, actual_root)
        except OSError as exc:
            return observation(
                SubjectState.UNDETERMINABLE,
                f"could not compare intended and actual roots: {exc}",
                root=actual_root,
                branch=actual_branch,
            )
        if not same_root:
            return observation(
                SubjectState.DIFFERENT,
                "Git resolved a different worktree root",
                root=actual_root,
                branch=actual_branch,
            )
    if intended_branch is not None and actual_branch != intended_branch:
        return observation(
            SubjectState.DIFFERENT,
            "Git resolved a different branch",
            root=actual_root,
            branch=actual_branch,
        )
    return observation(
        SubjectState.MATCH,
        "Git worktree and requested subject match",
        root=actual_root,
        branch=actual_branch,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, required=True, help="cwd the Git command will use")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--branch")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_subject(
            command_cwd=args.cwd,
            intended_root=args.repo_root,
            intended_branch=args.branch,
        )
    except ValueError as exc:
        print(f"git-subject: invalid subject: {exc}", file=sys.stderr)
        return 2
    print(result.describe())
    return {
        SubjectState.MATCH: 0,
        SubjectState.DIFFERENT: 1,
        SubjectState.NOT_WORK_TREE: 2,
        SubjectState.UNDETERMINABLE: 3,
    }[result.state]


if __name__ == "__main__":
    raise SystemExit(main())
