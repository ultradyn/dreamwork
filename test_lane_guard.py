"""Focused executable coverage for the lane-containment commit guard."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from dev import lane_guard


SOURCE_ROOT = Path(__file__).resolve().parent


def _git(
    root: Path,
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd or root), *args],
        check=check,
        capture_output=True,
        text=True,
        env=env,
        input=input_text,
    )


def _repo_with_modern_lane(
    tmp_path: Path, *, lane_owns: str | None = "owned.py", hooks: bool = False,
) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str, cwd: Path | None = None) -> None:
        _git(root, *args, cwd=cwd)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (root / "owned.py").write_text("base\n", encoding="utf-8")
    briefs = root / ".dreamwork" / "docs" / "briefs"
    briefs.mkdir(parents=True)
    ownership = f"\nLane-owns: {lane_owns}\n" if lane_owns is not None else "\n"
    (briefs / "992-modern.md").write_text(
        "Worktree: `.worktrees/cx-992modern` on `cx-992modern`.\n\n"
        + ownership,
        encoding="utf-8",
    )
    if hooks:
        shutil.copytree(SOURCE_ROOT / ".githooks", root / ".githooks")
        dev = root / "dev"
        dev.mkdir()
        (dev / "lane_guard.py").symlink_to(SOURCE_ROOT / "dev" / "lane_guard.py")
    git("add", "-A")
    git("commit", "-qm", "base")
    lane = root.parent / ".worktrees" / "cx-992modern"
    git("worktree", "add", "-q", "-b", "cx-992modern", str(lane))
    if hooks:
        git("config", "--local", "core.hooksPath", ".githooks")
    return root, lane


def _hook_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    global_hooks = tmp_path / "global-hooks"
    global_hooks.mkdir()
    trace = tmp_path / "global-hooks.trace"
    body = """#!/bin/sh
name=$(basename "$0")
printf '%s:%s\\n' "$name" "$*" >> "$HOOK_TRACE"
if [ "${GLOBAL_HOOK_REJECT:-}" = "$name" ]; then
    echo "global $name refused" >&2
    exit 73
fi
"""
    for name in ("pre-commit", "commit-msg", "pre-push"):
        hook = global_hooks / name
        hook.write_text(body, encoding="utf-8")
        hook.chmod(0o755)
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text(
        f"[core]\n\thooksPath = {global_hooks}\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = str(global_config)
    env["HOOK_TRACE"] = str(trace)
    return env, trace


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


def test_tracked_hook_forwards_global_then_refuses_the_indexed_path(tmp_path):
    """The production hook reaches `check` and `_staged_paths`, in that order."""
    root, lane = _repo_with_modern_lane(tmp_path, hooks=True)
    env, trace = _hook_env(tmp_path)
    (root / "owned.py").write_text("staged offender\n", encoding="utf-8")
    _git(root, "add", "owned.py")
    # Make the working tree innocent again. Only the index still carries the
    # offending bytes, so a working-tree reader would pass this false green.
    (root / "owned.py").write_text("base\n", encoding="utf-8")

    refused = _git(root, "commit", "-m", "must refuse", env=env, check=False)

    assert refused.returncode != 0
    assert "contested staged paths: owned.py" in refused.stderr
    assert f"lane cx-992modern ({lane}) owns" in refused.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == ["pre-commit:"]


def test_global_pre_commit_refusal_stops_before_lane_guard(tmp_path):
    root, _ = _repo_with_modern_lane(tmp_path, hooks=True)
    env, trace = _hook_env(tmp_path)
    env["GLOBAL_HOOK_REJECT"] = "pre-commit"
    (root / "owned.py").write_text("staged offender\n", encoding="utf-8")
    _git(root, "add", "owned.py")

    refused = _git(root, "commit", "-m", "global refuses", env=env, check=False)

    assert refused.returncode != 0
    assert "global pre-commit refused" in refused.stderr
    assert "lane-containment guard" not in refused.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == ["pre-commit:"]


def test_lane_commit_fires_relative_hook_and_forwards_commit_msg(tmp_path):
    root, lane = _repo_with_modern_lane(tmp_path, hooks=True)
    env, trace = _hook_env(tmp_path)
    (lane / "owned.py").write_text("legitimate lane edit\n", encoding="utf-8")
    _git(root, "add", "owned.py", cwd=lane)

    committed = _git(root, "commit", "-m", "lane commit", cwd=lane, env=env)

    assert "OK — linked worktree commit" in committed.stderr
    lines = trace.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "pre-commit:"
    assert lines[1].startswith("commit-msg:")
    assert _git(root, "config", "--local", "--get", "core.hooksPath").stdout.strip() == ".githooks"


def test_commit_msg_and_pre_push_forward_args_and_exit_status(tmp_path):
    root, _ = _repo_with_modern_lane(tmp_path, hooks=True)
    env, trace = _hook_env(tmp_path)
    env["GLOBAL_HOOK_REJECT"] = "commit-msg"
    message = tmp_path / "message"
    message.write_text("subject\n", encoding="utf-8")

    commit_msg = subprocess.run(
        [str(root / ".githooks" / "commit-msg"), str(message)],
        cwd=root, env=env, capture_output=True, text=True,
    )
    assert commit_msg.returncode == 73
    assert "global commit-msg refused" in commit_msg.stderr

    env["GLOBAL_HOOK_REJECT"] = "pre-push"
    pre_push = subprocess.run(
        [str(root / ".githooks" / "pre-push"), "origin", "ssh://example/repo"],
        cwd=root, env=env, input="refs/heads/x 1 refs/heads/x 0\n",
        capture_output=True, text=True,
    )
    assert pre_push.returncode == 73
    assert "global pre-push refused" in pre_push.stderr
    lines = trace.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("commit-msg:")
    assert lines[1] == "pre-push:origin ssh://example/repo"


def test_escape_hatch_is_exercised_through_installed_hook(tmp_path):
    root, _ = _repo_with_modern_lane(tmp_path, hooks=True)
    env, trace = _hook_env(tmp_path)
    env["DREAMWORK_LANE_GUARD_BYPASS"] = "1"
    (root / "owned.py").write_text("emergency commit\n", encoding="utf-8")
    _git(root, "add", "owned.py")

    committed = _git(root, "commit", "-m", "bypassed", env=env)

    assert "BYPASSED because DREAMWORK_LANE_GUARD_BYPASS is set" in committed.stderr
    assert [line.split(":", 1)[0] for line in trace.read_text().splitlines()] == [
        "pre-commit", "commit-msg",
    ]


def test_no_lane_population_allows_but_does_not_claim_containment(tmp_path):
    root, lane = _repo_with_modern_lane(tmp_path, hooks=True)
    _git(root, "worktree", "remove", str(lane))
    _git(root, "branch", "-D", "cx-992modern")
    env, _ = _hook_env(tmp_path)
    (root / "owned.py").write_text("unclassifiable owner\n", encoding="utf-8")
    _git(root, "add", "owned.py")

    committed = _git(root, "commit", "-m", "no lanes", env=env)

    assert "NOT EVALUATED — no lane worktrees exist" in committed.stderr
    assert "ownership comparison" in committed.stderr


def test_lane_without_lane_owns_allows_but_names_the_unprotected_lane(tmp_path):
    root, lane = _repo_with_modern_lane(tmp_path, lane_owns=None, hooks=True)
    env, _ = _hook_env(tmp_path)
    (root / "owned.py").write_text("unprotected edit\n", encoding="utf-8")
    _git(root, "add", "owned.py")

    committed = _git(root, "commit", "-m", "undeclared ownership", env=env)

    assert "INCOMPLETE — allowing commit" in committed.stderr
    assert "1 of 1 lane(s) declare no Lane-owns: paths" in committed.stderr
    assert f"cx-992modern ({lane})" in committed.stderr


def test_branch_rename_cannot_escape_path_based_ownership(tmp_path):
    root, lane = _repo_with_modern_lane(tmp_path, hooks=True)
    env, _ = _hook_env(tmp_path)
    _git(root, "branch", "-m", "branch-with-no-lane-prefix", cwd=lane)
    (root / "owned.py").write_text("staged offender\n", encoding="utf-8")
    _git(root, "add", "owned.py")

    refused = _git(root, "commit", "-m", "renamed branch", env=env, check=False)

    assert refused.returncode != 0
    assert "lane branch-with-no-lane-prefix" in refused.stderr
    assert "contested staged paths: owned.py" in refused.stderr


def test_detached_provisional_merge_does_not_invoke_pre_commit(tmp_path):
    """A merge forwards commit-msg, but never reaches the lane guard."""
    root, lane = _repo_with_modern_lane(tmp_path, hooks=True)
    env, trace = _hook_env(tmp_path)
    (lane / "owned.py").write_text("lane result\n", encoding="utf-8")
    _git(root, "add", "owned.py", cwd=lane)
    _git(root, "commit", "-m", "lane result", cwd=lane, env=env)
    trace.write_text("", encoding="utf-8")
    _git(root, "checkout", "--detach")

    merged = _git(root, "merge", "--no-ff", "cx-992modern", "-m", "provisional", env=env)

    assert merged.returncode == 0
    assert trace.read_text(encoding="utf-8") == "commit-msg:.git/MERGE_MSG\n"
    assert "lane-containment guard" not in merged.stderr


def test_just_recipes_pin_repo_local_enable_and_cautious_disable():
    text = (SOURCE_ROOT / "justfile").read_text(encoding="utf-8")
    assert "enable-lane-guard:\n    git config --local core.hooksPath .githooks" in text
    assert "disable-lane-guard:" in text
    assert "git config --local --unset core.hooksPath" in text
    assert "not .githooks" in text


def test_retired_global_installer_points_to_repo_local_recipes(capsys):
    assert lane_guard.main(["install"]) == 2
    assert "just enable-lane-guard" in capsys.readouterr().err
    assert lane_guard.main(["uninstall"]) == 2
    assert "just disable-lane-guard" in capsys.readouterr().err
