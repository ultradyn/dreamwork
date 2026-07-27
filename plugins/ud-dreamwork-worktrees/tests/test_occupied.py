"""Tests for ``occupied.py`` — the mechanical liveness check (#316).

Two layers:

* **Unit** — ``classify`` boundary logic, no process spawning. Locks the
  prefix trap (``/a/bb`` must not match target ``/a/b``) and the deleted
  signature.
* **Integration** — a real scratch git worktree in a temp dir, a real
  ``sleep`` cwd'd inside it, and the check run as the actual executable.

Every integration case asserts its precondition at runtime (the process
is alive and its cwd reads what we think) BEFORE asserting the check's
verdict. A setup that silently failed — wrong cwd, already-dead process,
missing ``/proc`` — fails loudly on the precondition instead of reporting
a clean pass. This is the discipline this repo demands of every check:
three born-hollow checks were found here in one batch.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
OCCUPIED = PLUGIN / "occupied.py"
LINUX = os.path.isdir("/proc")

# Load the module under test by path so the unit tests can call classify()
# directly without polluting sys.modules or relying on an importable name.
_spec = importlib.util.spec_from_file_location("occupied_under_test", OCCUPIED)
assert _spec is not None and _spec.loader is not None, "could not load occupied.py"
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
classify = _mod.classify


def _readlink_cwd(pid: int) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def _must_cwd(pid: int) -> str:
    """readlink that narrows None away — used to assert preconditions."""
    cwd = _readlink_cwd(pid)
    assert cwd is not None, f"could not read /proc/{pid}/cwd"
    return cwd


class TestClassify(unittest.TestCase):
    """Boundary logic for relating a raw readlink to a resolved target."""

    def test_live_at_target(self):
        self.assertEqual(classify("/a/b", "/a/b"), "live")

    def test_live_beneath_target(self):
        self.assertEqual(classify("/a/b/sub", "/a/b"), "live")
        self.assertEqual(classify("/a/b/x/y", "/a/b"), "live")

    def test_stranded_at_target(self):
        self.assertEqual(classify("/a/b (deleted)", "/a/b"), "stranded")

    def test_stranded_beneath_target(self):
        self.assertEqual(classify("/a/b/sub (deleted)", "/a/b"), "stranded")

    def test_sibling_prefix_does_not_match(self):
        # /a/bb shares the text prefix /a/b but is NOT beneath /a/b.
        self.assertIsNone(classify("/a/bb", "/a/b"))
        self.assertIsNone(classify("/a/bb (deleted)", "/a/b"))

    def test_unrelated_path(self):
        self.assertIsNone(classify("/other", "/a/b"))

    def test_cwd_above_target_is_not_a_match(self):
        # A process in /a/b is NOT in target /a/b/c (it is above it).
        self.assertIsNone(classify("/a/b", "/a/b/c"))


@unittest.skipUnless(LINUX, "live /proc integration is linux-only")
class _ScratchWorktreeCase(unittest.TestCase):
    """Shared fixture: a throwaway git repo + worktree under a temp dir.

    ``self.wt`` is the worktree path; ``self.repo`` is the temp repo that
    owns it. Cleaned up in tearDown, including any sleeper still running.
    """

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="occupied-test-"))
        self.wt = self.repo / "wt"
        self._proc: subprocess.Popen | None = None
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(self.repo)}
        for args in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "occupied@test"],
            ["git", "config", "user.name", "occupied-test"],
            ["git", "commit", "-q", "--allow-empty", "-m", "init"],
            ["git", "worktree", "add", "-q", "-b", "wt", str(self.wt)],
        ):
            subprocess.run(args, cwd=self.repo, env=env, check=True,
                           capture_output=True)

    def tearDown(self):
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        if self.repo.exists():
            shutil.rmtree(self.repo, ignore_errors=True)

    def _spawn_sleeper(self, seconds: int = 120) -> subprocess.Popen:
        # A process actually cwd'd in the worktree. cwd= is the whole point:
        # a backgrounded `sleep &` from the test's own cwd would silently be
        # in the wrong place, and the precondition assertion below is what
        # turns that silent failure into a loud one.
        self._proc = subprocess.Popen(["sleep", str(seconds)], cwd=self.wt)
        return self._proc

    def _run_occupied(self, target: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(OCCUPIED), target],
            capture_output=True, text=True,
        )


class TestOccupiedLiveProcess(_ScratchWorktreeCase):
    def test_finds_live_process_and_names_pid_and_command(self):
        proc = self._spawn_sleeper()
        # --- precondition: alive and actually cwd'd in the worktree ---
        self.assertIsNone(proc.poll(), "sleeper should be alive")
        self.assertEqual(_must_cwd(proc.pid), os.path.realpath(self.wt),
                         "sleeper cwd must be the worktree (setup failed)")
        # --- verdict ---
        result = self._run_occupied(str(self.wt))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(str(proc.pid), result.stdout)
        self.assertIn("sleep", result.stdout)
        self.assertIn("live", result.stdout)
        self.assertIn("do not remove", result.stdout)

    def test_clear_once_process_exits(self):
        proc = self._spawn_sleeper(seconds=1)
        # --- precondition before the "found" run: alive + cwd correct ---
        self.assertIsNone(proc.poll())
        self.assertEqual(_must_cwd(proc.pid), os.path.realpath(self.wt))
        found = self._run_occupied(str(self.wt))
        self.assertEqual(found.returncode, 1)
        # --- let it die, then precondition: actually dead ---
        proc.wait(timeout=5)
        self.assertIsNotNone(proc.poll(), "sleeper should have exited")
        self.assertIsNone(_readlink_cwd(proc.pid),
                          "sleeper /proc entry should be gone after exit")
        # --- verdict on the now-empty worktree ---
        clear = self._run_occupied(str(self.wt))
        self.assertEqual(clear.returncode, 0, clear.stdout + clear.stderr)
        self.assertIn("clear", clear.stdout)


class TestOccupiedStrandedProcess(_ScratchWorktreeCase):
    def test_reports_stranded_after_directory_deleted(self):
        proc = self._spawn_sleeper()
        target = os.path.realpath(self.wt)
        # --- precondition A: alive and cwd'd in the worktree ---
        self.assertIsNone(proc.poll())
        self.assertEqual(_must_cwd(proc.pid), target)
        # Delete the worktree directory out from under the running process.
        # The process keeps its cwd; the kernel marks it "(deleted)".
        shutil.rmtree(self.wt)
        self.assertFalse(self.wt.exists())
        # --- precondition B: the kernel's stranded signature ---
        stranded_cwd = _must_cwd(proc.pid)
        self.assertTrue(stranded_cwd.endswith(" (deleted)"),
                        f"expected deleted signature, got {stranded_cwd!r}")
        self.assertEqual(stranded_cwd[: -len(" (deleted)")], target)
        # --- verdict ---
        result = self._run_occupied(target)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(str(proc.pid), result.stdout)
        self.assertIn("stranded", result.stdout)
        self.assertIn("(deleted)", result.stdout)


class TestCliUsage(unittest.TestCase):
    def test_no_args_is_usage_error(self):
        result = subprocess.run([sys.executable, str(OCCUPIED)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage", result.stderr.lower())


class TestCommandLineIsScannable(unittest.TestCase):
    """A dispatched agent's argv CONTAINS ITS WHOLE PROMPT. (#316 follow-up.)

    Found by running the merged tool against a live worktree: one `ccc` agent
    printed thousands of characters across many lines, so the "one line per
    process, cwd beneath it" format stopped existing and neither the second
    process nor the do-not-remove verdict was visible. The report has to stay
    readable by the operator who is about to delete something.
    """

    def test_a_prompt_sized_command_line_stays_one_short_line(self):
        prompt = "You are a dreamer subagent\n" * 400
        cmd = f"ccc @glm52 -y --timeout-secs 2100 {prompt}"
        # Preconditions: without BOTH of these the assertions below are vacuous
        # — a short cmdline is not abridged, and a single-line one cannot show
        # that newlines are collapsed.
        self.assertGreater(len(cmd), _mod._CMD_WIDTH * 5,
                           "fixture must be far longer than the width, else nothing is cut")
        self.assertIn("\n", cmd, "fixture must be multi-line, else the collapse is untested")

        shown, cut = _mod._one_line(cmd)
        self.assertTrue(cut, "a prompt-sized command line must report as abridged")
        self.assertNotIn("\n", shown, "it must collapse to ONE line or the format breaks")
        self.assertLessEqual(len(shown), _mod._CMD_WIDTH + 40,
                             "and stay near the width, not merely lose its newlines")
        self.assertIn("ccc @glm52", shown, "the recognisable head must survive")
        self.assertIn("chars", shown, "and it must say how much was withheld")

    def test_a_short_command_line_is_left_exactly_alone(self):
        shown, cut = _mod._one_line("sleep 600")
        self.assertEqual(shown, "sleep 600")
        self.assertFalse(cut, "nothing was cut, so nothing may claim it was")


if __name__ == "__main__":
    unittest.main()
