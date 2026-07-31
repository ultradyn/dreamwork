#!/usr/bin/env python3
"""Contract tests for the checked Dreamwork lane dispatch route (#768)."""

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "dev" / "dispatch_lane.py"
CONTRACT = (ROOT / "briefs" / "boilerplate.md").read_text(encoding="utf-8")


def _run(prompt: Path, *runner: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "--prompt", str(prompt), "--", *runner],
        capture_output=True,
        text=True,
    )


def _healthy_prompt(tmp_path: Path) -> Path:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("# Task-specific lane head\n\n" + CONTRACT, encoding="utf-8")
    return prompt


def test_healthy_dispatch_is_silent_and_passes_prompt_as_one_argument(tmp_path):
    prompt = _healthy_prompt(tmp_path)
    capture = tmp_path / "capture.py"
    capture.write_text(
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(sys.argv[2], encoding='utf-8')\n",
        encoding="utf-8",
    )
    delivered = tmp_path / "delivered.txt"

    result = _run(prompt, sys.executable, str(capture), str(delivered))

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert delivered.read_text(encoding="utf-8") == prompt.read_text(encoding="utf-8")


def test_literal_command_substitution_refuses_and_names_missing_contract(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("$(cat /tmp/lane/p766.txt)\n", encoding="utf-8")

    result = _run(prompt, "true")

    assert result.returncode == 2
    assert "standing contract from briefs/boilerplate.md is missing or altered" in result.stderr


def test_long_prompt_without_rules_does_not_pass(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("task detail " * 10_000, encoding="utf-8")

    result = _run(prompt, "true")

    assert result.returncode == 2
    assert "standing contract" in result.stderr


def test_one_magic_phrase_does_not_pass(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Never merge, never push.\n", encoding="utf-8")

    result = _run(prompt, "true")

    assert result.returncode == 2
    assert "standing contract" in result.stderr


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_contract_as_quoted_example_does_not_pass(tmp_path, fence):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "This is quoted reference material, not an instruction:\n"
        f"{fence}markdown\n{CONTRACT}{fence}\n",
        encoding="utf-8",
    )

    result = _run(prompt, "true")

    assert result.returncode == 2
    assert "inside a fenced quotation" in result.stderr


def test_unreadable_and_empty_are_distinct_from_invalid(tmp_path):
    missing = tmp_path / "missing.txt"
    unreadable = _run(missing, "true")
    assert unreadable.returncode == 2
    assert "could not read prompt" in unreadable.stderr
    assert "standing contract" not in unreadable.stderr

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    empty_result = _run(empty, "true")
    assert empty_result.returncode == 2
    assert "prompt is empty" in empty_result.stderr


def test_no_runner_is_a_distinct_usage_fault(tmp_path):
    prompt = _healthy_prompt(tmp_path)

    result = _run(prompt)

    assert result.returncode == 2
    assert "runner command is missing" in result.stderr
