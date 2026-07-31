#!/usr/bin/env python3
"""Contract tests for the checked Dreamwork lane dispatch route (#768)."""

import subprocess
import sys
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "dev" / "dispatch_lane.py"
CONTRACT = (ROOT / "briefs" / "boilerplate.md").read_text(encoding="utf-8")


def _sandbox_cli(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "dev").mkdir(parents=True)
    (root / "briefs").mkdir()
    cli = root / "dev" / "dispatch_lane.py"
    shutil.copy2(CLI, cli)
    (root / "briefs" / "boilerplate.md").write_text(CONTRACT, encoding="utf-8")
    return cli, root


def _run(cli: Path, prompt: Path | None = None, *runner: str) -> subprocess.CompletedProcess[str]:
    mode = ["--verify-pending"] if prompt is None else ["--prompt", str(prompt), "--"]
    return subprocess.run(
        [sys.executable, str(cli), *mode, *runner],
        capture_output=True,
        text=True,
    )


def _healthy_prompt(tmp_path: Path, task: int = 900, lane: str = "cx-test") -> Path:
    prompt = tmp_path / f"prompt-{lane}.txt"
    prompt.write_text(
        f"# Brief — #{task}: task-specific lane head\n\n"
        f"Branch: {lane}\n\n" + CONTRACT,
        encoding="utf-8",
    )
    return prompt


def test_healthy_dispatch_is_silent_and_passes_prompt_as_one_argument(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path)
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


def test_same_task_dispatches_to_distinct_lanes_do_not_collide(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    first = _healthy_prompt(tmp_path, task=901, lane="cx-one")
    second = _healthy_prompt(tmp_path, task=901, lane="cx-two")

    assert _run(cli, first, "true").returncode == 0
    assert _run(cli, second, "true").returncode == 0

    briefs = root / ".dreamwork" / "docs" / "briefs"
    assert (briefs / "901-cx-one.md").read_text(encoding="utf-8") == first.read_text(encoding="utf-8")
    assert (briefs / "901-cx-two.md").read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_persistence_failure_refuses_and_names_what_was_not_persisted(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path)
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
    prompt.write_text("# Brief — #902: no branch identity\n\n" + CONTRACT, encoding="utf-8")

    result = _run(cli, prompt, "true")

    assert result.returncode == 2
    assert "no unique 'Branch: <lane>' line" in result.stderr
    assert not (root / ".dreamwork" / "docs" / "briefs").exists()


def test_verify_pending_rejects_changed_artifact(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path)
    assert _run(cli, prompt, "true").returncode == 0
    artifact = root / ".dreamwork" / "docs" / "briefs" / "900-cx-test.md"
    artifact.write_text("wrong artifact\n", encoding="utf-8")

    result = _run(cli)

    assert result.returncode == 2
    assert "changed after dispatch-time persistence" in result.stderr


def test_verify_pending_rejects_absent_artifact(tmp_path):
    cli, root = _sandbox_cli(tmp_path)
    prompt = _healthy_prompt(tmp_path)
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
    prompt = _healthy_prompt(tmp_path)

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
