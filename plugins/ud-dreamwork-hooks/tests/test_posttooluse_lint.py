"""PostToolUse ledger-lint hook tests (red-first, #138/#156/#387)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

from conftest import (
    LEDGER_LINT, assert_contract, make_target, posttool_payload, run_script,
)


def _fake_lint(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_lint.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return script


def _bash_payload(target: Path, *, cwd: str | None = "default",
                  command: str = "python3 -c pass") -> dict:
    """Fabricate a PostToolUse Bash event. A Bash event carries a
    `command` in tool_input and NO file_path — the ledger path lives inside
    the heredoc source, which is exactly the gap #387 filed. `cwd` is the
    only handle the hook has to the target."""
    payload = {
        "session_id": "sess-test",
        "transcript_path": "/tmp/transcript.jsonl",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"success": True},
    }
    if cwd == "default":
        payload["cwd"] = str(target)
    elif cwd is not None:
        payload["cwd"] = cwd
    # cwd is None → omit the key entirely (the absent-cwd edge)
    return payload


STATE_FILENAME = ".ledger-lint-mtimes.json"


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


class TestBashMtime:
    """The Bash/mtime branch (#387). A Bash event carries no file_path, so
    the hook resolves the target from `cwd` and compares the two ledger
    files' mtimes against a stored state, linting only when one moved.

    Born-red BEFORE the implementation: every assertion here exercises a
    production line (the mtime comparison, the cwd→target resolution, the
    state read/write) that the current `run()` cannot reach, because today
    `run()` returns "no file_path in tool input" the instant it sees a Bash
    event. So each test must fail with that skip reason until the branch
    lands.
    """

    def test_bash_moved_mtime_triggers_lint(self, tmp_path):
        """A Bash event where a ledger file's mtime moved past the stored
        state fires the lint subprocess."""
        target = make_target(tmp_path)
        dw = target / ".dreamwork"
        state_path = dw / STATE_FILENAME
        questions = dw / "questions.md"

        # Seed the state file with the CURRENT mtime, then bump the file so
        # the stored value is genuinely older (the precondition this check
        # depends on — derived at runtime, not a literal).
        seed = {str(questions): questions.stat().st_mtime_ns}
        state_path.write_text(json.dumps(seed), encoding="utf-8")
        # Force a real mtime advance (filesystem granularity can be 1s on
        # some Linux setups; st_mtime_ns is the field the hook compares).
        time.sleep(1.05)
        questions.write_text(questions.read_text(encoding="utf-8"),
                             encoding="utf-8")
        os.utime(questions, ns=(questions.stat().st_atime_ns,
                                questions.stat().st_mtime_ns))
        now_mtime = questions.stat().st_mtime_ns
        assert now_mtime > seed[str(questions)], (
            "precondition failed: the fixture did not advance the ledger "
            f"mtime ({seed[str(questions)]} -> {now_mtime}); this check is "
            "about a moved mtime, so it asserts nothing if it didn't move")

        fake = _fake_lint(tmp_path, """\
            print("clean")
        """)
        proc = run_script(
            LEDGER_LINT,
            _bash_payload(target),
            env_extra={"DREAMWORK_LINT": str(fake)},
        )
        out = assert_contract(proc)
        assert out["ok"] is True, f"hook should run lint on a moved mtime: {out}"
        assert out.get("lint") in ("clean", "warnings"), (
            "a Bash event with a moved ledger mtime must have actually run "
            f"lint (no 'lint' key); got {out}")

    def test_bash_appearing_file_triggers_lint(self, tmp_path):
        """A Bash event where a ledger file APPEARS after seeding (it was
        absent from the state) triggers a lint. A structural change — a
        ledger file springing into existence — is exactly the kind of edit
        the hook exists to check. The moved comparison must treat an absent
        entry as moved, not ignore it (`stored.get(name) != current[name]`,
        not `name in stored and ...`)."""
        target = make_target(tmp_path)
        dw = target / ".dreamwork"
        state_path = dw / STATE_FILENAME
        questions = dw / "questions.md"
        tasks = dw / "tasks.md"

        # Seed with ONLY questions.md recorded — the documented make_target
        # does not create tasks.md, so it is genuinely absent at seed-time
        # (the precondition this check depends on — derived at runtime).
        seed = {str(questions): questions.stat().st_mtime_ns}
        assert str(tasks) not in seed, (
            "precondition failed: tasks.md is in the seed; the appearing-file "
            "case needs it ABSENT from the stored state")
        assert not tasks.exists(), (
            "precondition failed: tasks.md exists at seed-time; the "
            "appearing-file case needs it to appear AFTER seeding")
        state_path.write_text(json.dumps(seed), encoding="utf-8")

        # tasks.md now appears — the structural change.
        tasks.write_text("# Task ledger\n\nNext id: **1**\n", encoding="utf-8")
        assert tasks.exists(), (
            "precondition failed: tasks.md did not appear after seeding")

        fake = _fake_lint(tmp_path, """\
            print("clean")
        """)
        proc = run_script(
            LEDGER_LINT,
            _bash_payload(target),
            env_extra={"DREAMWORK_LINT": str(fake)},
        )
        out = assert_contract(proc)
        assert out["ok"] is True, (
            f"hook should run lint when a ledger file appears: {out}")
        assert out.get("lint") in ("clean", "warnings"), (
            "a Bash event where a ledger file appeared must have actually "
            f"run lint (no 'lint' key); got {out}")

    def test_bash_unmoved_mtime_skips_lint(self, tmp_path):
        """A Bash event where neither ledger file moved does NOT run lint."""
        target = make_target(tmp_path)
        dw = target / ".dreamwork"
        state_path = dw / STATE_FILENAME
        questions = dw / "questions.md"

        # Seed with the current mtime; do NOT touch the file afterwards, so
        # the stored value equals the on-disk value (the precondition).
        seed = {str(questions): questions.stat().st_mtime_ns}
        state_path.write_text(json.dumps(seed), encoding="utf-8")
        assert questions.stat().st_mtime_ns == seed[str(questions)], (
            "precondition failed: the seeded mtime does not match disk; the "
            "unmoved case cannot be asserted from a moving fixture")

        # A fake lint that explodes if invoked — the proof the subprocess
        # was NOT spawned is that the hook never reports its output.
        fake = _fake_lint(tmp_path, """\
            import sys
            print("SHOULD NOT RUN")
            sys.exit(0)
        """)
        proc = run_script(
            LEDGER_LINT,
            _bash_payload(target),
            env_extra={"DREAMWORK_LINT": str(fake)},
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("lint") is None, (
            "an unmoved mtime must not run lint, but the 'lint' key is set; "
            f"got {out}")
        assert "SHOULD NOT RUN" not in out.get("lint_output", "")

    def test_bash_no_state_seeds_silently(self, tmp_path):
        """A Bash event with NO state file seeds without linting. A write
        that happened before the hook first looked is not this hook's
        window — it has no baseline to call 'moved'."""
        target = make_target(tmp_path)
        dw = target / ".dreamwork"
        state_path = dw / STATE_FILENAME
        assert not state_path.exists(), "precondition: no state file"

        fake = _fake_lint(tmp_path, """\
            import sys
            print("SHOULD NOT RUN")
            sys.exit(0)
        """)
        proc = run_script(
            LEDGER_LINT,
            _bash_payload(target),
            env_extra={"DREAMWORK_LINT": str(fake)},
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("lint") is None, (
            "first sight must seed without linting, but lint ran; got {out}")
        assert "SHOULD NOT RUN" not in out.get("lint_output", "")
        # And it did seed: the state file now exists with the ledger mtime.
        assert state_path.exists(), (
            "the state file should have been created on first sight")
        seeded = json.loads(state_path.read_text(encoding="utf-8"))
        q = str(dw / "questions.md")
        assert q in seeded, f"seeded state should name questions.md: {seeded}"

    def test_bash_absent_cwd_skips_with_reason(self, tmp_path):
        """A Bash event with no cwd (or a cwd that is not a dreamwork
        target) is skipped with a named reason — there is no handle to the
        ledger."""
        target = make_target(tmp_path)
        proc = run_script(
            LEDGER_LINT,
            _bash_payload(target, cwd=None),
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True
        reason = out.get("reason", "")
        assert "cwd" in reason.lower(), (
            f"a Bash event with no cwd should name cwd in its skip reason; "
            f"got {out}")

    def test_bash_cwd_not_dreamwork_skips(self, tmp_path):
        """A Bash event whose cwd is not a dreamwork target is skipped."""
        target = make_target(tmp_path)
        proc = run_script(
            LEDGER_LINT,
            _bash_payload(target, cwd=str(tmp_path)),
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True

    def test_bash_plugin_not_loaded_skips(self, tmp_path):
        """The consent boundary holds on the Bash path too."""
        target = make_target(tmp_path, load_line=False)
        proc = run_script(LEDGER_LINT, _bash_payload(target))
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True

    def test_write_edit_path_unchanged_by_bash_branch(self, tmp_path):
        """The existing Write/Edit file_path route behaves byte-for-byte as
        today: the Bash branch is a sibling, not a rewrite."""
        target = make_target(tmp_path, status={"current_task": "t"})
        proc = run_script(
            LEDGER_LINT,
            posttool_payload(target / ".dreamwork" / "questions.md"),
        )
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out["lint"] in ("clean", "warnings")
        # The Write/Edit route must not touch the Bash state file.
        assert not (target / ".dreamwork" / STATE_FILENAME).exists(), (
            "the Write/Edit path must not write the Bash mtime state")
