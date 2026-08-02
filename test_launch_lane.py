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
    # brief.py imports land_lane at module level for DERIVATION_RULES (#988);
    # the real module, not a stub, so the fixture can import brief.py at all.
    _write(root / "dev" / "land_lane.py", (REPO / "dev" / "land_lane.py").read_text(encoding="utf-8"))
    # brief.py's task_record function-locally imports ledger (#1100); the real
    # module, not a stub, so brief-generation can read the fixture's tasks.md.
    # ledger.py's own imports (watch, ledger_parse, dreamwork_db, …) resolve from
    # the worktree root, which is on sys.path via pytest's cwd.
    _write(root / "dev" / "ledger.py", (REPO / "dev" / "ledger.py").read_text(encoding="utf-8"))
    _write(root / "dev" / "dispatch_lane.py", """
import argparse, os, subprocess, sys
p = argparse.ArgumentParser(); p.add_argument('--prompt'); p.add_argument('--prepare', action='store_true'); p.add_argument('rest', nargs=argparse.REMAINDER)
a = p.parse_args(); cmd = a.rest[1:] if a.rest and a.rest[0] == '--' else a.rest
prompt = open(a.prompt, encoding='utf-8').read()
if a.prepare: raise SystemExit(int(os.environ.get('DISPATCH_PREPARE_EXIT', '0')))
# Production detaches the runner (fork/setsid/execvp) and returns 0 once the
# child confirms exec — the runner's own exit is never observed by the
# dispatcher. Simulate that contract: launch the runner, then report only
# whether the LAUNCH succeeded, never the runner's exit (#1093).
if launch_exit := os.environ.get('DISPATCH_LAUNCH_EXIT'):
    raise SystemExit(int(launch_exit))
subprocess.run([*cmd, prompt])
raise SystemExit(0)
""".lstrip())
    # The production launcher deliberately routes cleanup through this sibling.
    _write(root / "dev" / "reap.py", (REPO / "dev" / "reap.py").read_text(encoding="utf-8"))
    _write(root / "seed", "base\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    bindir = tmp_path / "bin"
    _write(bindir / "ccc", """#!/usr/bin/env python3
import glob, json, os, pathlib
root = os.environ.get('LAUNCH_MAIN', os.getcwd())
if target := os.environ.get('CAPTURE_ATTEMPT_STATE'):
    record = glob.glob(root + '/.dreamwork/launch-attempts/*.json')[0]
    pathlib.Path(target).write_text(json.load(open(record))['state'], encoding='utf-8')
if target := os.environ.get('CAPTURE_PROMPT'):
    pathlib.Path(target).write_text(__import__('sys').argv[-1], encoding='utf-8')
if target := os.environ.get('CAPTURE_CWD'):
    pathlib.Path(target).write_text(os.getcwd(), encoding='utf-8')
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


def _run(
    root: Path, head: Path, *extra: str,
    env: dict[str, str] | None = None, agent: str = "@agent",
):
    actual_env = (env or os.environ.copy()).copy()
    actual_env["DREAMWORK_ALLOW_PIPED_STDOUT"] = "1"
    # The governed dispatcher now spawns the runner in the lane worktree (#1093),
    # so a fixture fake that globs a main-checkout-local dir (launch-attempts/ is
    # gitignored) must resolve that dir from the main checkout, not from its
    # inherited cwd.
    actual_env["LAUNCH_MAIN"] = str(root)
    return subprocess.run(
        [sys.executable, str(root / "dev" / "launch_lane.py"), "832", "lane-832", agent, str(head), *extra],
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
    head = _head(launch_repo)
    first = _run(launch_repo, head)
    before = _worktree_rows(launch_repo)
    second = _run(launch_repo, head)
    assert first.returncode == 0
    assert second.returncode == 1
    assert "REFUSE phase=worktree-preflight" in second.stderr
    assert "use --resume ATTEMPT_ID" in second.stderr
    assert _worktree_rows(launch_repo) == before


def test_a_crashing_runner_is_not_reported_as_success_and_attempt_is_durable(launch_repo: Path):
    """#1093: the runner is detached by dispatch_lane.py, so its own exit is
    never observed here. The dispatcher returns 0 (launch confirmed) whether
    the runner goes on to exit 0 or 7. Measured before the fix, a runner that
    crashed (CCC_EXIT=7) was recorded as ``runner result verified: exit 0``
    one second after spawn — a green-faced lie, because the 0 was the
    dispatcher's detach-confirmation, not the runner's exit. The honest record
    is ``spawned: runner detached; exit not observed`` with ``runner_exit``
    null, and "verified" is unreachable from a path that observed no exit.
    """
    observed = launch_repo / "observed-state"
    env = os.environ.copy(); env["CCC_EXIT"] = "7"; env["CAPTURE_ATTEMPT_STATE"] = str(observed)
    result = _run(launch_repo, _head(launch_repo), env=env)
    path, record = _attempt(launch_repo)

    assert result.returncode == 0
    assert record["runner_exit"] is None
    assert record["state"] == "spawned: runner detached; exit not observed; exact brief bytes preserved"
    assert "verified" not in str(record["state"])
    assert observed.read_text(encoding="utf-8").startswith("unverified attempt:")
    assert path.with_suffix(".prompt.md").is_file()
    assert "lane-832" in _worktree_rows(launch_repo)


def test_dispatcher_refusal_records_launch_refused_and_no_success_claim(launch_repo: Path):
    """#1093 direction-2 guard: when the dispatcher itself refuses (the only
    non-zero it can return in production), the attempt records ``launch
    refused`` with ``runner_exit`` null — never ``runner result verified``.
    """
    env = os.environ.copy(); env["DISPATCH_LAUNCH_EXIT"] = "2"
    result = _run(launch_repo, _head(launch_repo), env=env)
    _, record = _attempt(launch_repo)

    assert result.returncode == 2
    assert record["runner_exit"] is None
    assert record["state"] == "launch refused: dispatcher exited 2; runner not confirmed spawned; exact brief bytes preserved"
    assert "verified" not in str(record["state"])


def test_launcher_dispatches_brief_pys_canonical_frame(launch_repo: Path):
    captured = launch_repo / "captured-prompt.md"
    env = os.environ.copy(); env["CAPTURE_PROMPT"] = str(captured)
    result = _run(launch_repo, _head(launch_repo), env=env)
    assert result.returncode == 0, (
        f"canonical brief never reached the runner: {result.stderr}"
    )
    prompt = captured.read_text(encoding="utf-8")
    assert prompt.count("## Canonical frame") == 1
    assert prompt.count("Lane-owns: dev/thing.py") == 1
    assert prompt.endswith("# Standing rules\nDo the checked work.\n")


def test_launcher_resolves_lane_under_the_sibling_worktree_root(launch_repo: Path):
    result = _run(launch_repo, _head(launch_repo))
    _, record = _attempt(launch_repo)
    expected = (launch_repo.parent / ".worktrees" / "lane-832").resolve()

    assert result.returncode == 0
    resolved = Path(str(record["worktree"]))
    assert resolved == expected, (
        f"governed launcher resolved {resolved}, expected sibling lane path {expected}"
    )
    assert f"worktree {expected}" in _worktree_rows(launch_repo)
    assert not (launch_repo / ".worktrees").exists(), (
        "the governed launcher recreated the draining in-repo root"
    )


def test_runner_inherits_the_lane_worktree_as_cwd_not_the_main_checkout(launch_repo: Path):
    """#1093: ``/proc/<pid>/cwd`` is where a process was LAUNCHED, not where
    its brief tells it to work. A runner spawned with the main checkout as cwd
    holds that tree — the one directory a lane must never commit to — and a
    brief that says "work in a clone" does not move the process. The governed
    launcher must spawn the dispatcher in the lane's worktree so the detached
    runner inherits that worktree as its cwd. The fake ``ccc`` captures the
    cwd it INHERITED from the launcher's spawn (through the dispatcher stub),
    proving the assertion is load-bearing: reverting ``cwd`` to the main
    checkout makes this capture the main checkout and the test fails.
    """
    captured = launch_repo / "captured-cwd"
    env = os.environ.copy(); env["CAPTURE_CWD"] = str(captured)
    result = _run(launch_repo, _head(launch_repo), env=env)
    _, record = _attempt(launch_repo)
    expected_worktree = (launch_repo.parent / ".worktrees" / "lane-832").resolve()

    assert result.returncode == 0, result.stderr
    inherited = Path(captured.read_text(encoding="utf-8")).resolve()
    assert inherited == expected_worktree, (
        f"runner inherited cwd {inherited}, expected the lane worktree "
        f"{expected_worktree}; a runner holding the main checkout blocks every "
        "merge gate (#1093)"
    )
    assert inherited != launch_repo.resolve(), (
        "runner inherited the MAIN CHECKOUT as its cwd — this is the #1093 defect"
    )
    # The derived launch line must name the worktree it spawned into, so a reader
    # of the log can corroborate the cwd without consulting /proc.
    assert f"cwd={expected_worktree}" in result.stdout


def test_native_agent_refuses_sibling_worktree_with_remedy_before_creation(launch_repo: Path):
    before = _worktree_rows(launch_repo)
    result = _run(launch_repo, _head(launch_repo), agent="@opus5")
    expected = launch_repo.parent / ".worktrees" / "lane-832"

    assert result.returncode == 1
    assert "REFUSE phase=agent-worktree-reach" in result.stderr
    assert f"worktree {expected}" in result.stderr
    assert "use @glm52 or @cx-coder" in result.stderr
    assert "interpreter availability was not checked" in result.stderr
    assert "verified launch completion" not in result.stdout
    assert _worktree_rows(launch_repo) == before
    assert not (launch_repo / ".dreamwork" / "launch-attempts").exists()


@pytest.mark.parametrize("agent", ["@glm52", "@cx-coder"])
def test_ccc_sandbox_agents_are_not_refused_for_sibling_worktree(
    launch_repo: Path, agent: str,
):
    result = _run(launch_repo, _head(launch_repo), agent=agent)

    assert result.returncode == 0, result.stderr
    assert "REFUSE phase=agent-worktree-reach" not in result.stderr
    assert "worktree reach was not checked" in result.stdout


def test_runner_zero_names_only_the_checks_it_actually_completed(launch_repo: Path):
    result = _run(launch_repo, _head(launch_repo))

    assert result.returncode == 0, result.stderr
    # #1093: the runner is detached, so the only check the launcher completed is
    # the dispatcher's exit (the spawn); it did NOT observe a runner exit. The
    # summary must name "dispatcher exit=0" and "runner exit not observed", and
    # must not claim "verified" — that word is unreachable without an observed
    # exit.
    assert "dispatcher exit=0" in result.stdout
    assert "runner exit not observed" in result.stdout
    assert "unchecked=runner exit, worktree reach, interpreter availability, lane work" in result.stdout
    assert "verified" not in result.stdout


def test_a_spawned_runner_is_reported_as_spawned_not_not_attempted(launch_repo: Path):
    """#1093: a coordinator reading "runner not attempted" dispatched a second
    agent onto the same task twice in one session. The prepare pass honestly
    prints "runner not attempted" (it did not attempt one), but that line must
    not survive as the final word when the launcher then spawned a runner. The
    derived summary — ``launching governed runner`` before the spawn and
    ``runner spawned`` after — must state what actually happened, so the two
    outputs cannot contradict each other about whether a runner was launched.
    """
    result = _run(launch_repo, _head(launch_repo))

    assert result.returncode == 0, result.stderr
    # The prepare pass's "runner not attempted" may appear earlier (it is true
    # at that moment), but a derived launch line must also appear...
    assert "launching governed runner" in result.stdout
    # ...and the final spawn summary must state a runner was spawned.
    assert "runner spawned" in result.stdout
    assert "dispatcher exit=0" in result.stdout
    # The "runner not attempted" claim from the prepare pass must come BEFORE
    # the derived "launching governed runner" line, never after the spawn — so
    # the last runner-state statement is the derived one.
    prepare_idx = result.stdout.find("runner not attempted")
    launch_idx = result.stdout.find("launching governed runner")
    spawn_idx = result.stdout.find("runner spawned")
    assert prepare_idx != -1 or launch_idx != -1  # at least one is present
    if prepare_idx != -1:
        assert launch_idx > prepare_idx, (
            "the derived launch line must follow the prepare pass's "
            "'runner not attempted', not precede or replace it"
        )
    assert spawn_idx > launch_idx


def test_native_reach_uses_abspath_not_realpath(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("launch_lane_reach", TOOL)
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)

    assert module._native_reach_fault("@opus5", root, root / "nested" / ".." / "lane") is None
    assert module._native_reach_fault("@opus5", root, root / "linked" / "lane") is None
    assert module._native_reach_fault("@opus5", root, outside / "lane") is not None


def test_changed_bytes_cannot_resume_the_same_attempt(launch_repo: Path):
    first = _run(launch_repo, _head(launch_repo))
    _, record = _attempt(launch_repo)
    attempt_id = str(record["attempt_id"])
    before = _worktree_rows(launch_repo)
    changed = _head(
        launch_repo,
        "# Task #832 — launch it\n\nLane-owns: dev/thing.py\n\n"
        "Implement different human requested bytes.\n\n## Direction 2\n\n"
        "A missing persisted prompt would pass a corpus-only check.\n",
    )
    retry = _run(launch_repo, changed, "--resume", attempt_id)

    assert first.returncode == 0
    assert retry.returncode == 1
    assert "REFUSE phase=resume" in retry.stderr
    assert "identical-digest retry required" in retry.stderr
    assert _worktree_rows(launch_repo) == before


def test_identical_digest_resume_reuses_attempt_and_worktree(launch_repo: Path):
    head = _head(launch_repo)
    first = _run(launch_repo, head)
    _, record = _attempt(launch_repo)
    retry = _run(launch_repo, head, "--resume", str(record["attempt_id"]))
    _, after = _attempt(launch_repo)

    assert first.returncode == retry.returncode == 0
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
