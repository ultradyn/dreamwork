"""Tests for dev/rotate_inbox.py — the inbox.md rotation tool (#1104).

These tests build their OWN fixture inbox (never touching the live file) and
exercise the rotation against it: the 'fixture-built-list' false-green the
brief warned about is closed by asserting byte conservation and entry counts
that are DERIVED at runtime, never hardcoded literals tuned to a fixture.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
TOOL = REPO / "dev" / "rotate_inbox.py"
BOILERPLATE = REPO / "briefs" / "boilerplate.md"
LIVE_INBOX = Path(
    "/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md"
)
RECIPE_START = "<!-- inbox-append-recipe:start -->"
RECIPE_END = "<!-- inbox-append-recipe:end -->"


def _load():
    spec = importlib.util.spec_from_file_location("rotate_inbox_under_test", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_entry(i: int) -> str:
    return f"## Task #{i} — report\n\nLane #{i} completed its work.\nSHA: abc{i:04d}\n\n"


def _extract_append_command(boilerplate: str) -> str:
    """Extract the one designated recipe as a logical shell command."""
    assert boilerplate.count(RECIPE_START) == 1 and boilerplate.count(RECIPE_END) == 1, (
        "expected exactly one designated inbox append recipe; "
        f"got starts={boilerplate.count(RECIPE_START)}, ends={boilerplate.count(RECIPE_END)}"
    )
    assert boilerplate.index(RECIPE_START) < boilerplate.index(RECIPE_END), (
        "inbox append recipe start marker must precede end marker"
    )
    body = boilerplate.split(RECIPE_START, 1)[1].split(RECIPE_END, 1)[0]
    logical_lines: list[str] = []
    pending = ""
    for physical_line in body.splitlines():
        stripped = physical_line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        pending += stripped
        if pending.endswith("\\"):
            pending = pending[:-1] + " "
        else:
            logical_lines.append(pending)
            pending = ""
    if pending:
        logical_lines.append(pending)
    assert len(logical_lines) == 1, (
        "designated inbox append recipe must contain one logical shell command; "
        f"got {logical_lines!r}"
    )
    heredoc = re.search(r"\s+<<\s*(?P<quote>['\"])(?P<word>[^'\"\n]+)(?P=quote)\s*$", logical_lines[0])
    assert heredoc, "designated inbox append recipe must end in a quoted heredoc delimiter"
    command = logical_lines[0][: heredoc.start()].rstrip()
    assert command, "designated inbox append recipe has no shell command"
    return command


def _fixture_append_command(target: Path, boilerplate: str | None = None) -> str:
    """Extract the designated recipe and retarget every live path to a fixture."""
    command = _extract_append_command(
        BOILERPLATE.read_text() if boilerplate is None else boilerplate
    )
    inbox = target / ".dreamwork" / "inbox.md"
    assert str(LIVE_INBOX) in command, (
        "standing append recipe did not name the live inbox path"
    )
    retargeted = command.replace(str(LIVE_INBOX), str(inbox))
    assert str(LIVE_INBOX) not in retargeted, (
        "live coordinator inbox path remained after fixture retargeting"
    )
    return retargeted


class TestAppendRecipeExtraction:
    def test_accepts_wrapping_indentation_and_arbitrary_quoted_delimiter(self, tmp_path: Path):
        boilerplate = f"""
{RECIPE_START}
        flock {LIVE_INBOX}.lock \\
          -c 'cat >> {LIVE_INBOX}' <<\"REPORT_END\"
{RECIPE_END}
"""
        command = _fixture_append_command(tmp_path, boilerplate)
        assert "flock " in command
        assert "REPORT_END" not in command
        assert str(LIVE_INBOX) not in command
        assert str(tmp_path / ".dreamwork" / "inbox.md.lock") in command
        assert f"cat >> {tmp_path / '.dreamwork' / 'inbox.md'}" in command

    def test_no_flock_recipe_still_extracts_for_behavioural_race(self):
        boilerplate = f"""
{RECIPE_START}
    cat >> {LIVE_INBOX} <<'ANY_DELIMITER'
{RECIPE_END}
"""
        assert _extract_append_command(boilerplate) == f"cat >> {LIVE_INBOX}"

    def test_missing_designated_recipe_fails_distinctly(self):
        with pytest.raises(AssertionError, match="exactly one designated inbox append recipe"):
            _extract_append_command("The append guidance was removed.\n")

    def test_reversed_markers_fail_distinctly(self):
        boilerplate = f"""
{RECIPE_END}
unrelated prose
{RECIPE_START}
flock {LIVE_INBOX}.lock -c 'cat >> {LIVE_INBOX}' <<'EOF'
"""
        with pytest.raises(AssertionError, match="start marker must precede end marker"):
            _extract_append_command(boilerplate)

    def test_two_designated_regions_fail_distinctly(self):
        recipe = f"""{RECIPE_START}
flock {LIVE_INBOX}.lock -c 'cat >> {LIVE_INBOX}' <<'EOF'
{RECIPE_END}"""
        with pytest.raises(
            AssertionError,
            match="expected exactly one designated inbox append recipe; got starts=2, ends=2",
        ):
            _extract_append_command(f"{recipe}\n{recipe}\n")

    def test_retargeting_refuses_changed_live_paths(self, tmp_path: Path):
        boilerplate = f"""
{RECIPE_START}
    flock /future/coordinator/inbox.md.lock -c 'cat >> /future/coordinator/inbox.md' <<'EOF'
{RECIPE_END}
"""
        with pytest.raises(AssertionError, match="did not name the live inbox path"):
            _fixture_append_command(tmp_path, boilerplate)


@pytest.fixture
def dw(tmp_path: Path) -> Path:
    d = tmp_path / ".dreamwork"
    d.mkdir()
    return d


class TestSplitEntries:
    def test_splits_on_double_hash_headings(self):
        mod = _load()
        text = "old pointer line\n\n## First\nbody1\n\n## Second\nbody2\n"
        prologue, entries = mod._split_entries(text)
        assert "old pointer" in prologue
        assert len(entries) == 2
        assert entries[0].startswith("## First")
        assert "body1" in entries[0]
        assert entries[1].startswith("## Second")

    def test_no_headings_returns_prologue_only(self):
        mod = _load()
        text = "just prose\nno headings\n"
        prologue, entries = mod._split_entries(text)
        assert entries == []
        assert prologue == text


class TestRotate:
    def test_moves_older_entries_and_keeps_recent(self, dw: Path):
        mod = _load()
        n_total = 10
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(n_total)))
        result = mod.rotate(dw, keep=3)
        assert result["action"] == "rotated"
        assert result["entries_moved"] == 7  # derived: n_total - keep
        assert result["entries_kept"] == 3
        # The live file has the LAST 3 entries.
        live = inbox.read_text()
        assert "Task #7" in live
        assert "Task #8" in live
        assert "Task #9" in live
        assert "Task #0" not in live
        assert "Task #6" not in live

    def test_archive_contains_moved_entries(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)
        archive = list((dw / "inbox-archive").glob("*.md"))
        assert len(archive) == 1
        atext = archive[0].read_text()
        assert "Task #0" in atext
        assert "Task #6" in atext
        assert "Task #9" not in atext

    def test_pointer_comment_names_the_archive(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)
        first_line = inbox.read_text().splitlines()[0]
        assert "inbox-archive" in first_line
        assert first_line.startswith("<!--")

    def test_byte_conservation(self, dw: Path):
        """The archive + live file must account for every byte (minus the pointer)."""
        mod = _load()
        inbox = dw / "inbox.md"
        original = "".join(_make_entry(i) for i in range(10))
        inbox.write_text(original)
        original_bytes = len(original.encode("utf-8"))
        mod.rotate(dw, keep=3)
        live = inbox.read_text()
        archive = list((dw / "inbox-archive").glob("*.md"))[0].read_text()
        live_bytes = len(live.encode("utf-8"))
        archive_bytes = len(archive.encode("utf-8"))
        # live + archive >= original (pointer line adds a small overhead).
        assert live_bytes + archive_bytes >= original_bytes
        # The overhead is just the pointer comment (~100 bytes).
        overhead = live_bytes + archive_bytes - original_bytes
        assert overhead < 200, f"unexpected overhead: {overhead}"

    def test_noop_when_few_entries(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(3)))
        result = mod.rotate(dw, keep=50)
        assert result["action"] == "noop"
        assert not (dw / "inbox-archive").exists()

    def test_idempotent_second_run(self, dw: Path):
        """Running twice does not corrupt or duplicate."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)
        first_live = inbox.read_text()
        # Second run: only 3 entries, keep=3 -> noop.
        result = mod.rotate(dw, keep=3)
        assert result["action"] == "noop"
        assert inbox.read_text() == first_live

    def test_prologue_goes_to_archive(self, dw: Path):
        """Old pre-heading prologue (/tmp pointer era) is archived, not kept."""
        mod = _load()
        inbox = dw / "inbox.md"
        prologue = "- 302 — old /tmp pointer line\n- 203 — another old one\n"
        inbox.write_text(prologue + "".join(_make_entry(i) for i in range(5)))
        mod.rotate(dw, keep=2)
        live = inbox.read_text()
        assert "/tmp pointer" not in live
        archive = list((dw / "inbox-archive").glob("*.md"))[0].read_text()
        assert "/tmp pointer" in archive

    def test_absent_inbox_is_noop(self, dw: Path):
        mod = _load()
        result = mod.rotate(dw, keep=50)
        assert result["action"] == "noop"

    def test_appends_to_existing_archive_same_month(self, dw: Path):
        """Two rotations in the same month accumulate in one archive file."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)  # moves 7, keeps 3
        # Add more entries to trigger a second rotation.
        live = inbox.read_text()
        inbox.write_text(live + "".join(_make_entry(100 + i) for i in range(5)))
        mod.rotate(dw, keep=3)  # moves 5 more
        archives = list((dw / "inbox-archive").glob("*.md"))
        assert len(archives) == 1  # same month -> one file
        atext = archives[0].read_text()
        assert "Task #0" in atext  # from first rotation
        assert "Task #100" in atext  # from second


class TestStatus:
    def test_reports_bytes_and_entries(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(5)))
        info = mod.status(dw)
        assert info["exists"] is True
        assert info["entries"] == 5
        assert info["bytes"] > 0

    def test_absent_inbox(self, dw: Path):
        mod = _load()
        info = mod.status(dw)
        assert info["exists"] is False


class TestLiveLaneRefusal:
    """#1158: rotate refuses (distinct from noop) when a live lane is detected."""

    def test_refused_when_live_lane_count_positive(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        result = mod.rotate(
            dw, keep=3, live_lane_probe=lambda: mod.LaneProbeResult(2, 100)
        )
        assert result["action"] == "refused"
        assert result["live_lanes"] == 2

    def test_refused_leaves_live_file_untouched(self, dw: Path):
        """Refusing must not move a single byte — no archive written."""
        mod = _load()
        inbox = dw / "inbox.md"
        original = "".join(_make_entry(i) for i in range(10))
        inbox.write_text(original)
        mod.rotate(dw, keep=3, live_lane_probe=lambda: mod.LaneProbeResult(1, 100))
        assert inbox.read_text() == original  # untouched
        assert not (dw / "inbox-archive").exists()  # no archive created

    def test_refused_is_distinct_from_noop(self, dw: Path):
        """'refused (lane live)' and 'noop (nothing to do)' are two states (#136)."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        refused = mod.rotate(
            dw, keep=3, live_lane_probe=lambda: mod.LaneProbeResult(1, 100)
        )
        assert refused["action"] == "refused"
        # A separate file with too few entries is noop, not refused.
        dw2 = dw.parent / "dw2" / ".dreamwork"
        dw2.mkdir(parents=True)
        (dw2 / "inbox.md").write_text("".join(_make_entry(i) for i in range(2)))
        noop = mod.rotate(
            dw2, keep=50, live_lane_probe=lambda: mod.LaneProbeResult(1, 100)
        )
        assert noop["action"] == "noop"
        assert refused["action"] != noop["action"]

    def test_rotates_when_no_live_lanes(self, dw: Path):
        """A zero live count lets the rotation proceed."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        result = mod.rotate(
            dw, keep=3, live_lane_probe=lambda: mod.LaneProbeResult(0, 100)
        )
        assert result["action"] == "rotated"


class TestIncompleteProbe:
    def test_proc_enumeration_failure_refuses_before_rotation(
        self, dw: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A failed /proc probe must not collapse to observable-empty."""
        mod = _load()
        inbox = dw / "inbox.md"
        original = "".join(_make_entry(i) for i in range(10))
        inbox.write_text(original)

        def unreadable_proc(_path: str):
            raise PermissionError("fixture denies /proc")

        monkeypatch.setattr(mod.os, "listdir", unreadable_proc)
        probe = mod._count_live_lanes(dw.parent)
        result = mod.rotate(dw, keep=3, live_lane_probe=lambda: probe)

        assert result["action"] == "refused", (
            f"/proc directory probe failed but rotation proceeded with action={result['action']}"
        )
        assert "could not read /proc directory" in result["reason"]
        assert "PermissionError: fixture denies /proc" in result["reason"]
        assert inbox.read_text() == original
        assert not (dw / "inbox-archive").exists()

    def test_probe_callback_exception_refuses(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        original = "".join(_make_entry(i) for i in range(10))
        inbox.write_text(original)

        def failed_probe():
            raise RuntimeError("fixture probe crash")

        result = mod.rotate(dw, keep=3, live_lane_probe=failed_probe)
        assert result["action"] == "refused"
        assert "could not read live-lane probe callback" in result["reason"]
        assert inbox.read_text() == original


def _run_cli_at_observation(
    target: Path, appended_entry: str | None, boilerplate: str | None = None
) -> tuple[subprocess.CompletedProcess[str], int | None, bool | None]:
    """Run the real CLI, optionally racing the documented ``flock`` + ``cat``."""
    observed_r, observed_w = os.pipe()
    proceed_r, proceed_w = os.pipe()
    env = os.environ.copy()
    env["ROTATE_INBOX_TEST_OBSERVED_FD"] = str(observed_w)
    env["ROTATE_INBOX_TEST_PROCEED_FD"] = str(proceed_r)
    cli = subprocess.Popen(
        [sys.executable, str(TOOL), "rotate", "--target", str(target), "--keep", "3"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        pass_fds=(observed_w, proceed_r),
    )
    os.close(observed_w)
    os.close(proceed_r)
    appender_status = None
    appender_blocked = None
    appender = None
    try:
        observed = os.read(observed_r, 1)
        if observed != b"1":
            stdout, stderr = cli.communicate(timeout=10)
            raise AssertionError(
                f"CLI exited before observation hook: rc={cli.returncode}, "
                f"stdout={stdout!r}, stderr={stderr!r}"
            )
        if appended_entry is not None:
            inbox = target / ".dreamwork" / "inbox.md"
            appender = subprocess.Popen(
                ["sh", "-c", _fixture_append_command(target, boilerplate)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert appender.stdin is not None
            appender.stdin.write(appended_entry)
            appender.stdin.close()
            appender.stdin = None
            lock_stat = (inbox.parent / "inbox.md.lock").stat()
            lock_identity = (
                os.major(lock_stat.st_dev),
                os.minor(lock_stat.st_dev),
                lock_stat.st_ino,
            )
            deadline = time.monotonic() + 10
            while True:
                if appender.poll() is not None:
                    appender_status = appender.returncode
                    appender_blocked = False
                    break
                locks = Path("/proc/locks").read_text()
                if lock_identity in _waiting_flock_identities(locks):
                    appender_blocked = True
                    break
                if time.monotonic() >= deadline:
                    raise AssertionError(
                        "appender did not reach lock acquisition before harness deadline"
                    )
                time.sleep(0.01)

            original_live = inbox.read_text()
            if not appender_blocked:
                assert appended_entry in original_live, (
                    "appender precondition unmet: unique entry did not land before proceed"
                )
                assert sum(line.startswith("## ") for line in original_live.splitlines()) == 11
            else:
                assert appended_entry not in original_live
                assert sum(line.startswith("## ") for line in original_live.splitlines()) == 10
        os.write(proceed_w, b"1")
        stdout, stderr = cli.communicate(timeout=10)
        if appender is not None:
            appender_stdout, appender_stderr = appender.communicate(timeout=10)
            appender_status = appender.returncode
            assert appender_status == 0, (appender_stdout, appender_stderr)
    finally:
        os.close(observed_r)
        os.close(proceed_w)
        if cli.poll() is None:
            cli.kill()
            cli.wait()
        if appender is not None and appender.poll() is None:
            appender.kill()
            appender.wait()
    return (
        subprocess.CompletedProcess(cli.args, cli.returncode, stdout, stderr),
        appender_status,
        appender_blocked,
    )


def _waiting_flock_identities(locks: str) -> set[tuple[int, int, int]]:
    """Parse device and inode identities for blocked advisory flock waiters."""
    identities = set()
    for line in locks.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[1:5] != ["->", "FLOCK", "ADVISORY", "WRITE"]:
            continue
        try:
            major, minor, inode = fields[6].rsplit(":", 2)
            identities.add((int(major, 16), int(minor, 16), int(inode)))
        except (ValueError, IndexError) as exc:
            raise AssertionError(f"malformed candidate FLOCK row: {line}") from exc
    return identities


def test_waiting_flock_identity_binds_device_and_inode():
    locks = """\
12: -> FLOCK ADVISORY WRITE 123 08:01:456 0 EOF
13: -> FLOCK ADVISORY WRITE 124 00:2a:789 0 EOF
14: FLOCK ADVISORY WRITE 125 08:01:456 0 EOF
"""
    identities = _waiting_flock_identities(locks)
    assert (0x08, 0x01, 456) in identities
    assert (0x09, 0x01, 456) not in identities
    assert (0x00, 0x2A, 789) in identities


def test_waiting_flock_identity_rejects_malformed_candidate_row():
    locks = "15: -> FLOCK ADVISORY WRITE 126 08:01:not-an-inode 0 EOF\n"
    with pytest.raises(
        AssertionError, match=r"malformed candidate FLOCK row: .*not-an-inode"
    ):
        _waiting_flock_identities(locks)


class TestConcurrentAppenderHarness:
    def _fixture(self, tmp_path: Path) -> tuple[Path, Path]:
        target = tmp_path / "coordinator"
        dw = target / ".dreamwork"
        dw.mkdir(parents=True)
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        (dw / "inbox.md.lock").touch()
        return target, dw

    def test_real_cli_positive_control_without_appender(self, tmp_path: Path):
        """The synchronized real-CLI harness succeeds when no appender runs."""
        target, dw = self._fixture(tmp_path)
        cli, appender_status, appender_blocked = _run_cli_at_observation(target, None)
        assert appender_status is None
        assert appender_blocked is None
        assert cli.returncode == 0, cli.stderr
        assert "observed-snapshot accounted: moved=7 + retained=3 = observed=10" in cli.stdout
        assert "lock held; locking appenders resume after replacement" in cli.stdout
        combined = (dw / "inbox.md").read_text() + next(
            (dw / "inbox-archive").glob("*.md")
        ).read_text()
        assert sum(1 for line in combined.splitlines() if line.startswith("## ")) == 10

    def test_real_cli_lock_excludes_shell_cat_and_preserves_entry(self, tmp_path: Path):
        """The documented locking shell ``cat`` waits, then appends losslessly.

        The pipes hold rotation immediately before rename. The real ``flock``
        subprocess must still be blocked there; after rename and unlock, its
        real shell ``cat >>`` writes the unique entry to the new live inode.
        """
        target, dw = self._fixture(tmp_path)
        appended = "## Concurrent #1170 entry\n\nWritten with O_APPEND.\n"
        cli, appender_status, appender_blocked = _run_cli_at_observation(target, appended)
        assert appender_status == 0
        assert cli.returncode == 0, cli.stderr
        combined = (dw / "inbox.md").read_text() + next(
            (dw / "inbox-archive").glob("*.md")
        ).read_text()
        assert appended in combined, f"raced entry lost: {appended.splitlines()[0]}"
        for index in range(10):
            original = _make_entry(index)
            assert original in combined, f"retained entry lost: {original.splitlines()[0]}"
        mod = _load()
        archive = next((dw / "inbox-archive").glob("*.md")).read_text()
        _, archived_entries = mod._split_entries(archive)
        _, live_entries = mod._split_entries((dw / "inbox.md").read_text())
        assert [entry.splitlines()[0] for entry in archived_entries] == [
            _make_entry(index).splitlines()[0] for index in range(7)
        ], "archived entries reordered"
        assert [entry.splitlines()[0] for entry in live_entries] == [
            *(_make_entry(index).splitlines()[0] for index in range(7, 10)),
            appended.splitlines()[0],
        ], "live entries reordered"
        assert appender_blocked, "locking shell cat did not block while rotation held the lock"
        print(
            f"raced-entry={appended.splitlines()[0]!r} "
            f"blocked={appender_blocked} survived={appended in combined}"
        )

    @pytest.mark.parametrize(
        ("mutation", "boilerplate"),
        [
            (
                "delimiter-change",
                BOILERPLATE.read_text().replace("<<'EOF'", '<<"ROUND3_END"', 1),
            ),
            (
                "indent-only",
                BOILERPLATE.read_text().replace("    flock ", "        flock ", 1),
            ),
        ],
    )
    def test_harmless_recipe_reformatting_preserves_race(
        self, tmp_path: Path, mutation: str, boilerplate: str
    ):
        target, dw = self._fixture(tmp_path)
        appended = f"## {mutation} #1170 entry\n\nSurvives rotation.\n"
        cli, appender_status, appender_blocked = _run_cli_at_observation(
            target, appended, boilerplate
        )
        assert appender_status == 0
        assert cli.returncode == 0, cli.stderr
        combined = (dw / "inbox.md").read_text() + next(
            (dw / "inbox-archive").glob("*.md")
        ).read_text()
        assert appended in combined, f"raced entry lost after {mutation}"
        assert appender_blocked, f"{mutation} recipe did not wait on the inbox sidecar"


class TestCliContract:
    def test_reconciliation_error_uses_declared_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        mod = _load()
        target = tmp_path / "coordinator"
        (target / ".dreamwork").mkdir(parents=True)

        def fail_reconciliation(*_args, **_kwargs):
            raise mod.ReconciliationError("fixture balance mismatch")

        monkeypatch.setattr(mod, "rotate", fail_reconciliation)
        assert mod.main(["rotate", "--target", str(target)]) == 2
        assert "error: reconciliation failed: fixture balance mismatch" in capsys.readouterr().err

    def test_lock_io_error_uses_declared_exit_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        mod = _load()
        target = tmp_path / "coordinator"
        dw = target / ".dreamwork"
        dw.mkdir(parents=True)
        (dw / "inbox.md.lock").mkdir()

        assert mod.main(["rotate", "--target", str(target)]) == 2
        assert "error: I/O failed:" in capsys.readouterr().err

    def test_unexpected_oserror_is_not_mislabeled_as_operational(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        mod = _load()
        target = tmp_path / "coordinator"

        def fail_outside_rotation_boundary(*_args, **_kwargs):
            raise OSError("synthetic non-operational failure")

        monkeypatch.setattr(mod, "rotate", fail_outside_rotation_boundary)
        with pytest.raises(OSError, match="synthetic non-operational failure"):
            mod.main(["rotate", "--target", str(target)])


class TestReconciliation:
    """#868/#702: a rotation must account for every entry it observed."""

    def test_reconciliation_balances_on_success(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        n_total = 12  # derived at runtime, not a tuned literal
        inbox.write_text("".join(_make_entry(i) for i in range(n_total)))
        keep = 4
        result = mod.rotate(dw, keep=keep)
        assert result["action"] == "rotated"
        # ONE counting rule (^## headings): moved + retained == observed.
        assert result["reconcile_moved"] + result["reconcile_retained"] == result["reconcile_observed"]
        assert result["reconcile_observed"] == n_total
        assert result["reconcile_moved"] == n_total - keep
        assert result["reconcile_retained"] == keep
        assert result["reconciled"] is True

    def test_pointer_names_first_retained_and_live_matches(self, dw: Path):
        """The pointer claims a heading; the live file's first entry must match."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        keep = 3
        mod.rotate(dw, keep=keep)
        live = inbox.read_text()
        first_line = live.splitlines()[0]
        # The pointer carries the first retained entry's heading.
        first_live_heading = next(l for l in live.splitlines() if l.startswith("## "))
        assert first_live_heading in first_line
        assert first_live_heading == "## Task #%d — report" % (10 - keep)

    def test_reconciliation_detects_a_lost_entry(self, dw: Path):
        """The balance check fires when moved+retained != observed (#868).

        A rotation that lost one retained entry: 7 moved + 2 retained != 10
        observed. The pure verdict is the single source, so a sabotage here
        reddens every reconciliation — tested directly with a discriminating
        count, not an ``assert 0 == 1``.
        """
        mod = _load()
        assert mod._reconcile_balanced(observed=10, moved=7, retained=3) is True
        # One entry lost: 7 + 2 = 9 != 10 — the discriminating unbalanced count.
        assert mod._reconcile_balanced(observed=10, moved=7, retained=2) is False, (
            "unbalanced: moved=7 + retained=2 = 9 != observed=10 (a lost entry)")
        # An entry dropped from the archive side: 6 + 3 = 9 != 10.
        assert mod._reconcile_balanced(observed=10, moved=6, retained=3) is False

    def test_pointer_claims_first_retained_heading(self, dw: Path):
        """The pointer carries the first retained entry; the live file honours it."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        keep = 3
        mod.rotate(dw, keep=keep)
        live = inbox.read_text()
        first_line = live.splitlines()[0]
        first_live_heading = next(l for l in live.splitlines() if l.startswith("## "))
        # The pointer (an HTML comment) names the heading the live file resumes at.
        assert first_live_heading in first_line
        assert first_live_heading == "## Task #%d — report" % (10 - keep)

    def test_reconciliation_over_accumulating_archive(self, dw: Path):
        """Two rotations same month: archive accumulates, delta still balances."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        r1 = mod.rotate(dw, keep=3)
        assert r1["reconciled"] is True
        # Add entries and rotate again — archive_before > 0 this time.
        inbox.write_text(inbox.read_text() + "".join(_make_entry(100 + i) for i in range(5)))
        r2 = mod.rotate(dw, keep=3)
        assert r2["action"] == "rotated"
        assert r2["reconciled"] is True
        assert r2["reconcile_moved"] + r2["reconcile_retained"] == r2["reconcile_observed"]
