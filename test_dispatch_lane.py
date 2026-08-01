#!/usr/bin/env python3
"""Contract tests for the checked Dreamwork lane dispatch route (#768)."""

import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


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
    shutil.copy2(ROOT / "ledger_store.py", root / "ledger_store.py")
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
    shutil.copy2(ROOT / "ledger_store.py", lane / "ledger_store.py")
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
    prompt = tmp_path / f"prompt-{lane}.txt"
    prompt.write_text(
        f"# Brief — #{task}: task-specific lane head\n\n"
        f"Worktree: {coordinator_root}/.worktrees/{lane}\n"
        f"Branch: {lane}\n"
        f"Base sha: {base_sha}\n"
        "Coordinator inbox — ABSOLUTE path, append your completion summary "
        f"here when you finish: {coordinator_root}/.dreamwork/inbox.md\n\n"
        + CONTRACT,
        encoding="utf-8",
    )
    return prompt


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


def test_explicit_pipe_override_launches_runner(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path, root)

    result = _run(cli, prompt, sys.executable, "-c", "print('launched')")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "launched\n"


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
    returncode = process.wait(timeout=5)
    os.close(master)

    assert returncode == 0
    assert launched.is_file()


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
    assert launched.is_file()


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
    assert launched.is_file()


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
    prompt = _healthy_prompt(tmp_path, root)
    assert _run(cli, prompt, "true").returncode == 0
    artifact = root / ".dreamwork" / "docs" / "briefs" / "900-cx-test.md"
    artifact.unlink()

    result = _run(cli)

    assert result.returncode == 2
    assert "has no governed brief artifact" in result.stderr


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
    recipe_body = justfile[recipe_start:]
    recipe_lines = [
        line for line in recipe_body.splitlines()
        if "dispatch_lane.py" in line and not line.lstrip().startswith("#")
    ]
    assert len(recipe_lines) == 1, "expected exactly one dispatch_lane.py line"
    assert recipe_lines[0].lstrip().startswith("@"), (
        "dispatch-lane recipe must be @-prefixed: without it just echoes the "
        "expanded command on every dispatch, so the route is not silent (#769)"
    )
