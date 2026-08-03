#!/usr/bin/env python3
"""Contract tests for the checked Dreamwork lane dispatch route (#768)."""

import hashlib
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import assert_dispatch_fixture_imports, install_dispatch_fixture_imports


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "dev" / "dispatch_lane.py"
CONTRACT = (ROOT / "briefs" / "boilerplate.md").read_text(encoding="utf-8")
_BASE_SHA_LINE_FOR_TEST = re.compile(r"^Base sha: [0-9a-f]{7,40}$", re.MULTILINE)


def _ledger_fixture(root: Path) -> None:
    dreamwork = root / ".dreamwork"
    dreamwork.mkdir()
    connection = sqlite3.connect(dreamwork / "ledger.sqlite3")
    connection.execute(
        "CREATE TABLE task (id INTEGER PRIMARY KEY, state TEXT NOT NULL DEFAULT 'open')"
    )
    connection.executemany(
        "INSERT INTO task(id) VALUES (?)",
        [(task_id,) for task_id in (136, 349, 440, 671, 755, 776, 900, 901, 902, 903, 904)],
    )
    connection.commit()
    connection.close()


def _sandbox_cli(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "dev").mkdir(parents=True)
    (root / "briefs").mkdir()
    cli = root / "dev" / "dispatch_lane.py"
    shutil.copy2(CLI, cli)
    shutil.copytree(ROOT / "dreamwork_db", root / "dreamwork_db")
    install_dispatch_fixture_imports(ROOT, root, cli)
    (root / "briefs" / "boilerplate.md").write_text(CONTRACT, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "master", str(root)], check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "--allow-empty", "-qm", "base"],
        cwd=root,
        check=True,
    )
    _ledger_fixture(root)
    return cli, root


def _linked_worktree_cli(tmp_path: Path) -> tuple[Path, Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "--allow-empty", "-qm", "base"],
        cwd=main,
        check=True,
    )
    _ledger_fixture(main)
    lane = tmp_path / "lane"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "cx-linked", str(lane)],
        cwd=main,
        check=True,
    )
    (lane / "dev").mkdir()
    (lane / "briefs").mkdir()
    cli = lane / "dev" / "dispatch_lane.py"
    shutil.copy2(CLI, cli)
    shutil.copytree(ROOT / "dreamwork_db", lane / "dreamwork_db")
    install_dispatch_fixture_imports(ROOT, lane, cli)
    (lane / "briefs" / "boilerplate.md").write_text(CONTRACT, encoding="utf-8")
    return cli, main, lane


def _run(cli: Path, prompt: Path | None = None, *runner: str) -> subprocess.CompletedProcess[str]:
    mode = ["--verify-pending"] if prompt is None else ["--prompt", str(prompt), "--"]
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    return subprocess.run(
        [sys.executable, str(cli), *mode, *runner],
        capture_output=True,
        text=True,
        env=env,
    )


def test_fixture_import_preflight_names_a_real_missing_module(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    missing = root / "lane_runner_identity.py"
    assert missing.is_file(), "derived closure omitted lane_liveness's repo-root import"
    assert not (root / "watch.py").exists(), "fixture copied root modules wholesale"

    missing.unlink()
    with pytest.raises(
            AssertionError, match=r"fixture repo could not import lane_runner_identity"):
        assert_dispatch_fixture_imports(ROOT, root, cli)


def _healthy_prompt(
        tmp_path: Path, coordinator_root: Path, task: int = 900,
        lane: str = "cx-test") -> Path:
    branch = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{lane}"],
        cwd=coordinator_root,
        capture_output=True,
        text=True,
    )
    if branch.returncode != 0:
        subprocess.run(["git", "branch", lane, "master"], cwd=coordinator_root, check=True)
    base_sha = subprocess.run(
        ["git", "merge-base", "master", lane],
        cwd=coordinator_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    worktree = coordinator_root / ".worktrees" / lane
    worktree.mkdir(parents=True, exist_ok=True)
    prompt = tmp_path / f"prompt-{lane}.txt"
    prompt.write_text(
        f"# Brief — #{task}: task-specific lane head\n\n"
        f"Worktree: {worktree}\n"
        f"Branch: {lane}\n"
        f"Base sha: {base_sha}\n"
        "Coordinator inbox — ABSOLUTE path, append your completion summary "
        f"here when you finish: {coordinator_root}/.dreamwork/inbox.md\n\n"
        + CONTRACT,
        encoding="utf-8",
    )
    return prompt


def _start_live_dispatch(cli: Path, prompt: Path, worktree: Path) -> tuple[subprocess.Popen, int]:
    runner = shutil.which("perl")
    if not runner:
        pytest.skip("perl is required to distinguish the runner executable from dispatch")
    dispatcher_exe = Path(sys.executable).resolve()
    assert Path(runner).resolve() != dispatcher_exe
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    process = subprocess.Popen(
        [
            sys.executable, str(cli), "--prompt", str(prompt), "--",
            runner, "-e", "sleep 60",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    lock = worktree / ".dreamwork" / "lane.lock"
    for _ in range(250):
        if lock.is_file():
            break
        time.sleep(0.02)
    else:
        raise AssertionError(f"fixture dispatch did not write {lock}")

    # Under detach (#876) the lock records the CHILD's pid — the parent has
    # already exited. Independent truth, deliberately not derived through
    # lane_liveness.
    record = json.loads(lock.read_text(encoding="utf-8"))
    child_pid = record["pid"]
    os.kill(child_pid, 0)
    _wait_for_execed_worktree_argv(child_pid, worktree, dispatcher_exe)
    return process, child_pid


def _wait_for_execed_worktree_argv(
        child_pid: int, worktree: Path, before_exec_exe: Path,
        attempts: int = 250) -> None:
    proc = Path(f"/proc/{child_pid}")
    for _ in range(attempts):
        try:
            current_exe = Path(os.readlink(proc / "exe")).resolve()
        except FileNotFoundError:
            raise AssertionError(
                f"precondition: child pid {child_pid} vanished before exec was observed"
            ) from None
        if current_exe != before_exec_exe:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
            marker = f"Worktree: {worktree}".encode()
            assert any(marker in arg.splitlines() for arg in argv), (
                f"precondition: live child pid {child_pid} exec'd without exact "
                f"worktree line {marker.decode()!r} in argv"
            )
            return
        time.sleep(0.02)
    raise AssertionError(
        f"precondition: live child pid {child_pid} timed out waiting for exec; "
        f"/proc/{child_pid}/exe remained {before_exec_exe}"
    )


def test_exec_without_worktree_is_not_misreported_as_slow_exec(tmp_path):
    runner = shutil.which("perl")
    if not runner:
        pytest.skip("perl is required to construct an independently exec'd child")
    process = subprocess.Popen([runner, "-e", "sleep 60", "unrelated-argv"])
    try:
        with pytest.raises(AssertionError, match="exec'd without exact worktree line") as error:
            _wait_for_execed_worktree_argv(
                process.pid, tmp_path / "missing-worktree", Path(sys.executable).resolve()
            )
        assert "timed out waiting for exec" not in str(error.value)
    finally:
        process.kill()
        process.wait()


def test_worktree_text_in_pre_exec_parent_argv_does_not_fake_exec(tmp_path):
    worktree = tmp_path / "parent-only-worktree"
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)", str(worktree)]
    )
    try:
        for _ in range(100):
            raw = Path(f"/proc/{process.pid}/cmdline").read_bytes()
            if raw:
                break
            time.sleep(0.01)
        assert str(worktree).encode() in raw, "fixture must fool the old substring check"
        with pytest.raises(AssertionError, match="timed out waiting for exec") as error:
            _wait_for_execed_worktree_argv(
                process.pid, worktree, Path(sys.executable).resolve(), attempts=5
            )
        assert "exec'd without exact worktree line" not in str(error.value)
    finally:
        process.kill()
        process.wait()


def test_second_dispatch_refuses_independently_proven_live_worktree(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    lane = "cx-live-lock"
    prompt = _healthy_prompt(tmp_path, root, task=900, lane=lane)
    worktree = root / ".worktrees" / lane
    process, child_pid = _start_live_dispatch(cli, prompt, worktree)
    try:
        result = _run(cli, prompt, sys.executable, "-c", "pass")
        assert result.returncode == 2, (
            f"dispatch into {worktree} allowed through live pid {child_pid} "
            f"lane {lane}: rc={result.returncode}, stderr={result.stderr!r}"
        )
        expected = (
            f"dispatch refused: worktree {worktree} already has live lane {lane!r}: "
            f"pid {child_pid}, task #900, brief {prompt.resolve()}"
        )
        assert result.stderr.strip() == expected, (
            "dispatch failed for a reason other than the live-lane refusal: "
            f"rc={result.returncode}, stderr={result.stderr!r}"
        )
    finally:
        # Kill the live child by pid only — never pkill -f (#876 live-state rule).
        # The child is reparented (its parent exited), so we cannot waitpid it.
        try:
            os.kill(child_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for _ in range(100):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        process.wait(timeout=5)


def test_dead_pid_lock_is_retired_and_worktree_can_be_reused(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    lane = "cx-stale-lock"
    prompt = _healthy_prompt(tmp_path, root, task=901, lane=lane)
    worktree = root / ".worktrees" / lane
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait(timeout=5)
    with pytest.raises(ProcessLookupError):
        os.kill(dead.pid, 0)

    lock_dir = worktree / ".dreamwork"
    lock_dir.mkdir()
    lock = lock_dir / "lane.lock"
    lock.write_text(json.dumps({
        "pid": dead.pid,
        "task": 900,
        "lane": lane,
        "brief": "/fixture/dead-brief.md",
        "identity": str(worktree / f".{lane}-lane-identity"),
    }) + "\n", encoding="utf-8")

    result = _run(cli, prompt, sys.executable, "-c", "pass")

    assert result.returncode == 0, (
        f"stale lock for independently dead pid {dead.pid} locked out {worktree}: "
        f"stderr={result.stderr!r}"
    )
    replacement = json.loads(lock.read_text(encoding="utf-8"))
    assert replacement["pid"] != dead.pid and replacement["task"] == 901


def test_healthy_dispatch_is_silent_and_passes_prompt_as_one_argument(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    capture = tmp_path / "capture.py"
    capture.write_text(
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(sys.argv[2], encoding='utf-8')\n",
        encoding="utf-8",
    )
    delivered = tmp_path / "delivered.txt"

    result = _run(cli, prompt, sys.executable, str(capture), str(delivered))

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert delivered.read_text(encoding="utf-8") == prompt.read_text(encoding="utf-8")
    persisted = root / ".dreamwork" / "docs" / "briefs" / "900-cx-test.md"
    assert persisted.read_text(encoding="utf-8") == prompt.read_text(encoding="utf-8")
    assert persisted.with_suffix(".sha256").is_file()


def test_dispatch_gives_each_lane_a_fresh_rediscoverable_identity(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    capture = tmp_path / "capture.py"
    capture.write_text(
        "import os, pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(os.environ['DREAMWORK_LANE_ID'])\n",
        encoding="utf-8",
    )
    identities = []
    for number in (901, 902):
        prompt = _healthy_prompt(tmp_path, root, task=number,
                                 lane=f"cx-{number}")
        delivered = tmp_path / f"identity-{number}"
        result = _run(cli, prompt, sys.executable, str(capture), str(delivered))
        assert result.returncode == 0, result.stderr
        identities.append(delivered.read_text())

    assert all(len(value) == 32 for value in identities)
    assert identities[0] != identities[1]


def test_dispatch_refuses_pipe_before_short_reader_can_kill_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    started = tmp_path / "runner-started"
    writer = (
        "import pathlib,signal,sys,time; "
        "pathlib.Path(sys.argv[1]).touch(); "
        "signal.signal(signal.SIGPIPE,signal.SIG_DFL); "
        "[(print(i,flush=True),time.sleep(.01)) for i in range(10000)]"
    )
    process = subprocess.Popen(
        [sys.executable, str(cli), "--prompt", str(prompt), "--",
         sys.executable, "-c", writer, str(started)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    lines = [process.stdout.readline() for _ in range(3)]
    process.stdout.close()
    returncode = process.wait(timeout=5)
    assert process.stderr is not None
    stderr = process.stderr.read()

    assert returncode == 2, (
        f"dispatcher reached the runner and died from SIGPIPE ({returncode})"
    )
    assert lines == ["", "", ""]
    assert "stdout is a pipe whose reader can close early" in stderr
    assert "DREAMWORK_ALLOW_PIPED_STDOUT=1" in stderr
    assert not started.exists(), "runner launched before the pipe refusal"


def test_dispatch_refuses_socket_before_peer_can_kill_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    started = tmp_path / "runner-started"
    writer = (
        "import pathlib,signal,sys,time; "
        "pathlib.Path(sys.argv[1]).touch(); "
        "signal.signal(signal.SIGPIPE,signal.SIG_DFL); "
        "[(print(i,flush=True),time.sleep(.01)) for i in range(10000)]"
    )
    reader, child_stdout = socket.socketpair()
    try:
        process = subprocess.Popen(
            [sys.executable, str(cli), "--prompt", str(prompt), "--",
             sys.executable, "-c", writer, str(started)],
            stdout=child_stdout,
            stderr=subprocess.PIPE,
            text=True,
        )
    finally:
        child_stdout.close()
    with reader.makefile("r", encoding="utf-8") as stream:
        lines = [stream.readline() for _ in range(3)]
    reader.close()
    returncode = process.wait(timeout=5)
    assert process.stderr is not None
    stderr = process.stderr.read()

    assert returncode == 2, (
        f"dispatcher reached the runner and died from SIGPIPE ({returncode})"
    )
    assert lines == ["", "", ""]
    assert "stdout is a socket whose peer can close early" in stderr
    assert "DREAMWORK_ALLOW_PIPED_STDOUT=1" in stderr
    assert not started.exists(), "runner launched before the socket refusal"


def test_explicit_pipe_override_launches_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)

    result = _run(cli, prompt, sys.executable, "-c", "print('launched')")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "launched\n"


def _wait_for_file(path: Path, timeout: float = 5.0) -> bool:
    """Poll for a file's appearance — the detached runner may not finish instantly."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.02)
    return path.is_file()


def test_tty_stdout_launches_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    launched = tmp_path / "tty-launched"
    master, slave = os.openpty()
    try:
        process = subprocess.Popen(
            [sys.executable, str(cli), "--prompt", str(prompt), "--",
             sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()",
             str(launched)],
            stdout=slave,
            stderr=slave,
        )
    finally:
        os.close(slave)
    process.wait(timeout=5)
    os.close(master)

    assert process.returncode == 0
    assert _wait_for_file(launched), "detached runner did not touch launched file"


def test_regular_file_redirect_launches_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    launched = tmp_path / "file-launched"
    output = tmp_path / "dispatch.log"
    with output.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            [sys.executable, str(cli), "--prompt", str(prompt), "--",
             sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()",
             str(launched)],
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
        )

    assert result.returncode == 0
    assert _wait_for_file(launched), "detached runner did not touch launched file"


def test_inherited_stdout_launches_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    launched = tmp_path / "inherited-stdout-launched"

    result = subprocess.run(
        [sys.executable, str(cli), "--prompt", str(prompt), "--",
         sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()",
         str(launched)],
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert _wait_for_file(launched), "detached runner did not touch launched file"


def test_dev_null_stdout_launches_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    launched = tmp_path / "dev-null-launched"

    result = subprocess.run(
        [sys.executable, str(cli), "--prompt", str(prompt), "--",
         sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()",
         str(launched)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert _wait_for_file(launched), "detached runner did not touch launched file"


def test_background_regular_file_redirect_launches_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    launched = tmp_path / "background-launched"
    output = tmp_path / "background.log"
    with output.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            [sys.executable, str(cli), "--prompt", str(prompt), "--",
             sys.executable, "-c",
             "import pathlib,sys,time; time.sleep(.1); pathlib.Path(sys.argv[1]).touch()",
             str(launched)],
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    returncode = process.wait(timeout=5)

    assert returncode == 0
    assert _wait_for_file(launched), "detached runner did not touch launched file"


def test_unresolved_ledger_get_is_reported_but_does_not_block(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    prompt.write_text(
        prompt.read_text(encoding="utf-8").replace(
            "\n\n" + CONTRACT,
            "\n\nRun `python3 dev/ledger.py get 199`.\n\n" + CONTRACT,
        ),
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 0
    assert "ledger.py get 199 names #199, which does not exist" in result.stderr
    assert "launch allowed because instruction and quotation" in result.stderr


def test_retired_bare_citation_reports_without_blocking_healthy_brief(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    prompt.write_text(
        prompt.read_text(encoding="utf-8").replace(
            "\n\n" + CONTRACT,
            "\n\nReal tasks #671, #440, and #755 apply; #199's lesson is historical.\n\n"
            + CONTRACT,
        ),
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 0
    assert "unresolved bare citation(s) #199" in result.stderr
    assert "ledger.py get 199" not in result.stderr


def test_unavailable_ledger_is_reported_and_does_not_block(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    (root / ".dreamwork" / "ledger.sqlite3").unlink()
    prompt = _healthy_prompt(tmp_path, root)

    result = _run(cli, prompt, "true")

    assert result.returncode == 0
    assert "ledger reference check DID NOT RUN" in result.stderr
    assert "launch allowed" in result.stderr


def test_locked_ledger_is_reported_and_does_not_block(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    lock = sqlite3.connect(root / ".dreamwork" / "ledger.sqlite3")
    lock.execute("BEGIN EXCLUSIVE")
    try:
        result = _run(cli, prompt, "true")
    finally:
        lock.rollback()
        lock.close()

    assert result.returncode == 0
    assert "ledger reference check DID NOT RUN" in result.stderr
    assert "database is locked" in result.stderr
    assert "launch allowed" in result.stderr


def test_unclassified_core_read_failure_is_reported_and_does_not_block(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    store = root / ".dreamwork" / "ledger.sqlite3"
    connection = sqlite3.connect(store)
    connection.execute("ALTER TABLE task RENAME COLUMN state TO unknown_state")
    connection.commit()
    connection.close()
    prompt = _healthy_prompt(tmp_path, root)

    result = _run(cli, prompt, "true")

    assert result.returncode == 0
    assert "ledger reference check DID NOT RUN" in result.stderr
    assert "no such column: state" in result.stderr
    assert "launch allowed" in result.stderr


def _land_task_in_fixture(root: Path, task_id: int) -> None:
    """Mark a fixture task LANDED without touching the shared _ledger_fixture.

    Asserts the update took (rowcount 1) so a silently-missed id -- the
    precondition the refuse depends on -- cannot let the test pass vacuously.
    """
    connection = sqlite3.connect(root / ".dreamwork" / "ledger.sqlite3")
    cursor = connection.execute(
        "UPDATE task SET state = 'landed' WHERE id = ?", (task_id,))
    assert cursor.rowcount == 1, f"precondition: task #{task_id} not in fixture store"
    connection.commit()
    connection.close()


def test_dispatch_refuses_brief_whose_primary_task_has_already_landed(tmp_path):
    # #1125: landing is terminal, so a brief whose primary task has LANDED is
    # stale by construction -- the record moved past its premise of open work.
    # This is the one head-vs-record supersession signal a dispatcher can detect
    # without reading prose; every broader signal is wallpaper (measured against
    # the live store: a citation-to-landed check fires 71x on one brief, and
    # "the record moved since the head was written" fires on 77% of dispatches).
    cli, root = _sandbox_cli(tmp_path)
    _land_task_in_fixture(root, 900)
    prompt = _healthy_prompt(tmp_path, root, task=900, lane="cx-stale")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2, (
        f"landed primary #900 was not refused (rc={result.returncode}); the "
        f"#1125 head-vs-record state guard did not fire. stderr={result.stderr!r}"
    )
    assert "task #900 is LANDED" in result.stderr
    assert "already-resolved work" in result.stderr
    # #651 ceiling, in the check's own output (#1114 idiom): the message names
    # the task's STATE, not the head's full claims.
    assert "names the task's STATE, not the head's full claims (#651)" in result.stderr
    # The refuse fires before persist, so nothing is written for resolved work.
    assert not (root / ".dreamwork" / "docs" / "briefs" / "900-cx-stale.md").exists()


def test_landed_citation_is_not_the_primary_so_dispatch_proceeds(tmp_path):
    # The guard keys on the PRIMARY task (the heading id), not on any landed
    # citation. A brief for an OPEN task that cites a LANDED sibling must NOT
    # refuse: landed citations are usually lesson authority, not live premises
    # (measured: 71 of 79 citations in a real brief are to landed tasks, so a
    # per-citation landed check is wallpaper). This binds that narrowness.
    cli, root = _sandbox_cli(tmp_path)
    _land_task_in_fixture(root, 901)
    prompt = _healthy_prompt(tmp_path, root, task=900, lane="cx-citeslanded")
    prompt.write_text(
        prompt.read_text(encoding="utf-8").replace(
            "\n\n" + CONTRACT,
            "\n\nRelated: #901 landed a fix this builds on.\n\n" + CONTRACT,
        ),
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 0, result.stderr
    assert "is LANDED" not in result.stderr


def test_dispatch_refuses_landed_primary_in_prepare_mode(tmp_path):
    # The guard runs before persist, which --prepare also reaches, so a landed
    # task cannot even be prepared for dispatch.
    cli, root = _sandbox_cli(tmp_path)
    _land_task_in_fixture(root, 902)
    prompt = _healthy_prompt(tmp_path, root, task=902, lane="cx-prepstale")

    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--prepare", "--prompt", str(prompt)],
        capture_output=True, text=True, env=env,
    )

    assert result.returncode == 2
    assert "task #902 is LANDED" in result.stderr


def test_dispatch_refuses_the_ambiguous_hand_off_wording(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    prompt.write_text(
        prompt.read_text(encoding="utf-8").replace(
            "append your completion summary here when you finish",
            "append your hand-off line here when you finish",
        ),
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "exactly this unambiguous coordinator inbox instruction" in result.stderr
    assert not (root / ".dreamwork" / "docs" / "briefs").exists()


def test_dispatch_refuses_a_well_formed_but_fake_inbox(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    prompt.write_text(
        prompt.read_text(encoding="utf-8").replace(
            f"{root}/.dreamwork/inbox.md", "/tmp/stale/inbox.md"
        ),
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert str(root / ".dreamwork" / "inbox.md") in result.stderr
    assert not (root / ".dreamwork" / "docs" / "briefs").exists()


def test_dispatch_refuses_missing_base_sha_with_discriminating_message(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    prompt.write_text(
        "\n".join(
            line for line in prompt.read_text(encoding="utf-8").splitlines()
            if not line.startswith("Base sha:")
        ) + "\n",
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert "missing required 'Base sha: <git revision>' line" in result.stderr
    assert result.returncode == 2
    assert not (root / ".dreamwork" / "docs" / "briefs").exists()


def test_40_hex_shape_that_does_not_resolve_is_refused(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    prompt.write_text(
        _BASE_SHA_LINE_FOR_TEST.sub("Base sha: " + "f" * 40, prompt.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "does not resolve to a commit" in result.stderr


def test_real_commit_that_is_not_branch_point_is_refused(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "--allow-empty", "-qm", "later master"],
        cwd=root,
        check=True,
    )
    wrong_real_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    prompt.write_text(
        _BASE_SHA_LINE_FOR_TEST.sub(
            f"Base sha: {wrong_real_sha}", prompt.read_text(encoding="utf-8")
        ),
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert f"resolves to {wrong_real_sha}, but does not match branch point" in result.stderr


def test_linked_worktree_dispatch_persists_only_to_main_corpus(tmp_path):
    cli, main, lane = _linked_worktree_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, main, task=903, lane="cx-linked")

    result = _run(cli, prompt, "true")

    assert result.returncode == 0, result.stderr
    corpus_artifact = main / ".dreamwork" / "docs" / "briefs" / "903-cx-linked.md"
    assert corpus_artifact.is_file(), (
        f"validated brief did not reach the main corpus: {corpus_artifact}"
    )
    assert corpus_artifact.read_text(encoding="utf-8") == prompt.read_text(encoding="utf-8")
    assert corpus_artifact.with_suffix(".sha256").is_file()
    assert not (lane / ".dreamwork" / "docs" / "briefs").exists(), (
        "validated brief leaked into the linked worktree instead of the main corpus"
    )


def test_valid_pair_outside_corpus_does_not_count_as_verified(tmp_path):
    cli, main, lane = _linked_worktree_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, main, task=904, lane="cx-linked")
    content = prompt.read_text(encoding="utf-8")
    wrong_dir = lane / ".dreamwork" / "docs" / "briefs"
    wrong_dir.mkdir(parents=True)
    artifact = wrong_dir / "904-cx-linked.md"
    artifact.write_text(content, encoding="utf-8")
    artifact.with_suffix(".sha256").write_text(
        f"{hashlib.sha256(content.encode('utf-8')).hexdigest()}  {artifact.name}\n",
        encoding="utf-8",
    )

    result = _run(cli)

    assert result.returncode == 2
    assert "DID NOT VERIFY" in result.stderr


def test_corpus_resolution_failure_is_distinct_from_persistence_failure(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    (root / ".git").rename(root / "not-git")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "could not determine brief corpus" in result.stderr
    assert "could not create brief corpus" not in result.stderr


def test_relative_git_common_dir_is_rejected(tmp_path, monkeypatch):
    cli, _ = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, tmp_path / "repo")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\nprintf '.git\\n'\n", encoding="utf-8")
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ['PATH']}")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "git returned a relative common directory" in result.stderr


def test_same_task_dispatches_to_distinct_lanes_do_not_collide(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    first = _healthy_prompt(tmp_path, root, task=901, lane="cx-one")
    second = _healthy_prompt(tmp_path, root, task=901, lane="cx-two")

    assert _run(cli, first, "true").returncode == 0
    assert _run(cli, second, "true").returncode == 0

    briefs = root / ".dreamwork" / "docs" / "briefs"
    assert (briefs / "901-cx-one.md").read_text(encoding="utf-8") == first.read_text(encoding="utf-8")
    assert (briefs / "901-cx-two.md").read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_persistence_failure_refuses_and_names_what_was_not_persisted(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    briefs = root / ".dreamwork" / "docs" / "briefs"
    briefs.parent.mkdir(parents=True)
    briefs.write_text("not a directory", encoding="utf-8")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "could not persist validated brief" in result.stderr
    assert str(briefs) in result.stderr


def test_unnameable_prompt_refuses_before_runner_exec(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = tmp_path / "prompt-without-lane.txt"
    prompt.write_text(
        "# Brief — #902: no branch identity\n\n"
        "Coordinator inbox — ABSOLUTE path, append your completion summary "
        f"here when you finish: {root}/.dreamwork/inbox.md\n\n" + CONTRACT,
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "no unique 'Branch: <lane>' line" in result.stderr
    assert not (root / ".dreamwork" / "docs" / "briefs").exists()


def test_verify_pending_rejects_changed_artifact(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    assert _run(cli, prompt, "true").returncode == 0
    artifact = root / ".dreamwork" / "docs" / "briefs" / "900-cx-test.md"
    artifact.write_text("wrong artifact\n", encoding="utf-8")

    result = _run(cli)

    assert result.returncode == 2
    assert "changed after dispatch-time persistence" in result.stderr


def test_verify_pending_rejects_absent_artifact(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root, task=173, lane="cx-legacy")
    assert _run(cli, prompt, "true").returncode == 0
    artifact = root / ".dreamwork" / "docs" / "briefs" / "173-cx-legacy.md"
    artifact.unlink()

    result = _run(cli)

    assert result.returncode == 2
    assert (
        "integrity receipt 173-cx-legacy.sha256 has no brief artifact "
        "173-cx-legacy.md"
    ) in result.stderr


def test_verify_pending_accepts_receipted_briefs_on_both_sides_of_cutoff(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    legacy = _healthy_prompt(tmp_path, root, task=173, lane="cx-legacy")
    governed = _healthy_prompt(tmp_path, root, task=900, lane="cx-governed")
    assert _run(cli, legacy, "true").returncode == 0
    assert _run(cli, governed, "true").returncode == 0

    result = _run(cli)

    assert result.returncode == 0, result.stderr
    assert "brief integrity verified: 2 governed brief(s) matched receipts" in result.stdout


def test_commit_corpus_stages_receipted_pairs_on_both_sides_of_cutoff(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    shutil.copy2(ROOT / "justfile", root / "justfile")
    briefs = root / ".dreamwork" / "docs" / "briefs"
    briefs.mkdir(parents=True)
    (briefs / "100-historical.md").write_text("predates receipts\n", encoding="utf-8")
    legacy = _healthy_prompt(tmp_path, root, task=173, lane="cx-legacy")
    governed = _healthy_prompt(tmp_path, root, task=900, lane="cx-governed")
    assert _run(cli, legacy, "true").returncode == 0
    assert _run(cli, governed, "true").returncode == 0

    result = subprocess.run(
        ["just", "commit-corpus"], cwd=root, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert "staged 2 brief/receipt pair(s)" in result.stdout
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert staged == [
        ".dreamwork/docs/briefs/173-cx-legacy.md",
        ".dreamwork/docs/briefs/173-cx-legacy.sha256",
        ".dreamwork/docs/briefs/900-cx-governed.md",
        ".dreamwork/docs/briefs/900-cx-governed.sha256",
    ]


def test_verify_pending_that_examined_nothing_does_not_pass(tmp_path):
    cli, _ = _sandbox_cli(tmp_path)

    result = _run(cli)

    assert result.returncode == 2
    assert "DID NOT VERIFY" in result.stderr


def test_literal_command_substitution_refuses_and_names_missing_contract(tmp_path):
    cli, _ = _sandbox_cli(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("$(cat /tmp/lane/p766.txt)\n", encoding="utf-8")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "standing contract from briefs/boilerplate.md is missing or altered" in result.stderr


def test_long_prompt_without_rules_does_not_pass(tmp_path):
    cli, _ = _sandbox_cli(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("task detail " * 10_000, encoding="utf-8")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "standing contract" in result.stderr


def test_one_magic_phrase_does_not_pass(tmp_path):
    cli, _ = _sandbox_cli(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Never merge, never push.\n", encoding="utf-8")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "standing contract" in result.stderr


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_contract_as_quoted_example_does_not_pass(tmp_path, fence):
    cli, _ = _sandbox_cli(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "This is quoted reference material, not an instruction:\n"
        f"{fence}markdown\n{CONTRACT}{fence}\n",
        encoding="utf-8",
    )

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "inside a fenced quotation" in result.stderr


def test_unreadable_and_empty_are_distinct_from_invalid(tmp_path):
    cli, _ = _sandbox_cli(tmp_path)
    missing = tmp_path / "missing.txt"
    unreadable = _run(cli, missing, "true")
    assert unreadable.returncode == 2
    assert "could not read prompt" in unreadable.stderr
    assert "standing contract" not in unreadable.stderr

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    empty_result = _run(cli, empty, "true")
    assert empty_result.returncode == 2
    assert "prompt is empty" in empty_result.stderr


def test_no_runner_is_a_distinct_usage_fault(tmp_path):
    cli, _ = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, tmp_path / "repo")

    result = _run(cli, prompt)

    assert result.returncode == 2
    assert "runner command is missing" in result.stderr


def test_prepare_persists_exact_brief_before_the_lane_branch_exists(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root, lane="not-created-yet")
    subprocess.run(["git", "branch", "-D", "not-created-yet"], cwd=root, check=True,
                   capture_output=True, text=True)
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}

    prepared = subprocess.run(
        [sys.executable, str(cli), "--prompt", str(prompt), "--prepare"],
        capture_output=True, text=True, env=env,
    )

    assert prepared.returncode == 0, prepared.stderr
    assert "runner not attempted" in prepared.stdout
    persisted = root / ".dreamwork" / "docs" / "briefs" / "900-not-created-yet.md"
    assert persisted.read_bytes() == prompt.read_bytes()
    assert persisted.with_suffix(".sha256").is_file()


def test_just_recipe_is_the_documented_ccc_route():
    justfile = (ROOT / "justfile").read_text(encoding="utf-8")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "dispatch-lane prompt agent *CCC_ARGS:" in justfile
    assert "python3 dev/dispatch_lane.py" in justfile
    assert "just dispatch-lane <prompt-file> <@agent>" in " ".join(skill.split())
    assert "Direct `ccc` lane dispatch is unsupported" in skill


def test_dispatch_lane_recipe_is_at_prefixed_so_the_route_is_silent():
    """The supported route is `just dispatch-lane`, not the bare wrapper.
    `just` echoes every un-@-prefixed recipe line before running it, so without
    the '@' the route prints the expanded command on every healthy dispatch —
    contradicting the wrapper's own silence and the #768 ledger's claim that
    'contract-appended is rc=0 and SILENT (#755)'.  The assertion would fail if
    someone removed the '@' prefix from the dispatch-lane recipe body."""
    justfile = (ROOT / "justfile").read_text(encoding="utf-8")
    recipe_start = justfile.index("dispatch-lane prompt agent *CCC_ARGS:")
    # Scope to the dispatch-lane recipe only, not to EOF: other recipes
    # legitimately call dispatch_lane.py (e.g. --verify-pending in
    # commit-corpus), and slicing to the end of file would count them.
    next_recipe = justfile.find("\n\n#", recipe_start)
    recipe_body = justfile[recipe_start : next_recipe if next_recipe > 0 else len(justfile)]
    recipe_lines = [
        line for line in recipe_body.splitlines()
        if "dispatch_lane.py" in line and not line.lstrip().startswith("#")
    ]
    assert len(recipe_lines) == 1, "expected exactly one dispatch_lane.py line"
    assert recipe_lines[0].lstrip().startswith("@"), (
        "dispatch-lane recipe must be @-prefixed: without it just echoes the "
        "expanded command on every dispatch, so the route is not silent (#769)"
    )


# --------------------------------------------------------------------------- #
# #876: a lane must survive its launcher                                       #
# --------------------------------------------------------------------------- #

def test_detached_runner_survives_launcher_exit_in_distinct_session(tmp_path):
    """The runner runs in its own session and is alive AFTER the launcher exits."""
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    # The runner writes its own pid + session id, then stays alive long enough
    # to be observed after the launcher has exited.
    witness = tmp_path / "session-witness.txt"
    runner = tmp_path / "survivor.py"
    runner.write_text(
        "import os, pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text("
        "f\"{os.getpid()}\\n{os.getsid(0)}\\n\", encoding='utf-8')\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    parent_sid = os.getsid(os.getpid())
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    log = tmp_path / "dispatch.log"
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            [sys.executable, str(cli), "--prompt", str(prompt), "--",
             sys.executable, str(runner), str(witness)],
            stdout=stream, stderr=subprocess.STDOUT, env=env,
        )
    # The launcher (parent) exits 0 — that is the precondition for "survives."
    returncode = process.wait(timeout=5)
    assert returncode == 0, (
        f"launcher exited {returncode}, expected 0 (successful detached launch)"
    )

    assert _wait_for_file(witness), "detached runner never wrote its session witness"
    lines = witness.read_text(encoding="utf-8").strip().split("\n")
    runner_pid = int(lines[0])
    runner_sid = int(lines[1])
    assert runner_sid != parent_sid, (
        f"runner session {runner_sid} == launcher session {parent_sid}; "
        f"the lane was NOT detached — reaping the launcher would kill it"
    )
    # The runner IS alive AFTER the launcher exited (process.wait returned above).
    os.kill(runner_pid, 0)
    # Clean up: kill by pid only — never pkill -f (#876 live-state rule).
    try:
        os.kill(runner_pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for _ in range(100):
        try:
            os.kill(runner_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)


def test_detached_dispatch_still_refuses_bad_base_sha_before_fork(tmp_path):
    """Early refusals (base-sha) still surface as exit 2 after detaching."""
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)
    prompt.write_text(
        "\n".join(
            line for line in prompt.read_text(encoding="utf-8").splitlines()
            if not line.startswith("Base sha:")
        ) + "\n",
        encoding="utf-8",
    )
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--prompt", str(prompt), "--", "true"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 2
    assert "missing required 'Base sha: <git revision>' line" in result.stderr
    # No lane.lock should exist — the refusal happened before fork.
    assert not any(root.rglob("lane.lock"))


# --- #1056: review dispatch pins a sha and warns on a live lane ------------

REVIEW_FRAME = (ROOT / "briefs" / "review-frame.md").read_text(encoding="utf-8")


def _import_dispatch_lane():
    """Import the worktree's dev/dispatch_lane.py for unit-level liveness tests.

    The CLI tests shell out; the liveness helper takes injectable process
    readers, so testing it in-process lets a fake process table prove the
    self-exclusion and examined-count properties directly.
    """
    sys.path.insert(0, str(ROOT / "dev"))
    import dispatch_lane
    return dispatch_lane


def _sandbox_review_cli(tmp_path: Path, branch: str = "cx-review") -> tuple[Path, Path]:
    """A sandbox with boilerplate + review-frame, plus a real branch for sha pinning."""
    cli, root = _sandbox_cli(tmp_path)
    (root / "briefs" / "review-frame.md").write_text(REVIEW_FRAME, encoding="utf-8")
    subprocess.run(["git", "branch", branch, "master"], cwd=root, check=True)
    return cli, root


def _review_prompt(tmp_path: Path, root: Path, branch: str = "cx-review") -> Path:
    """A minimal valid review prompt: task head + review frame (verbatim, last)."""
    prompt = tmp_path / f"review-{branch}.txt"
    prompt.write_text(
        f"# Review — branch {branch}\n\n"
        f"Branch under review: {branch}\n\n"
        + REVIEW_FRAME,
        encoding="utf-8",
    )
    return prompt


def _run_review(cli: Path, prompt: Path, branch: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    return subprocess.run(
        [sys.executable, str(cli), "--review-prompt", str(prompt),
         "--review-branch", branch],
        capture_output=True, text=True, env=env,
    )


def test_launch_review_creates_attached_branch_worktree_and_records_cwd(tmp_path):
    """The supported launch path must never recreate #1163's detached checkout.

    The branch-line assertion is independent of the production helper: it reads
    Git's porcelain worktree record, the same evidence lane containment sees.
    """
    branch = "cx-review"
    cli, root = _sandbox_review_cli(tmp_path, branch)
    prompt = _review_prompt(tmp_path, root, branch)
    observed = tmp_path / "review-runner.json"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ccc = fake_bin / "ccc"
    fake_ccc.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['REVIEW_TEST_OUTPUT']).write_text(json.dumps({\n"
        "    'argv': sys.argv[1:], 'cwd': os.getcwd(),\n"
        "    'role': os.environ.get('DREAMWORK_LANE_ROLE'),\n"
        "}), encoding='utf-8')\n"
        "os.execlp('sleep', 'ccc', '2')\n",
        encoding="utf-8",
    )
    fake_ccc.chmod(0o755)
    env = {
        **os.environ,
        "DREAMWORK_ALLOW_PIPED_STDOUT": "1",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "REVIEW_TEST_OUTPUT": str(observed),
        "REVIEW_RUNNER_SETTLE": "0.05",
    }
    result = subprocess.run(
        [
            sys.executable, str(cli), "--launch-review", str(prompt),
            "--review-branch", branch, "--review-round", "2", "--",
            "ccc", "--permission-mode", "plan", "@cx-reviewer",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    for _ in range(100):
        if observed.is_file():
            break
        time.sleep(0.01)
    payload = json.loads(observed.read_text(encoding="utf-8"))

    review_lane = "cx-review-review-r2"
    review_worktree = tmp_path / ".worktrees" / review_lane
    porcelain = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    block = next(
        part for part in porcelain.split("\n\n")
        if f"worktree {review_worktree}" in part
    )
    assert f"branch refs/heads/{review_lane}" in block, (
        "review worktree has no attached branch line"
    )
    assert "detached" not in block
    attempts = sorted((root / ".dreamwork" / "review-dispatches").glob("*.launch.json"))
    assert len(attempts) == 1
    attempt = json.loads(attempts[0].read_text(encoding="utf-8"))
    format_row = next(
        line for line in (ROOT / "file-formats.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| `.dreamwork/review-dispatches/")
        and ".launch.json`" in line
    )
    field_clause = format_row.split("JSON fields: ", 1)[1].split(". Meanings:", 1)[0]
    documented_fields = re.findall(r"`([a-z][a-z0-9_]*)`", field_clause)
    assert len(documented_fields) == len(set(documented_fields))
    assert set(documented_fields) == set(attempt), (
        "review launch format field list drifted: "
        f"documented={sorted(documented_fields)} actual={sorted(attempt)}"
    )
    persisted_prompt = Path(attempt["prompt"]).read_text(encoding="utf-8")
    assert payload == {
        "argv": ["--permission-mode", "plan", "@cx-reviewer", persisted_prompt],
        "cwd": str(review_worktree),
        "role": "reviewer",
    }
    assert attempt["review_lane"] == review_lane
    assert attempt["worktree"] == str(review_worktree)
    assert subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=review_worktree,
        capture_output=True, text=True, check=True,
    ).stdout.strip() == attempt["pinned_sha"]
    assert attempt["state"] == (
        "spawned: reviewer present in review worktree (cwd-containment); "
        "runner exit not observed"
    )


@pytest.mark.parametrize("write_controls", [
    ["-y"],
    ["--permission-mode", "plan", "--permission-mode", "yolo"],
])
def test_launch_review_refuses_write_capable_runner_mode(tmp_path, write_controls):
    cli, root = _sandbox_review_cli(tmp_path)
    prompt = _review_prompt(tmp_path, root)
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [
            sys.executable, str(cli), "--launch-review", str(prompt),
            "--review-branch", "cx-review", "--",
            "ccc", *write_controls, "@cx-reviewer",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "review launch requires ccc --permission-mode plan @cx-reviewer" in result.stderr
    assert not (tmp_path / ".worktrees" / "cx-review-review-r1").exists()


def _fake_lane_runner(worktree: Path, name: str = "ccc") -> subprocess.Popen:
    """A short-lived process whose argv[0] basename is a lane runner name,
    with its cwd set inside ``worktree`` (#1056's endorsed fixture).

    A symlink ``<name> -> sleep`` is exec'd with argv ``[<link>, "60"]``: the
    kernel resolves the target but keeps argv[0] as the link path, so
    /proc/<pid>/cmdline's first element has basename ``name`` — exactly what
    lane_liveness._is_lane_runner keys on. A #!/bin/sh script would NOT work:
    the shebang rewrites argv[0] to the interpreter, so the basename check fails.
    """
    worktree.mkdir(parents=True, exist_ok=True)
    sleep_bin = shutil.which("sleep")
    if not sleep_bin:
        pytest.skip("sleep is required for the fake runner fixture")
    link = worktree / name
    if not link.exists():
        link.symlink_to(sleep_bin)
    proc = subprocess.Popen(
        [str(link), "60"], cwd=str(worktree),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(150):
        try:
            cwd = os.readlink("/proc/%d/cwd" % proc.pid)
            raw = Path("/proc/%d/cmdline" % proc.pid).read_bytes()
            first = raw.split(b"\x00", 1)[0]
            if (cwd and os.path.basename(first.decode("utf-8", "replace")) == name
                    and (cwd == str(worktree.resolve())
                         or cwd.startswith(str(worktree.resolve()) + os.sep))):
                return proc
        except FileNotFoundError:
            break
        time.sleep(0.02)
    raise AssertionError(f"fake runner {proc.pid} did not settle in {worktree}")


def _review_receipt(root: Path, branch: str) -> dict:
    """Read the persisted review-dispatch receipt JSON for ``branch``."""
    dispatches = root / ".dreamwork" / "review-dispatches"
    matches = sorted(dispatches.glob(f"{branch}-r*.json"))
    assert matches, f"no review-dispatch receipt for {branch} in {dispatches}"
    return json.loads(matches[-1].read_text(encoding="utf-8"))


def _review_persisted_prompt(root: Path, branch: str) -> str:
    dispatches = root / ".dreamwork" / "review-dispatches"
    matches = sorted(dispatches.glob(f"{branch}-r*.prompt.md"))
    assert matches, f"no review-dispatch prompt for {branch}"
    return matches[-1].read_text(encoding="utf-8")


def test_review_persists_pinned_sha_when_no_live_lane(tmp_path):
    """No live runner → dispatch proceeds with no liveness warning; the receipt
    carries the pinned sha and the prompt head carries the sha line (#1056)."""
    cli, root = _sandbox_review_cli(tmp_path)
    branch = "cx-review"
    prompt = _review_prompt(tmp_path, root, branch)
    expected_sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", branch],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    result = _run_review(cli, prompt, branch)
    assert result.returncode == 0, result.stderr
    assert "live lane runner" not in result.stderr
    receipt = _review_receipt(root, branch)
    assert receipt["pinned_sha"] == expected_sha, receipt
    persisted = _review_persisted_prompt(root, branch)
    assert "Review sha (pinned at dispatch, #1056): %s" % expected_sha in persisted


def test_review_warns_but_proceeds_when_live_lane_runner_present(tmp_path):
    """A live runner in the branch worktree → the dispatch WARNS (naming the
    branch), proceeds (exit 0), and still pins the sha — warn not refuse, so a
    hung lane stays reviewable with the sha as backstop (#1056)."""
    cli, root = _sandbox_review_cli(tmp_path)
    branch = "cx-review"
    worktree = root / ".worktrees" / branch
    proc = _fake_lane_runner(worktree)
    try:
        prompt = _review_prompt(tmp_path, root, branch)
        result = _run_review(cli, prompt, branch)
        assert result.returncode == 0, result.stderr
        assert "live lane runner" in result.stderr, result.stderr
        assert branch in result.stderr, result.stderr
        assert "examined" in result.stderr, result.stderr
        # Dispatch proceeded despite the warning: the receipt exists with a pin.
        receipt = _review_receipt(root, branch)
        assert receipt["pinned_sha"] is not None, receipt
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_review_liveness_counts_runner_via_cwd_never_argv(tmp_path):
    """The runner is detected by cwd, and the argv-embedding trap (#729) is
    avoided: a NON-runner process (basename not in the runner set) sharing the
    worktree cwd is NOT counted as live."""
    dl = _import_dispatch_lane()
    # The scan checks candidate paths worktree_paths derives from coordinator
    # root (tmp_path.parent/.worktrees/<branch> and tmp_path/.worktrees/<branch>).
    worktree = tmp_path / ".worktrees" / "cx-review"
    worktree.mkdir(parents=True)
    proc = _fake_lane_runner(worktree, name="not-a-runner")
    try:
        entries = [str(proc.pid)]
        live, examined, _ = dl._review_lane_live(
            "cx-review", tmp_path,
            process_entries=entries,
        )
        assert not live
        assert examined == 1
        # Same pid but a runner basename → live. Override the cmdline reader so
        # the process argv[0] reads as a runner name regardless of the symlink.
        live, _, _ = dl._review_lane_live(
            "cx-review", tmp_path,
            process_entries=entries,
            read_cmdline=lambda pid: b"/x/ccc\x00sleep 60\x00",
        )
        assert live
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_review_liveness_excludes_self_and_ancestors(tmp_path):
    """#729: a pid in the ancestor/skip set is never counted, even if its cwd
    is in the worktree and it is a runner. Without this, the probe counts
    itself and refuses/warns on every dispatch."""
    dl = _import_dispatch_lane()
    worktree = tmp_path / ".worktrees" / "cx-review"
    worktree.mkdir(parents=True)
    runner_pid = 999999
    fake_read_cwd = lambda pid: str(worktree)
    fake_read_cmdline = lambda pid: b"/x/ccc\x00"
    # Excluded as an ancestor → not live.
    live, examined, _ = dl._review_lane_live(
        "cx-review", tmp_path,
        process_entries=[str(runner_pid)],
        read_cwd=fake_read_cwd, read_cmdline=fake_read_cmdline,
        skip_pids={runner_pid},
    )
    assert not live
    assert examined == 0  # the only candidate was skipped, so examined is 0
    # Not excluded → live.
    live, examined, _ = dl._review_lane_live(
        "cx-review", tmp_path,
        process_entries=[str(runner_pid)],
        read_cwd=fake_read_cwd, read_cmdline=fake_read_cmdline,
        skip_pids=set(),
    )
    assert live
    assert examined == 1


def test_review_liveness_probed_nothing_reports_examined_zero(tmp_path):
    """#868: a probe that examined 0 processes must not read as 'found none,
    all clear'. An empty process table yields examined=0 and the CLI warns
    NO VERDICT rather than silently proceeding as if clean."""
    dl = _import_dispatch_lane()
    live, examined, _ = dl._review_lane_live(
        "cx-review", tmp_path, process_entries=[],
    )
    assert not live
    assert examined == 0


def test_review_liveness_resolves_worktree_from_coordinator_root(tmp_path):
    """The scan checks the worktree paths worktree_paths.derives, so a runner
    in a DIFFERENT branch's worktree is not counted for this branch (#136:
    no lane / lane live / lane finished are distinct)."""
    dl = _import_dispatch_lane()
    other_wt = tmp_path / ".worktrees" / "cx-other"
    other_wt.mkdir(parents=True)
    other_pid = 888888
    # Runner in cx-other's worktree, reviewing cx-review → not live.
    live, examined, _ = dl._review_lane_live(
        "cx-review", tmp_path,
        process_entries=[str(other_pid)],
        read_cwd=lambda pid: str(other_wt),
        read_cmdline=lambda pid: b"/x/ccc\x00",
    )
    assert not live
    assert examined == 1
