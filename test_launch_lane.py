from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parent
TOOL = REPO / "dev" / "launch_lane.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def launch_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "master")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    _write(root / "briefs" / "boilerplate.md", "# Standing rules\nDo the checked work.\n")
    _write(root / "briefs" / "frame.md", "## Canonical frame\nGenerated, never retyped.\n")
    _write(root / ".dreamwork" / "tasks.md",
           "# Tasks\n\n## Open\n\n- **#832** launch it\n\n"
           "  Measured launcher composition.\n\n## Recently landed\n")
    _write(root / "dev" / "launch_lane.py", TOOL.read_text(encoding="utf-8"))
    _write(root / "worktree_paths.py", (REPO / "worktree_paths.py").read_text(encoding="utf-8"))
    # launch_lane shares brief.py's placeholder predicate (#881); the real
    # module, not a stub, so a change to it is exercised here too.
    _write(root / "dev" / "brief.py", (REPO / "dev" / "brief.py").read_text(encoding="utf-8"))
    _write(root / "dev" / "dispatch_lane.py", """
import argparse, os, subprocess, sys
p = argparse.ArgumentParser(); p.add_argument('--prompt'); p.add_argument('--prepare', action='store_true'); p.add_argument('rest', nargs=argparse.REMAINDER)
a = p.parse_args(); cmd = a.rest[1:] if a.rest and a.rest[0] == '--' else a.rest
prompt = open(a.prompt, encoding='utf-8').read()
if a.prepare: raise SystemExit(int(os.environ.get('DISPATCH_PREPARE_EXIT', '0')))
raise SystemExit(subprocess.run([*cmd, prompt]).returncode)
""".lstrip())
    # The production launcher deliberately routes cleanup through this sibling.
    _write(root / "dev" / "reap.py", (REPO / "dev" / "reap.py").read_text(encoding="utf-8"))
    _write(root / "seed", "base\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    bindir = tmp_path / "bin"
    _write(bindir / "ccc", """#!/usr/bin/env python3
import glob, json, os, pathlib
if target := os.environ.get('CAPTURE_ATTEMPT_STATE'):
    record = glob.glob('.dreamwork/launch-attempts/*.json')[0]
    pathlib.Path(target).write_text(json.load(open(record))['state'], encoding='utf-8')
if target := os.environ.get('CAPTURE_PROMPT'):
    pathlib.Path(target).write_text(__import__('sys').argv[-1], encoding='utf-8')
raise SystemExit(int(os.environ.get('CCC_EXIT', '0')))
""")
    (bindir / "ccc").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("PYTHONPATH", f"{REPO / 'dev'}:{REPO}")
    return root


def _head(root: Path, text: str = (
    "# Task #832 — launch it\n\nLane-owns: dev/thing.py\n\n"
    "Implement the human requested change.\n\n## Direction 2\n\n"
    "A missing persisted prompt would pass a corpus-only check.\n"
)) -> Path:
    path = root / "head.md"
    _write(path, text)
    return path


def _run(root: Path, head: Path, *extra: str, env: dict[str, str] | None = None):
    actual_env = (env or os.environ.copy()).copy()
    actual_env["DREAMWORK_ALLOW_PIPED_STDOUT"] = "1"
    return subprocess.run(
        [sys.executable, str(root / "dev" / "launch_lane.py"), "832", "lane-832", "@agent", str(head), *extra],
        cwd=root, capture_output=True, text=True, env=actual_env,
    )


def _worktree_rows(root: Path) -> str:
    return _git(root, "worktree", "list", "--porcelain")


def _attempt(root: Path) -> tuple[Path, dict[str, object]]:
    paths = list((root / ".dreamwork" / "launch-attempts").glob("*.json"))
    assert len(paths) == 1
    return paths[0], json.loads(paths[0].read_text(encoding="utf-8"))


def test_brief_validation_reports_every_violation_before_worktree_creation(launch_repo: Path):
    head = _head(
        launch_repo,
        "# Task #999\nLane-owns: dev/thing.py\nBranch: wrong\nCoordinator inbox: wrong\n",
    )
    before = _worktree_rows(launch_repo)
    result = _run(launch_repo, head)

    assert result.returncode == 1
    assert "REFUSE phase=brief-generation: 1 violation(s)" in result.stderr
    assert "one first-level task heading for #832" in result.stderr
    assert _worktree_rows(launch_repo) == before


@pytest.mark.parametrize("core, label", [
    ("TODO: describe the defect\n", "a four-word fill-in"),
    ("<describe the defect here>\n", "an angle-bracket fill-in"),
    ("## The defect\n\n## The fix shape\n\n## Direction 2\n", "copied headings, no bodies"),
])
def test_a_placeholder_head_is_refused_not_dispatched(launch_repo: Path, core, label):
    """#881: the word-count bar passes on a placeholder — `TODO: describe the
    defect` is four words, and this route dispatched it as a briefed lane.

    Measured against this function before the fix: empty REFUSED, but all three
    cases below ACCEPTED. A lane briefed with a fill-in looks exactly like a
    briefed lane, which is the failure mode the loop cannot see from outside.
    """
    head = _head(launch_repo, f"# Task #832 — launch it\n\nLane-owns: dev/thing.py\n\n{core}")
    before = _worktree_rows(launch_repo)
    result = _run(launch_repo, head)

    assert result.returncode == 1, f"{label} was dispatched: {result.stderr!r}"
    assert ("no substantive line" in result.stderr
            or "has no body" in result.stderr)
    assert _worktree_rows(launch_repo) == before


def test_a_concise_real_core_is_still_accepted(launch_repo: Path):
    """The positive control for the refusal above: it must not refuse real prose.

    Without this, tightening the bar to "refuse everything" would pass the three
    cases above and nothing would say so.
    """
    head = _head(
        launch_repo,
        "# Task #832 — launch it\n\nLane-owns: dev/thing.py\n\n"
        "The block was retyped 33 times, 32 distinct bodies.\n\n"
        "## Direction 2\n\nAn unpersisted prompt could evade corpus lint.\n")
    result = _run(launch_repo, head)
    assert "entirely placeholder" not in result.stderr
    assert "no substantive task content" not in result.stderr


def test_selection_failure_leaves_git_worktree_inventory_unchanged(launch_repo: Path):
    before = _worktree_rows(launch_repo)
    result = _run(launch_repo, launch_repo / "missing.md")
    assert "REFUSE phase=selection" in result.stderr
    assert _worktree_rows(launch_repo) == before


def test_foreground_refusal_names_phase_and_creates_nothing(
    launch_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    spec = importlib.util.spec_from_file_location("launch_lane_foreground", launch_repo / "dev" / "launch_lane.py")
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    monkeypatch.chdir(launch_repo)
    monkeypatch.setattr(module, "_foreground_state", lambda: True)
    monkeypatch.setattr(module, "_stdout_fault", lambda: None)
    before = _worktree_rows(launch_repo)
    result = module.launch(832, "lane-832", "@agent", _head(launch_repo), [])
    captured = capsys.readouterr()
    assert result == 1
    assert "REFUSE phase=background-check" in captured.err
    assert _worktree_rows(launch_repo) == before


def test_output_safety_refusal_names_phase_and_creates_nothing(
    launch_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    spec = importlib.util.spec_from_file_location("launch_lane_pipe", launch_repo / "dev" / "launch_lane.py")
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    monkeypatch.chdir(launch_repo)
    monkeypatch.setattr(module, "_stdout_fault", lambda: "injected unsafe pipe")
    before = _worktree_rows(launch_repo)
    result = module.launch(832, "lane-832", "@agent", _head(launch_repo), [])
    captured = capsys.readouterr()
    assert result == 1
    assert "REFUSE phase=output-safety" in captured.err
    assert "injected unsafe pipe" in captured.err
    assert _worktree_rows(launch_repo) == before


def test_worktree_creation_failure_names_phase_and_inventory_stays_unchanged(
    launch_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    spec = importlib.util.spec_from_file_location("launch_lane_add", launch_repo / "dev" / "launch_lane.py")
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    monkeypatch.chdir(launch_repo)
    monkeypatch.setattr(module, "_foreground_state", lambda: None)
    monkeypatch.setattr(module, "_stdout_fault", lambda: None)
    real_git = module._git
    def fail_add(repo, *args):
        if args[:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(["git", *args], 73, "", "injected add failure\n")
        return real_git(repo, *args)
    monkeypatch.setattr(module, "_git", fail_add)
    before = _worktree_rows(launch_repo)
    result = module.launch(832, "lane-832", "@agent", _head(launch_repo), [])
    captured = capsys.readouterr()
    assert result == 1
    assert "REFUSE phase=worktree-creation" in captured.err
    assert "git worktree add exited 73" in captured.err
    assert _worktree_rows(launch_repo) == before


def test_governed_prepare_failure_reaps_created_worktree(
    launch_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    before = _worktree_rows(launch_repo)
    env = os.environ.copy(); env["DISPATCH_PREPARE_EXIT"] = "41"
    result = _run(launch_repo, _head(launch_repo), env=env)
    assert result.returncode == 1
    assert "REFUSE phase=governed-prepare" in result.stderr
    assert "existing dispatcher validation/persistence exited 41" in result.stderr
    assert "dev/reap.py cleanup exited 0" in result.stderr
    assert _worktree_rows(launch_repo) == before


def test_existing_lane_refuses_without_explicit_resume_and_changes_nothing(launch_repo: Path):
    env = os.environ.copy(); env["CCC_EXIT"] = "8"
    head = _head(launch_repo)
    first = _run(launch_repo, head, env=env)
    before = _worktree_rows(launch_repo)
    second = _run(launch_repo, head, env=env)
    assert first.returncode == 8
    assert second.returncode == 1
    assert "REFUSE phase=worktree-preflight" in second.stderr
    assert "use --resume ATTEMPT_ID" in second.stderr
    assert _worktree_rows(launch_repo) == before


def test_runner_exit_is_not_reported_as_success_and_attempt_is_durable(launch_repo: Path):
    observed = launch_repo / "observed-state"
    env = os.environ.copy(); env["CCC_EXIT"] = "7"; env["CAPTURE_ATTEMPT_STATE"] = str(observed)
    result = _run(launch_repo, _head(launch_repo), env=env)
    path, record = _attempt(launch_repo)

    assert result.returncode == 7
    assert "REFUSE phase=runner-result: runner exited 7; this is not a successful launch" in result.stderr
    assert "deliberately did not perform: worktree retirement or corpus identity deletion" in result.stderr
    assert record["runner_exit"] == 7
    assert record["state"] == "runner result verified: exit 7; worktree and exact brief retained"
    assert observed.read_text(encoding="utf-8").startswith("unverified attempt:")
    assert path.with_suffix(".prompt.md").is_file()
    assert "lane-832" in _worktree_rows(launch_repo)


def test_launcher_dispatches_brief_pys_canonical_frame(launch_repo: Path):
    captured = launch_repo / "captured-prompt.md"
    env = os.environ.copy(); env["CAPTURE_PROMPT"] = str(captured)
    result = _run(launch_repo, _head(launch_repo), env=env)
    prompt = captured.read_text(encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert prompt.count("## Canonical frame") == 1
    assert prompt.count("Lane-owns: dev/thing.py") == 1
    assert prompt.endswith("# Standing rules\nDo the checked work.\n")


def test_launcher_resolves_lane_under_the_sibling_worktree_root(launch_repo: Path):
    env = os.environ.copy(); env["CCC_EXIT"] = "7"
    result = _run(launch_repo, _head(launch_repo), env=env)
    _, record = _attempt(launch_repo)
    expected = (launch_repo.parent / ".worktrees" / "lane-832").resolve()

    assert result.returncode == 7
    resolved = Path(str(record["worktree"]))
    assert resolved == expected, (
        f"governed launcher resolved {resolved}, expected sibling lane path {expected}"
    )
    assert f"worktree {expected}" in _worktree_rows(launch_repo)
    assert not (launch_repo / ".worktrees").exists(), (
        "the governed launcher recreated the draining in-repo root"
    )


def test_changed_bytes_cannot_resume_the_same_attempt(launch_repo: Path):
    env = os.environ.copy(); env["CCC_EXIT"] = "9"
    first = _run(launch_repo, _head(launch_repo), env=env)
    _, record = _attempt(launch_repo)
    attempt_id = str(record["attempt_id"])
    before = _worktree_rows(launch_repo)
    changed = _head(
        launch_repo,
        "# Task #832 — launch it\n\nLane-owns: dev/thing.py\n\n"
        "Implement different human requested bytes.\n\n## Direction 2\n\n"
        "A missing persisted prompt would pass a corpus-only check.\n",
    )
    retry = _run(launch_repo, changed, "--resume", attempt_id, env=env)

    assert first.returncode == 9
    assert retry.returncode == 1
    assert "REFUSE phase=resume" in retry.stderr
    assert "identical-digest retry required" in retry.stderr
    assert _worktree_rows(launch_repo) == before


def test_identical_digest_resume_reuses_attempt_and_worktree(launch_repo: Path):
    env = os.environ.copy(); env["CCC_EXIT"] = "6"
    head = _head(launch_repo)
    first = _run(launch_repo, head, env=env)
    _, record = _attempt(launch_repo)
    retry = _run(launch_repo, head, "--resume", str(record["attempt_id"]), env=env)
    _, after = _attempt(launch_repo)

    assert first.returncode == retry.returncode == 6
    assert after["runs"] == 2
    assert _worktree_rows(launch_repo).count("branch refs/heads/lane-832") == 1


def test_prelaunch_persistence_failure_reuses_reap_and_leaves_no_worktree(
    launch_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    spec = importlib.util.spec_from_file_location("launch_lane_cleanup", launch_repo / "dev" / "launch_lane.py")
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    monkeypatch.chdir(launch_repo)
    monkeypatch.setattr(module, "_foreground_state", lambda: None)
    monkeypatch.setattr(module, "_stdout_fault", lambda: None)
    real_write = module._write_record
    calls = 0
    def fail_second(path, record, *, create=False):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected receipt fault")
        return real_write(path, record, create=create)
    monkeypatch.setattr(module, "_write_record", fail_second)

    result = module.launch(832, "lane-832", "@agent", _head(launch_repo), [])
    captured = capsys.readouterr()
    rows = _worktree_rows(launch_repo)
    assert result == 1
    assert "REFUSE phase=attempt-persistence" in captured.err
    assert "injected receipt fault" in captured.err
    assert "dev/reap.py cleanup exited 0" in captured.err
    assert "lane-832" not in rows
    assert _git(launch_repo, "show-ref", "--verify", "refs/heads/lane-832")


def test_tool_has_only_the_checked_reap_removal_route():
    source = TOOL.read_text(encoding="utf-8")
    assert '"worktree", "remove"' not in source
    assert 'Path(__file__).with_name("reap.py")' in source


def test_just_recipe_exposes_explicit_task_lane_agent_and_head():
    result = subprocess.run(
        ["just", "--dry-run", "launch-lane", "832", "lane", "@agent", "head.md", "-y"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'python3 dev/launch_lane.py "832" "lane" "@agent" "head.md" -y' in result.stderr
