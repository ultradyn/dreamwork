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
        "os.execlp('sleep', 'ccc', '4')\n",
        encoding="utf-8",
    )
    fake_ccc.chmod(0o755)
    env = {
        **os.environ,
        "DREAMWORK_ALLOW_PIPED_STDOUT": "1",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "REVIEW_TEST_OUTPUT": str(observed),
        "REVIEW_RUNNER_SETTLE": "0.2",
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
        "runner exit observed on completion via .runner.exit.json"
    )
    # #1214: a launch record must name where the runner's output is captured,
    # so a completed review's verdict is recoverable from the record alone.
    assert "runner_log" in attempt, (
        "launch record has no runner_log field; the captured output has no "
        "discoverable path (#1214)"
    )
    runner_log = Path(attempt["runner_log"])
    assert runner_log.name.endswith(".runner.log"), attempt["runner_log"]
    assert runner_log.parent == Path(attempt["prompt"]).parent


def test_launch_review_captures_runner_log_and_records_it(tmp_path):
    """#1214: a completed review's outcome is recoverable from the record alone.

    A reviewer that prints its verdict to stdout and exits 0 must leave that
    verdict in a file whose path the launch record names, and an exit witness
    beside it — so the coordinator finds the verdict without having redirected
    the launcher, and --review-status reads the dispatch as terminal (not
    runner-absent). This is the property the two incidents violated: a finished
    review was indistinguishable from a dead one because nothing captured or
    recorded where the output went.
    """
    branch = "cx-revcap"
    cli, root = _sandbox_review_cli(tmp_path, branch)
    prompt = _review_prompt(tmp_path, root, branch)
    verdict_text = "VERDICT-MARKER-1214: ANOTHER ROUND, one P1 finding"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ccc = fake_bin / "ccc"
    # The reviewer prints its verdict to stdout and exits 0 — a successful
    # review whose output would be lost without the capture mechanism. It then
    # execs ``sleep`` with argv[0]=ccc so the spawn-time liveness probe
    # recognises it (a real ccc binary's argv[0] is ccc; a shebang script's is
    # /usr/bin/env, which is not a known runner), mirroring the existing launch
    # test's fake runner.
    fake_ccc.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({verdict_text!r} + chr(10))\n"
        "sys.stdout.flush()\n"
        "import os\n"
        "os.execlp('sleep', 'ccc', '4')\n",
        encoding="utf-8",
    )
    fake_ccc.chmod(0o755)
    env = {
        **os.environ,
        "DREAMWORK_ALLOW_PIPED_STDOUT": "1",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "REVIEW_RUNNER_SETTLE": "0.2",
    }
    result = subprocess.run(
        [
            sys.executable, str(cli), "--launch-review", str(prompt),
            "--review-branch", branch, "--review-round", "1", "--",
            "ccc", "--permission-mode", "plan", "@cx-reviewer",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    attempts = sorted((root / ".dreamwork" / "review-dispatches").glob("*.launch.json"))
    assert len(attempts) == 1
    attempt = json.loads(attempts[0].read_text(encoding="utf-8"))
    runner_log = Path(attempt["runner_log"])
    exit_path = runner_log.with_name(
        runner_log.name[:-len(".runner.log")] + ".runner.exit.json")
    # The supervisor runs detached; poll for the capture + exit record to land.
    for _ in range(500):
        if runner_log.is_file() and exit_path.is_file():
            break
        time.sleep(0.02)
    else:
        raise AssertionError(
            f"runner capture did not land: log={runner_log.is_file()} "
            f"exit={exit_path.is_file()}")
    # (1) The verdict is recoverable from the recorded path.
    captured = runner_log.read_text(encoding="utf-8")
    assert verdict_text in captured, (
        f"verdict text missing from captured runner log; got={captured!r}")
    # (2) The exit was observed and recorded beside the log.
    exit_record = json.loads(exit_path.read_text(encoding="utf-8"))
    assert exit_record["runner_exit"] == 0, exit_record
    assert exit_record["runner_log"] == str(runner_log), exit_record
    # (3) --review-status reads the dispatch as terminal naming the log, NOT
    # runner-absent — a finished review no longer reads as a corpse.
    status = subprocess.run(
        [sys.executable, str(cli), "--review-status"],
        capture_output=True, text=True,
        env={**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"},
    )
    assert status.returncode == 0, status.stderr
    assert "classified 1 dispatch" in status.stdout, status.stdout
    line = next(l for l in status.stdout.splitlines() if "cx-revcap" in l)
    assert "terminal" in line, (
        f"a completed review (exit observed) did not classify terminal; "
        f"line={line!r}")
    assert "runner-absent" not in line, line
    assert str(runner_log) in line, (
        f"status line did not name the recoverable verdict path; line={line!r}")


def test_launch_review_accepts_fast_completing_review_not_spawn_fail(tmp_path):
    """#1214 round 3 / P1(b): a genuine one-line review that finishes INSIDE the
    settle window leaves a non-blank matching log and {runner_exit: 0} but no
    LIVE reviewer. The liveness probe sees no runner, yet this is a COMPLETED
    review, not a spawn failure — launch_review must read the exit witness and
    accept it (return 0), not refuse with spawn-failed (return 3). The mirror
    of round 1's defect: round 1 fixed an unobserved outcome reading as
    delivery; what remained was a completed outcome reading as a failure to
    start."""
    branch = "cx-fast"
    cli, root = _sandbox_review_cli(tmp_path, branch)
    prompt = _review_prompt(tmp_path, root, branch)
    verdict_text = "MERGE"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ccc = fake_bin / "ccc"
    # The reviewer prints its one-line verdict and exits 0 immediately — fast
    # enough to finish inside the settle window, so the spawn probe finds no
    # live runner, but the supervisor has already written a complete witness.
    fake_ccc.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({verdict_text!r} + chr(10))\n"
        "sys.stdout.flush()\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_ccc.chmod(0o755)
    env = {
        **os.environ,
        "DREAMWORK_ALLOW_PIPED_STDOUT": "1",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "REVIEW_RUNNER_SETTLE": "0.1",
    }
    result = subprocess.run(
        [
            sys.executable, str(cli), "--launch-review", str(prompt),
            "--review-branch", branch, "--review-round", "1", "--",
            "ccc", "--permission-mode", "plan", "@cx-reviewer",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"a completed fast review was refused as a spawn failure; "
        f"stdout={result.stdout!r}; stderr={result.stderr!r}")
    attempts = sorted((root / ".dreamwork" / "review-dispatches").glob("*.launch.json"))
    assert len(attempts) == 1
    attempt = json.loads(attempts[0].read_text(encoding="utf-8"))
    assert "spawn failed" not in attempt["state"], attempt["state"]
    assert "completed during settle" in attempt["state"], attempt["state"]
    runner_log = Path(attempt["runner_log"])
    for _ in range(100):
        if runner_log.is_file():
            break
        time.sleep(0.01)
    assert verdict_text in runner_log.read_text(encoding="utf-8")
    exit_path = runner_log.with_name(
        runner_log.name[:-len(".runner.log")] + ".runner.exit.json")
    exit_record = json.loads(exit_path.read_text(encoding="utf-8"))
    assert exit_record["runner_exit"] == 0, exit_record


def test_launch_review_fast_review_with_blank_log_still_refuses(tmp_path):
    """#1214 round 3 / P1(b) trap-guard: accepting a completed fast review
    requires a VALID witness, not merely an absent live runner. A reviewer that
    exits 0 inside the settle window but produces a BLANK log leaves an exit
    integer but no recoverable verdict; _read_runner_exit rejects it (blank
    log) and launch_review still refuses (return 3). This proves the fast-exit
    acceptance did NOT reopen round 1 — a review that died producing nothing
    does not read as delivered."""
    branch = "cx-blank"
    cli, root = _sandbox_review_cli(tmp_path, branch)
    prompt = _review_prompt(tmp_path, root, branch)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ccc = fake_bin / "ccc"
    # Exits 0 immediately, writing nothing — a blank capture beside exit 0.
    fake_ccc.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_ccc.chmod(0o755)
    env = {
        **os.environ,
        "DREAMWORK_ALLOW_PIPED_STDOUT": "1",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "REVIEW_RUNNER_SETTLE": "0.1",
    }
    result = subprocess.run(
        [
            sys.executable, str(cli), "--launch-review", str(prompt),
            "--review-branch", branch, "--review-round", "1", "--",
            "ccc", "--permission-mode", "plan", "@cx-reviewer",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 3, (
        f"a blank-log fast exit was accepted (round 1 reopened); "
        f"stdout={result.stdout!r}; stderr={result.stderr!r}")
    attempts = sorted((root / ".dreamwork" / "review-dispatches").glob("*.launch.json"))
    assert len(attempts) == 1
    attempt = json.loads(attempts[0].read_text(encoding="utf-8"))
    assert "spawn failed" in attempt["state"], attempt["state"]


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


# --- #1207: consume runner_exit=null so a dead review is not "still thinking" -

def _classify(record_overrides: dict | None = None, **liveness) -> tuple[str, str]:
    """Call classify_review_dispatch with injectable liveness readers.

    Mirrors the injectable-reader pattern the _review_lane_live tests use, so
    the dead/slow discrimination is proven in-process without a real process.
    """
    dl = _import_dispatch_lane()
    record = {"runner_exit": None, "review_lane": "cx-review-review-r1",
              "branch": "cx-review", "round": 1, "attempt_id": "cx-review-review-r1-deadbeef",
              "state": "spawned: reviewer present in review worktree (cwd-containment); "
                       "runner exit not observed"}
    if record_overrides:
        record.update(record_overrides)
    return dl.classify_review_dispatch(record, Path("/tmp"), **liveness)


def test_classify_dead_review_is_runner_absent_the_alarm():
    """#1207 Direction 2 (dead half): a review whose runner is GONE while
    runner_exit is still null is the alarm — runner-absent.  Before this fix
    nothing consumed that null and the record read as benign."""
    # A process exists but holds a DIFFERENT cwd (the runner left the worktree).
    category, detail = _classify(
        process_entries=["999999"],
        read_cwd=lambda pid: "/somewhere/else",
        read_cmdline=lambda pid: b"/x/ccc\x00",
    )
    assert category == "runner-absent", detail
    assert "runner_exit never observed" in detail
    assert "no longer progressing" in detail


def test_classify_slow_review_is_in_progress_not_an_alarm():
    """#1207 Direction 2 (slow half): a review whose runner is STILL PRESENT
    is in-progress — it must NOT trip the alarm.  A 20-minute reviewer thinking
    under load is live, not dead.  This is the false-positive half: without it
    the classifier is a dead-review machine that also files every slow review."""
    category, detail = _classify(
        process_entries=["999999"],
        read_cwd=lambda pid: "/tmp/.worktrees/cx-review-review-r1",
        read_cmdline=lambda pid: b"/x/ccc\x00",
    )
    assert category == "in-progress", detail
    assert "still in progress" in detail


def test_classify_review_is_unknown_when_probe_examined_nothing():
    """#868: a probe that examined 0 processes reports unknown, never an
    all-clear.  This is the honest 'I could not tell' — not runner-absent."""
    category, detail = _classify(process_entries=[])
    assert category == "unknown"
    assert "examined 0" in detail
    assert "not an all-clear" in detail


def test_launch_record_runner_exit_alone_does_not_classify_as_terminal():
    """#1214 round 3 / P1(c): the launch record's own ``runner_exit`` is always
    null for the supervisor format (file-formats.md), so a non-null value is a
    stale or corrupt record — the cheapest lying witness of the three. With no
    ``.runner.log`` and no ``.runner.exit.json`` at all, a launch record
    ``{runner_exit: 0}`` used to classify ``terminal`` via a fallback that
    bypassed every condition; it must now fall through to the liveness probe and
    report ``runner-absent`` when the runner is gone. (The #1207 era model — a
    future revision sets runner_exit in the launch record — is superseded: the
    supervisor writes the sibling ``.runner.exit.json`` instead, never this
    field. The real terminal path is covered by
    ``test_nonempty_runner_log_with_exit_record_classifies_as_terminal``.)"""
    category, detail = _classify(
        record_overrides={"runner_exit": 0, "state": "done"},
        process_entries=["999999"],
        read_cwd=lambda pid: "/somewhere/else",
        read_cmdline=lambda pid: b"/x/ccc\x00",
    )
    assert category == "runner-absent", (
        f"a launch-record-only runner_exit classified as {category!r}; "
        f"detail={detail!r}")
    assert "verdict recoverable" not in detail, detail


def test_classify_review_is_unknown_without_review_lane():
    """A malformed record with no review_lane cannot be probed; unknown, not a
    silent pass."""
    category, detail = _classify(record_overrides={"review_lane": None})
    assert category == "unknown"
    assert "no review_lane" in detail


# --- #1214 round 2: a present-but-empty capture must NOT classify as delivered --

def _classify_with_exit_record(
        tmp_path: Path, *, log_bytes: bytes | None = b"",
        exit_runner_log: str | None = None,
        exit_runner_exit: object = 0, **liveness) -> tuple[str, str]:
    """Build a launch record + sibling ``.runner.log``/``.runner.exit.json`` in
    ``tmp_path`` and classify it.

    ``log_bytes`` is written to ``.runner.log`` (``None`` deletes it so the
    missing-file case is testable); ``exit_runner_log`` defaults to the launch
    record's ``runner_log`` path (pass a different string to test a path
    mismatch).  ``exit_runner_exit`` defaults to ``0``; pass a non-int
    (e.g. ``True``) to test a lying exit record.  The liveness kwargs are
    forwarded so the fall-through path can be driven deterministically.
    """
    dl = _import_dispatch_lane()
    runner_log = tmp_path / "cx-review-review-r1-deadbeef.runner.log"
    exit_path = runner_log.with_name(
        runner_log.name[:-len(".runner.log")] + ".runner.exit.json")
    if log_bytes is not None:
        runner_log.write_bytes(log_bytes)
    log_in_exit = exit_runner_log if exit_runner_log is not None else str(runner_log)
    exit_path.write_text(json.dumps(
        {"runner_exit": exit_runner_exit, "runner_log": log_in_exit}
    ) + "\n", encoding="utf-8")
    record = {
        "runner_exit": None,
        "runner_log": str(runner_log),
        "review_lane": "cx-review-review-r1",
        "branch": "cx-review", "round": 1,
        "attempt_id": "cx-review-review-r1-deadbeef",
        "state": "spawned: reviewer present in review worktree (cwd-containment); "
                 "runner exit observed on completion via .runner.exit.json",
    }
    return dl.classify_review_dispatch(record, Path("/tmp"), **liveness)


# A runner whose cwd is NOT the review worktree — the fall-through liveness
# probe sees it gone, so a capture that falls through reports runner-absent.
_FALLTHROUGH_LIVENESS = dict(
    process_entries=["999999"],
    read_cwd=lambda pid: "/somewhere/else",
    read_cmdline=lambda pid: b"/x/ccc\x00",
)


def test_empty_runner_log_with_exit_record_does_not_classify_as_terminal(tmp_path):
    """#1214 round 2 P1: an EMPTY .runner.log beside a well-formed
    .runner.exit.json must NOT classify as terminal. A reviewer that died before
    producing output leaves an exit integer but no recoverable verdict; the
    honest classification is runner-absent (fall through to liveness)."""
    category, detail = _classify_with_exit_record(
        tmp_path, log_bytes=b"", **_FALLTHROUGH_LIVENESS)
    assert category == "runner-absent", (
        f"an empty capture classified as {category!r}; detail={detail!r}")
    assert "verdict recoverable" not in detail, detail


def test_whitespace_only_runner_log_does_not_classify_as_terminal(tmp_path):
    """A log whose only content is whitespace is as empty as zero bytes for the
    purpose of recovering a verdict — the single-space trap (#1214 round 2)."""
    category, detail = _classify_with_exit_record(
        tmp_path, log_bytes=b"   \n\t\n", **_FALLTHROUGH_LIVENESS)
    assert category == "runner-absent", detail


def test_missing_runner_log_with_exit_record_does_not_classify_as_terminal(tmp_path):
    """A .runner.exit.json whose sibling .runner.log does not exist is an
    unobserved outcome — the log may have been cleaned up, or the exit record
    was written ahead of the capture."""
    category, detail = _classify_with_exit_record(
        tmp_path, log_bytes=None, **_FALLTHROUGH_LIVENESS)
    assert category == "runner-absent", detail


def test_path_mismatched_exit_record_does_not_classify_as_terminal(tmp_path):
    """An exit record whose runner_log names a DIFFERENT path than the launch
    recorded is a lying or stale witness — it could point at a real log from a
    different run.  Treated as unobserved (#1214 round 2)."""
    category, detail = _classify_with_exit_record(
        tmp_path, log_bytes=b"real verdict\n",
        exit_runner_log="/tmp/different-runner.log",
        **_FALLTHROUGH_LIVENESS)
    assert category == "runner-absent", detail


def test_nonempty_runner_log_with_exit_record_classifies_as_terminal(tmp_path):
    """Discriminating positive: a non-empty .runner.log with a well-formed,
    path-matching .runner.exit.json DOES classify as terminal — proving the
    empty/mismatched tests above are exercising the content check, not a blanket
    refusal."""
    category, detail = _classify_with_exit_record(
        tmp_path, log_bytes=b"VERDICT: ANOTHER ROUND, one P1\n")
    assert category == "terminal", detail
    assert "verdict recoverable" in detail, detail


def test_bool_runner_exit_does_not_classify_as_terminal(tmp_path):
    """#1214 round 3 / P1(a): a JSON ``true`` is a Python ``bool``, and ``bool``
    IS an ``int`` subclass, so ``isinstance(..., int)`` accepted it. A
    path-matching record with a non-blank log but ``runner_exit: true`` must
    fall through to runner-absent — a bool is not an exit code, and a lying or
    corrupt record is not a delivered verdict."""
    category, detail = _classify_with_exit_record(
        tmp_path, log_bytes=b"VERDICT\n", exit_runner_exit=True,
        **_FALLTHROUGH_LIVENESS)
    assert category == "runner-absent", (
        f"a JSON true runner_exit classified as {category!r}; detail={detail!r}")
    assert "verdict recoverable" not in detail, detail


def test_unicode_whitespace_only_runner_log_does_not_classify_as_terminal(tmp_path):
    """#1214 round 3 / P2(a): ``bytes.strip()`` only strips ASCII whitespace, so
    a capture holding only U+2003 (em space, three non-ASCII bytes) read as
    non-blank. "Non-blank" is a TEXT judgment: a log of only Unicode whitespace
    is blank, falls through to runner-absent."""
    em_space = "\u2003".encode("utf-8")  # three bytes, no ASCII whitespace
    assert em_space.strip(), "precondition: bytes.strip sees content here"
    category, detail = _classify_with_exit_record(
        tmp_path, log_bytes=em_space, **_FALLTHROUGH_LIVENESS)
    assert category == "runner-absent", (
        f"a U+2003-only capture classified as {category!r}; detail={detail!r}")
    assert "verdict recoverable" not in detail, detail


def test_review_status_cli_reports_runner_absent_dispatch(tmp_path):
    """The --review-status verb reads every *.launch.json and classifies it, so
    a dispatch whose runner is gone surfaces as runner-absent instead of the
    benign 'runner exit not observed' the launch record is frozen at."""
    cli, root = _sandbox_review_cli(tmp_path)
    dispatches = root / ".dreamwork" / "review-dispatches"
    dispatches.mkdir(parents=True, exist_ok=True)
    (dispatches / "cx-review-r1-deadbeef.prompt.md").write_text("prompt\n", encoding="utf-8")
    (dispatches / "cx-review-r1-deadbeef.launch.json").write_text(json.dumps({
        "attempt_id": "cx-review-review-r1-deadbeef",
        "branch": "cx-review", "round": 1,
        "review_lane": "cx-review-review-r1",
        "pinned_sha": "abc123", "prompt_sha256": "f" * 64, "prompt_bytes": 7,
        "prompt": str(dispatches / "cx-review-r1-deadbeef.prompt.md"),
        "worktree": str(root.parent / ".worktrees" / "cx-review-review-r1"),
        "permission_mode": "plan",
        "state": "spawned: reviewer present in review worktree (cwd-containment); "
                 "runner exit not observed",
        "runner_exit": None, "runs": 1,
    }) + "\n", encoding="utf-8")
    # No live runner holds that worktree, so the real /proc probe finds it gone.
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--review-status"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "classified 1 dispatch" in result.stdout
    line = next(l for l in result.stdout.splitlines() if "deadbeef" in l)
    assert "runner-absent" in line, (
        f"a dead review (runner gone, runner_exit null) did not surface as "
        f"runner-absent; line={line!r}"
    )


def test_review_status_cli_reports_no_launches_cleanly(tmp_path):
    """With no launched reviews the verb reports none found, not an error or a
    false all-clear over zero records."""
    cli, root = _sandbox_review_cli(tmp_path)
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--review-status"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "no launched review dispatches found" in result.stdout


# --- #1207 round 2: malformed launch records must not abort or corrupt the report -

def _write_launch_json(dispatches: Path, slug: str, content: str) -> None:
    """Write arbitrary text as a .launch.json (for malformed-record tests)."""
    (dispatches / f"{slug}.launch.json").write_text(content, encoding="utf-8")


def _write_valid_launch(dispatches: Path, slug: str, *, review_lane: str,
                        runner_exit=None) -> None:
    """Write a minimal valid .launch.json that classify_review_dispatch accepts."""
    (dispatches / f"{slug}.prompt.md").write_text("prompt\n", encoding="utf-8")
    _write_launch_json(dispatches, slug, json.dumps({
        "attempt_id": f"{slug}-attempt", "branch": slug, "round": 1,
        "review_lane": review_lane,
        "pinned_sha": "abc123", "prompt_sha256": "f" * 64, "prompt_bytes": 7,
        "prompt": str(dispatches / f"{slug}.prompt.md"),
        "worktree": str(dispatches.parent.parent / ".worktrees" / review_lane),
        "permission_mode": "plan",
        "state": "spawned: reviewer present in review worktree (cwd-containment); "
                 "runner exit not observed",
        "runner_exit": runner_exit, "runs": 1,
    }) + "\n")


def test_review_status_invalid_json_first_is_unknown(tmp_path):
    """A corrupt .launch.json as the FIRST record must not crash the report
    (#1207 P1).  Without the per-iteration record reset, the first decode
    failure leaves ``record`` unbound and the report aborts with
    UnboundLocalError — hiding every other alarm."""
    cli, root = _sandbox_review_cli(tmp_path)
    dispatches = root / ".dreamwork" / "review-dispatches"
    dispatches.mkdir(parents=True, exist_ok=True)
    _write_launch_json(dispatches, "aaa-corrupt", "{not valid json\n")
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--review-status"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "classified 1 dispatch" in result.stdout
    line = next(l for l in result.stdout.splitlines() if "aaa-corrupt" in l)
    assert "unknown" in line


def test_review_status_invalid_json_after_valid_does_not_leak_prior_identity(tmp_path):
    """A corrupt record AFTER a valid one must not display the previous record's
    identity (#1207 P1 staleness).  Without the per-iteration reset, ``record``
    is stale from the prior iteration and the corrupt row shows the PREVIOUS
    dispatch's attempt_id/branch/round while claiming to describe this one.
    This is the test that distinguishes the unset bug from the stale bug."""
    cli, root = _sandbox_review_cli(tmp_path)
    dispatches = root / ".dreamwork" / "review-dispatches"
    dispatches.mkdir(parents=True, exist_ok=True)
    _write_valid_launch(dispatches, "aaa-firstvalid", review_lane="aaa-review-r1")
    _write_launch_json(dispatches, "bbb-corrupt", "{not valid json\n")
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--review-status"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "classified 2 dispatch" in result.stdout
    corrupt_line = next(l for l in result.stdout.splitlines() if "bbb-corrupt" in l)
    assert "unknown" in corrupt_line
    # The corrupt record must NOT leak the prior record's identity.
    assert "aaa-firstvalid" not in corrupt_line, (
        f"corrupt record leaked prior identity; line={corrupt_line!r}"
    )


def test_review_status_non_object_json_array_is_unknown(tmp_path):
    """Valid JSON that is not an object (e.g. ``[]``) must classify as unknown,
    not crash (#1207 P1).  Without the isinstance guard, ``[]`` reaches
    classify_review_dispatch where ``record.get()`` raises AttributeError and
    aborts the entire report."""
    cli, root = _sandbox_review_cli(tmp_path)
    dispatches = root / ".dreamwork" / "review-dispatches"
    dispatches.mkdir(parents=True, exist_ok=True)
    _write_launch_json(dispatches, "aaa-array", "[]\n")
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--review-status"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "classified 1 dispatch" in result.stdout
    line = next(l for l in result.stdout.splitlines() if "aaa-array" in l)
    assert "unknown" in line


def test_review_status_malformed_in_middle_does_not_hide_later_alarm(tmp_path):
    """A malformed record in the middle must not prevent later records from
    being classified (#1207 P1).  Without the fix, a ``[]`` record aborts the
    report via AttributeError, hiding every subsequent alarm — including a
    runner-absent dispatch, which is the whole point of --review-status."""
    cli, root = _sandbox_review_cli(tmp_path)
    dispatches = root / ".dreamwork" / "review-dispatches"
    dispatches.mkdir(parents=True, exist_ok=True)
    _write_valid_launch(dispatches, "aaa-first", review_lane="aaa-review-r1")
    _write_launch_json(dispatches, "bbb-malformed", "[]\n")
    _write_valid_launch(dispatches, "ccc-alarm", review_lane="ccc-review-r1")
    env = {**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"}
    result = subprocess.run(
        [sys.executable, str(cli), "--review-status"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "classified 3 dispatch" in result.stdout
    alarm_line = next(l for l in result.stdout.splitlines() if "ccc-alarm" in l)
    assert "runner-absent" in alarm_line, (
        f"a malformed record in the middle hid the later alarm; line={alarm_line!r}"
    )

