from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from dev import land_lane, suite_baseline


REPO = Path(__file__).resolve().parent


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def _fixture_repo(tmp_path: Path, just_body: str) -> tuple[Path, Path, dict[str, str]]:
    repo = tmp_path / "repo"
    bindir = tmp_path / "bin"
    repo.mkdir()
    bindir.mkdir()
    _write(repo / "justfile", 'guards:\n    DEFAULT_GUARDS="alpha beta"\n    HUB_GUARDS=${DREAMWORK_HUB_GUARDS-"hub contract"}\n')
    _write(bindir / "just", "#!/bin/sh\nset -eu\n" + just_body)
    (bindir / "just").chmod(0o755)
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
    subprocess.run(["git", "add", "justfile"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    record = tmp_path / "suite-baseline.json"
    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    return repo, record, env


def _run(repo: Path, record: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "dev/suite_baseline.py"), "run", "--repo", str(repo), "--record", str(record)],
        text=True, capture_output=True, env=env, check=False,
    )


def test_gate_coverage_names_the_full_suite_complement():
    # This assertion is a PROSE PIN on land_lane._gate_coverage_line, and #949
    # necessarily reworded it: the gate now runs tests derived from the diff, so
    # the sentence naming what coverage the reader did NOT get had to say so.
    #
    # WHY THIS TEST IS WORTH THE BUMP COST, and it earned it the day it was
    # rewritten: it is the ONLY thing standing between a reworded coverage claim
    # and a reader who trusts it. #948 is the whole family — "4 of 4 declared
    # gates passed" reads as completeness — and a line that describes coverage
    # is exactly where a true statement becomes a stronger claim than it
    # supports. Pinning the prose is the point, not an accident of the fixture.
    #
    # HOW IT WAS REACHED, recorded because it is #949's own blind spot. This
    # test lives in test_suite_baseline.py, NOT in test_land_lane.py. #949's
    # name convention (`foo.py` -> `test_foo.py`) derives test_land_lane.py and
    # CANNOT reach this file; #953's import-graph rule now does (this test does
    # `from dev import land_lane`), which is free evidence that #953 works. The
    # three rules in DERIVATION_RULES — name, import, map — are what this pin's
    # hardcoded "3" counts. Adding a rule changes len(DERIVATION_RULES) and
    # breaks this pin; that is the #852/#905 property, and #959 bound it.
    passed = list(land_lane.GATES)
    assert land_lane._gate_coverage_line(passed) == (
        "gate-coverage: 5 of 5 declared gates passed: red-proof-history "
        "named-tests guard-selection repo-wide-guards lint-comparison; full "
        "repo suite NOT RUN (test coverage was limited to lane-named tests, "
        "the tests derived from the changed files by 3 derivation rule(s), "
        "and the repo-wide guards)"
    )


def test_no_receipt_is_not_run_and_does_not_substitute_last_green(tmp_path, capsys):
    assert suite_baseline.main(["status", "--record", str(tmp_path / "missing.json")]) == 0
    output = capsys.readouterr().out
    assert "last attempt: NOT RUN — no attempt receipt" in output
    assert "last full pass: UNKNOWN" in output


def test_a_command_that_does_not_run_the_suite_cannot_record_green(tmp_path):
    repo, record, env = _fixture_repo(tmp_path, "exit 42\n")
    prior_sha = "1" * 40
    suite_baseline._atomic_write(record, {
        "schema_version": suite_baseline.SCHEMA_VERSION,
        "last_full_pass": {"sha": prior_sha, "finished_at": "2026-08-01T01:02:03+10:00"},
    })
    result = _run(repo, record, env)
    receipt = json.loads(record.read_text())
    status = suite_baseline.format_status(receipt)
    assert result.returncode == 42
    assert receipt["state"] == "INCOMPLETE"
    assert all(part["state"] == "NOT RUN" for part in receipt["components"].values())
    assert "pytest 0/UNKNOWN outcomes" in status
    assert f"last full pass: {prior_sha}" in status
    assert "last attempt: PASS" not in status


def test_sigterm_finalises_the_pre_run_receipt_as_interrupted(tmp_path):
    repo, record, env = _fixture_repo(tmp_path, "sleep 30\n")
    process = subprocess.Popen(
        [sys.executable, str(REPO / "dev/suite_baseline.py"), "run", "--repo", str(repo), "--record", str(record)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    for _ in range(100):
        if record.exists() and json.loads(record.read_text()).get("state") == "RUNNING":
            break
        time.sleep(0.02)
    else:
        process.kill()
        pytest.fail("RUNNING receipt was not written before the suite subprocess")
    process.send_signal(signal.SIGTERM)
    process.communicate(timeout=5)
    receipt = json.loads(record.read_text())
    assert receipt["state"] == "INTERRUPTED"
    assert "last attempt: INTERRUPTED" in suite_baseline.format_status(receipt)
    assert receipt["last_full_pass"] is None


def test_collection_error_is_incomplete_with_a_loud_denominator(tmp_path):
    repo, record, env = _fixture_repo(
        tmp_path, "exec python3 -m pytest -q --continue-on-collection-errors\n"
    )
    _write(repo / "test_ok.py", "import pytest\n\n@pytest.mark.parametrize('n', range(40))\ndef test_ok(n):\n    assert n >= 0\n")
    _write(repo / "broken/conftest.py", "def broken(:\n")
    _write(repo / "broken/test_never.py", "def test_never():\n    assert True\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "collection fixture"], cwd=repo, check=True)
    result = _run(repo, record, env)
    receipt = json.loads(record.read_text())
    status = suite_baseline.format_status(receipt)
    assert result.returncode != 0
    assert receipt["state"] != "PASS"
    assert receipt["components"]["pytest"]["state"] != "PASS"
    assert "collection errors 1" in status
    assert "pytest 40/40 outcomes" in status
    assert "lint 0/UNKNOWN NOT RUN" in status
    assert "last full pass: UNKNOWN" in status


def test_only_a_clean_stable_complete_run_updates_last_full_pass(tmp_path):
    body = """cat <<'EOF'
40 passed in 0.01s
clean (3 warning(s))
  PASS alpha
  PASS beta
  PASS hub
  PASS contract
  OK    guards: 4 of 4 registered guard(s) ran and judged
EOF
"""
    repo, record, env = _fixture_repo(tmp_path, body)
    result = _run(repo, record, env)
    receipt = json.loads(record.read_text())
    assert result.returncode == 0, result.stdout + result.stderr
    assert receipt["state"] == "PASS"
    assert receipt["last_full_pass"]["sha"] == _git(repo, "rev-parse", "HEAD")
    assert "pytest 40/40 outcomes" in suite_baseline.format_status(receipt)


def test_a_dirty_tree_pass_is_not_eligible_for_last_full_pass(tmp_path):
    body = """cat <<'EOF'
1 passed in 0.01s
clean (0 warning(s))
  PASS alpha
  PASS beta
  PASS hub
  PASS contract
  OK    guards: 4 of 4 registered guard(s) ran and judged
EOF
"""
    repo, record, env = _fixture_repo(tmp_path, body)
    _write(repo / "dirty.txt", "not represented by HEAD\n")
    result = _run(repo, record, env)
    receipt = json.loads(record.read_text())
    assert result.returncode == 1
    assert receipt["tree_clean_at_start"] is False
    assert receipt["state"] == "INCOMPLETE"
    assert receipt["last_full_pass"] is None
