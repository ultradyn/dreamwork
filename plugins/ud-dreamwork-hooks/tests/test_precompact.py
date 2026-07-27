"""PreCompact preservation-focus hook tests (red-first, #138/#156)."""
from __future__ import annotations

import json
from pathlib import Path

from conftest import (
    PRECOMPACT, assert_contract, make_target, precompact_payload, run_script,
)


def _cfg_env(tmp_path: Path) -> dict:
    return {"DREAMWORK_HOOKS_CONFIG": str(tmp_path / "cfg")}


def _read_records(cfg_root: Path) -> list[dict]:
    files = list(cfg_root.rglob("precompact-focus.jsonl"))
    assert len(files) == 1, f"expected one focus log, got {files}"
    return [json.loads(ln) for ln in files[0].read_text().splitlines() if ln.strip()]


class TestPreCompactFocus:
    def test_manual_trigger_writes_focus(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "#138 hooks plugin"})
        proc = run_script(PRECOMPACT, precompact_payload(target, "manual"),
                          env_extra=_cfg_env(tmp_path))
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out["hook"] == "precompact-focus"
        records = _read_records(tmp_path / "cfg")
        assert len(records) == 1
        rec = records[0]
        assert rec["trigger"] == "manual"
        assert rec["current_task"] == "#138 hooks plugin"
        assert rec["open_questions"] == 2
        assert rec["session_id"] == "sess-test"

    def test_auto_trigger_writes_focus(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "auto run"})
        proc = run_script(PRECOMPACT, precompact_payload(target, "auto"),
                          env_extra=_cfg_env(tmp_path))
        out = assert_contract(proc)
        assert out["ok"] is True
        records = _read_records(tmp_path / "cfg")
        assert records[0]["trigger"] == "auto"

    def test_appends_across_invocations(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "t"})
        env = _cfg_env(tmp_path)
        for trigger in ("manual", "auto", "manual"):
            run_script(PRECOMPACT, precompact_payload(target, trigger), env_extra=env)
        assert len(_read_records(tmp_path / "cfg")) == 3

    def test_missing_status_json_still_ok_with_note(self, tmp_path):
        target = make_target(tmp_path, status=None)
        proc = run_script(PRECOMPACT, precompact_payload(target),
                          env_extra=_cfg_env(tmp_path))
        out = assert_contract(proc)
        assert out["ok"] is True
        assert "note" in out
        rec = _read_records(tmp_path / "cfg")[0]
        assert rec["current_task"] is None
        assert rec["open_questions"] == 2
        assert rec["note"]

    def test_malformed_status_json_noted_not_fatal(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "x"})
        (target / ".dreamwork" / "status.json").write_text("{not json", encoding="utf-8")
        proc = run_script(PRECOMPACT, precompact_payload(target),
                          env_extra=_cfg_env(tmp_path))
        out = assert_contract(proc)
        assert out["ok"] is True
        rec = _read_records(tmp_path / "cfg")[0]
        assert rec["current_task"] is None
        assert "unreadable" in rec["note"]

    def test_unavailable_target_reports_error_and_writes_nothing(self, tmp_path):
        bare = tmp_path / "bare"
        bare.mkdir()
        proc = run_script(PRECOMPACT, precompact_payload(bare),
                          env_extra=_cfg_env(tmp_path))
        out = assert_contract(proc)
        assert out["ok"] is False
        assert "error" in out
        assert not (tmp_path / "cfg").exists()

    def test_plugin_not_loaded_skips(self, tmp_path):
        target = make_target(tmp_path, load_line=False,
                             status={"current_task": "t"})
        proc = run_script(PRECOMPACT, precompact_payload(target),
                          env_extra=_cfg_env(tmp_path))
        out = assert_contract(proc)
        assert out["ok"] is True
        assert out.get("skipped") is True
        assert not (tmp_path / "cfg").exists()

    def test_garbage_stdin_still_exits_zero(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "t"})
        proc = run_script(PRECOMPACT, "this is not json {",
                          env_extra=_cfg_env(tmp_path), cwd=target)
        out = assert_contract(proc)
        assert out["ok"] is True  # falls back to cwd, still a loaded target

    def test_focus_record_is_bounded(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "x" * 5000})
        proc = run_script(PRECOMPACT, precompact_payload(target),
                          env_extra=_cfg_env(tmp_path))
        assert_contract(proc)
        rec = _read_records(tmp_path / "cfg")[0]
        assert len(rec["current_task"]) <= 200
        assert len(json.dumps(rec)) <= 2000

    def test_log_rotation_is_bounded(self, tmp_path):
        target = make_target(tmp_path, status={"current_task": "t"})
        env = _cfg_env(tmp_path)
        # Seed an over-long log, then run once: it must trim, not grow forever.
        run_script(PRECOMPACT, precompact_payload(target), env_extra=env)
        log = next((tmp_path / "cfg").rglob("precompact-focus.jsonl"))
        log.write_text("\n".join(json.dumps({"i": i}) for i in range(500)) + "\n")
        run_script(PRECOMPACT, precompact_payload(target), env_extra=env)
        lines = log.read_text().splitlines()
        assert len(lines) <= 201, f"log grew unbounded: {len(lines)} lines"
