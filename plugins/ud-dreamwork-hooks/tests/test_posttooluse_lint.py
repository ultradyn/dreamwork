"""PostToolUse ledger-lint hook tests (red-first, #138/#156)."""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from conftest import (
    LEDGER_LINT, assert_contract, make_target, posttool_payload, run_script,
)


def _fake_lint(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_lint.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return script


class TestLedgerLint:
    def test_clean_ledger_reports_ok(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "t"})
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out["hook"] == "ledger-lint"
        assert out["lint"] in ("clean", "warnings")

    def test_tasks_md_also_linted(self, tmp_path):
        target = make_target(tmp_path, status=None)
        (target / ".dreamwork" / "tasks.md").write_text(
            "# Task ledger\n\nNext id: **1**\n", encoding="utf-8")
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "tasks.md", "Edit"),
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out["lint"] in ("clean", "warnings")

    def test_non_ledger_file_skipped(self, tmp_path):
        target = make_target(tmp_path)
        other = target / "src" / "questions.md"
        other.parent.mkdir()
        other.write_text("x", encoding="utf-8")
        proc = run_script(LEDGER_LINT, posttool_payload(other))
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True

    def test_no_file_path_skipped(self, tmp_path):
        payload = posttool_payload(tmp_path / "x.md")
        payload["tool_input"] = {}
        proc = run_script(LEDGER_LINT, payload)
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True

    def test_plugin_not_loaded_skips(self, tmp_path):
        target = make_target(tmp_path, load_line=False)
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True

    def test_missing_lint_py_reports_error_exit_zero(self, tmp_path):
        target = make_target(tmp_path)
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
            env_extra={"DREAMWORK_LINT": str(tmp_path / "no-such-lint.py")},
        )
        out = assert_contract(proc)
        assert out["ok"] is False
        assert "error" in out

    def test_lint_nonzero_exit_reports_error_exit_zero(self, tmp_path):
        target = make_target(tmp_path)
        fake = _fake_lint(tmp_path, """
            import sys
            print("ERROR something is badly shaped")
            sys.exit(1)
        """)
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
            env_extra={"DREAMWORK_LINT": str(fake)},
        )
        out = assert_contract(proc)
        assert out["ok"] is False
        assert "error" in out
        assert "lint_output" in out

    def test_lint_timeout_reports_error_exit_zero(self, tmp_path):
        target = make_target(tmp_path)
        fake = _fake_lint(tmp_path, """
            import time
            time.sleep(30)
        """)
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
            env_extra={"DREAMWORK_LINT": str(fake),
                       "DREAMWORK_LINT_TIMEOUT": "0.5"},
            timeout=20.0,
        )
        out = assert_contract(proc)
        assert out["ok"] is False
        assert "timed out" in out["error"]

    def test_warnings_verdict_when_lint_warns(self, tmp_path):
        target = make_target(tmp_path)
        fake = _fake_lint(tmp_path, """
            print("WARN questions.md missing sections")
            sys = __import__("sys")
            sys.exit(0)
        """)
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
            env_extra={"DREAMWORK_LINT": str(fake)},
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out["lint"] == "warnings"

    def test_garbage_stdin_still_exits_zero(self, tmp_path):
        proc = run_script(LEDGER_LINT, "garbage {")
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True

    def test_real_lint_catches_broken_ledger_through_hook(self, tmp_path):
        """The one path the fake-lint tests skip: the REAL lint.py through the
        REAL hook subprocess against a genuinely malformed ledger.

        The fake-lint tests (nonzero→ok:False, timeout, WARN→warnings) prove the
        hook's plumbing but never run the real lint. The one real-lint test
        (`test_clean_ledger_reports_ok`) uses a valid fixture, so it only proves
        clean→clean. A broken questions.md an agent writes, flowing through real
        hook + real lint, was asserted by nothing.

        Red-proof — two nameable production lines, neither circular (the test
        introduces no seam; the subprocess invocation and $DREAMWORK_LINT both
        predate it):
          (1) lint.py check_questions — if lint stopped erroring on a missing
              `## Open`, the runtime precondition assert below fires.
          (2) posttooluse_ledger_lint.py subprocess.run + returncode gate — if
              the hook stopped invoking lint, the broken ledger returns ok:True.
        """
        target = make_target(tmp_path, status={"current_task": "t"})
        # Genuinely broken: prose present but no `## Open` heading — the ERROR
        # lint.py's check_questions raises. Derived at runtime below, not assumed.
        (target / ".dreamwork" / "questions.md").write_text(
            "# Questions\n\nReal question text the dashboard will never see.\n",
            encoding="utf-8")
        real_lint = LEDGER_LINT.resolve().parents[3] / "lint.py"
        assert real_lint.is_file(), f"real lint.py not found at {real_lint}"
        # Precondition, derived at runtime: the real lint exits nonzero on this.
        pre = subprocess.run(
            [sys.executable, str(real_lint), "--target", str(target)],
            capture_output=True, text=True, timeout=20.0,
        )
        assert pre.returncode != 0, (
            "precondition failed: real lint did not error on the broken ledger; "
            f"the fixture is not what this check depends on.\n{pre.stdout}")
        # Real hook, real lint resolution — empty $DREAMWORK_LINT forces the
        # hook's own parents[3]/lint.py path (falsy override → falls through).
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
            env_extra={"DREAMWORK_LINT": ""},
        )
        out = assert_contract(proc)
        assert out["ok"] is False, (
            "the real hook should surface the real lint's ERROR as ok:false; "
            f"got {out}")
        assert "lint exited" in out.get("error", "")
