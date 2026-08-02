"""Focused executable coverage for the lane-containment commit guard."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dev import lane_guard


def _repo_with_modern_lane(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str, cwd: Path | None = None) -> None:
        subprocess.run(
            ["git", "-C", str(cwd or root), *args],
            check=True, capture_output=True, text=True,
        )

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (root / "owned.py").write_text("base\n", encoding="utf-8")
    briefs = root / ".dreamwork" / "docs" / "briefs"
    briefs.mkdir(parents=True)
    (briefs / "992-modern.md").write_text(
        "Worktree: `.worktrees/cx-992modern` on `cx-992modern`.\n\n"
        "Lane-owns: owned.py\n",
        encoding="utf-8",
    )
    git("add", "-A")
    git("commit", "-qm", "base")
    lane = root.parent / ".worktrees" / "cx-992modern"
    git("worktree", "add", "-q", "-b", "cx-992modern", str(lane))
    return root, lane


def test_commit_guard_protects_a_modern_branch_from_its_registered_path(
        tmp_path, capsys):
    """Production seams: `_parse_worktree_list` and `_owned_paths_for_lane`."""
    root, lane = _repo_with_modern_lane(tmp_path)
    (root / "owned.py").write_text("coordinator edit\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "owned.py"], check=True)

    rc = lane_guard.check(root)
    err = capsys.readouterr().err
    assert rc == 1, err
    assert "cx-992modern" in err and str(lane) in err, err
    assert "contested staged paths: owned.py" in err, err


def test_commit_guard_fails_loud_when_classification_cannot_run(
        tmp_path, monkeypatch, capsys):
    """Enumeration failure is exit 2, distinct from the idle exit 0."""
    root, _ = _repo_with_modern_lane(tmp_path)
    monkeypatch.setattr(
        lane_guard, "_parse_worktree_list",
        lambda _: (_ for _ in ()).throw(lane_guard.GuardError(
            "git unavailable; worktrees examined=0; lanes classified=0")),
    )
    rc = lane_guard.check(root)
    err = capsys.readouterr().err
    assert rc == 2, err
    assert "git unavailable" in err, err
    assert "worktrees examined=0; lanes classified=0" in err, err
