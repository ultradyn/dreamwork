"""install.py contract tests (red-first, #138/#156)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import INSTALL, LEDGER_LINT, PRECOMPACT


def run_install(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALL), *args],
        capture_output=True, text=True, timeout=15.0,
    )


def _settings(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


class TestPrint:
    def test_print_emits_exact_snippet(self, tmp_path):
        proc = run_install("--print")
        assert proc.returncode == 0, proc.stderr
        snippet = json.loads(proc.stdout)
        hooks = snippet["hooks"]
        assert set(hooks) == {"PreCompact", "PostToolUse"}
        commands = [
            h["command"]
            for groups in hooks.values()
            for group in groups
            for h in group["hooks"]
        ]
        assert any(str(PRECOMPACT) in c for c in commands)
        assert any(str(LEDGER_LINT) in c for c in commands)
        assert hooks["PostToolUse"][0]["matcher"] == "Write|Edit"


class TestApply:
    def test_apply_creates_settings(self, tmp_path):
        settings = _settings(tmp_path)
        proc = run_install("--apply", "--settings", str(settings))
        assert proc.returncode == 0, proc.stderr
        summary = json.loads(proc.stdout)
        assert summary["ok"] is True
        assert summary["changed"] is True
        data = json.loads(settings.read_text())
        assert "PreCompact" in data["hooks"]
        assert "PostToolUse" in data["hooks"]

    def test_apply_is_idempotent(self, tmp_path):
        settings = _settings(tmp_path)
        first = run_install("--apply", "--settings", str(settings))
        assert first.returncode == 0
        content_after_first = settings.read_text()
        second = run_install("--apply", "--settings", str(settings))
        assert second.returncode == 0, second.stderr
        summary = json.loads(second.stdout)
        assert summary["ok"] is True
        assert summary["changed"] is False
        assert settings.read_text() == content_after_first

    def test_apply_makes_timestamped_backup(self, tmp_path):
        settings = _settings(tmp_path)
        original = {"model": "opus", "hooks": {"SessionStart": [
            {"matcher": "", "hooks": [{"type": "command", "command": "echo hi"}]}
        ]}}
        settings.write_text(json.dumps(original), encoding="utf-8")
        proc = run_install("--apply", "--settings", str(settings))
        assert proc.returncode == 0, proc.stderr
        summary = json.loads(proc.stdout)
        backup = Path(summary["backup"])
        assert backup.is_file()
        assert backup.name.startswith("settings.json.bak-")
        assert json.loads(backup.read_text()) == original
        merged = json.loads(settings.read_text())
        assert merged["model"] == "opus"  # unrelated content preserved
        assert "SessionStart" in merged["hooks"]  # unrelated hooks preserved
        assert "PreCompact" in merged["hooks"]

    def test_apply_refuses_to_clobber_without_force(self, tmp_path):
        settings = _settings(tmp_path)
        stale = {"hooks": {"PostToolUse": [
            {"matcher": "Bash", "hooks": [
                {"type": "command",
                 "command": f"python3 {LEDGER_LINT} --old-flag"}]}
        ]}}
        settings.write_text(json.dumps(stale), encoding="utf-8")
        before = settings.read_text()
        proc = run_install("--apply", "--settings", str(settings))
        assert proc.returncode == 2
        summary = json.loads(proc.stdout)
        assert summary["ok"] is False
        assert settings.read_text() == before  # untouched

    def test_apply_force_replaces_stale_entry(self, tmp_path):
        settings = _settings(tmp_path)
        stale = {"hooks": {"PostToolUse": [
            {"matcher": "Bash", "hooks": [
                {"type": "command",
                 "command": f"python3 {LEDGER_LINT} --old-flag"}]}
        ]}}
        settings.write_text(json.dumps(stale), encoding="utf-8")
        proc = run_install("--apply", "--settings", str(settings), "--force")
        assert proc.returncode == 0, proc.stderr
        merged = json.loads(settings.read_text())
        group = merged["hooks"]["PostToolUse"][0]
        assert group["matcher"] == "Write|Edit"
        assert "--old-flag" not in json.dumps(merged)

    def test_apply_invalid_settings_json_refused(self, tmp_path):
        settings = _settings(tmp_path)
        settings.write_text("{ not json", encoding="utf-8")
        before = settings.read_text()
        proc = run_install("--apply", "--settings", str(settings))
        assert proc.returncode == 2
        assert settings.read_text() == before


class TestHardlinkedSettings:
    """#369 — his two config dirs are ONE inode, and `os.replace` splits them.

    `~/.claude/settings.json` and `~/.claude-w/settings.json` are the same
    file (both `256518042`, verified), and this session runs with
    `CLAUDE_CONFIG_DIR=~/.claude-w` while the default target is
    `~/.claude/settings.json`. A rename is the correct write for a file with
    one name and the wrong write for a file with two: it rebinds the name it
    was given to a new inode and leaves the other name on the old one. Exit
    0, a timestamped backup, an idempotent re-run — every visible signal
    still says it worked, and the session it was asked to protect has no
    hooks. That is the silent class exactly, so the assertion has to be about
    the INODE, not about the file it was asked to write.
    """

    @staticmethod
    def _linked_pair(tmp_path: Path) -> tuple[Path, Path]:
        primary = tmp_path / "settings.json"
        primary.write_text(json.dumps({"env": {"KEEP": "1"}}), encoding="utf-8")
        other = tmp_path / "settings-w.json"
        import os
        os.link(primary, other)
        # The precondition IS the test: derive it, never assume the link took.
        assert primary.stat().st_ino == other.stat().st_ino
        assert primary.stat().st_nlink == 2
        return primary, other

    def test_apply_keeps_both_names_on_one_inode(self, tmp_path):
        primary, other = self._linked_pair(tmp_path)
        proc = run_install("--apply", "--settings", str(primary))
        assert proc.returncode == 0, proc.stderr
        assert primary.stat().st_ino == other.stat().st_ino, (
            "the link was broken: the other config dir is still on the old inode"
        )
        assert primary.stat().st_nlink == 2

    def test_apply_gives_the_other_name_the_hooks(self, tmp_path):
        primary, other = self._linked_pair(tmp_path)
        proc = run_install("--apply", "--settings", str(primary))
        assert proc.returncode == 0, proc.stderr
        seen = json.loads(other.read_text(encoding="utf-8"))
        assert "hooks" in seen, "the name that was NOT written has no hooks"
        assert set(seen["hooks"]) == {"PreCompact", "PostToolUse"}
        assert seen["env"] == {"KEEP": "1"}, "pre-existing settings lost"

    def test_apply_reports_the_link_it_preserved(self, tmp_path):
        primary, _ = self._linked_pair(tmp_path)
        proc = run_install("--apply", "--settings", str(primary))
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["hardlinked"] == 2, (
            "a write that trades atomicity for the link must say so"
        )

    def test_apply_leaves_no_tmp_file_behind(self, tmp_path):
        primary, _ = self._linked_pair(tmp_path)
        run_install("--apply", "--settings", str(primary))
        assert not (tmp_path / "settings.json.tmp").exists()

    def test_unlinked_settings_still_report_no_hardlink(self, tmp_path):
        settings = _settings(tmp_path)
        settings.write_text(json.dumps({"env": {"KEEP": "1"}}), encoding="utf-8")
        assert settings.stat().st_nlink == 1
        proc = run_install("--apply", "--settings", str(settings))
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout).get("hardlinked") is None
