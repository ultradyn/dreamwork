"""Red-first cutover + rollback tests — #294 R4 (the FINAL increment).

Fixtures 6, 8, 9, 10 from the plan's ten red-first acceptance list. Each
names in its docstring the PRODUCTION LINE that must change for it to fail,
derives its preconditions at runtime (never a literal pinned to today's
fixture), and was red-proved: the named line was injected, the test failed,
and the source restored byte-identical (cp backup, never git checkout).

The cutover operates on a scratch --target-dir (never the real .dreamwork/);
the live execution is a separate coordinator act.
"""

import importlib.machinery
import importlib.util
import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ledger_parse
import migration_notice

REPO = Path(__file__).resolve().parent
CLI = REPO / "ud-dw-tasks-migrate"


def _load_cli():
    loader = importlib.machinery.SourceFileLoader("ud_dw_tasks_migrate", str(CLI))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def module():
    return _load_cli()


# ---------------------------------------------------------------------------
# Importable fixture — no fatal conflicts, seed == MAX(id)+1.
# ---------------------------------------------------------------------------
FIXTURE = """# Task ledger

Next id: **12**

## Open

- **#10** — a clean open entry · P1 · task · origin: **human**

## Recently landed

- **#11** — a clean landed entry · P0 · implementation · origin: **human** (abc1234)
"""


def _setup_target(tmp_path, text=FIXTURE):
    """A scratch .dreamwork/-like directory with a valid tasks.md."""
    td = tmp_path / "dw"
    td.mkdir()
    (td / "tasks.md").write_text(text)
    return td


# ---------------------------------------------------------------------------
# Fixture 6 — Cutover freezes writers.
#
# Production line: the ``active = cur_s is not None and cur_s > now_s`` guard
# in ``_acquire_cutover_lease``. Break by setting ``active = False`` and the
# second writer acquires the lease — the mixed-writer hazard.
# ---------------------------------------------------------------------------
def test_cutover_freezes_writers_second_acquire_fails(module, tmp_path):
    td = _setup_target(tmp_path)
    module.perform_cutover(str(td), out=io.StringIO())

    store_db = str(td / ledger_parse.STORE_FILENAME)
    store = module.ledger_store.open_store(store_db)
    try:
        module._acquire_cutover_lease(store.conn, "first", 300)

        # Precondition: the lease is actually active (lease_until > now).
        lease_row = store.conn.execute(
            "SELECT value FROM meta WHERE key = 'cutover_lease_until'"
        ).fetchone()
        assert lease_row is not None, "lease not written — test has no anchor"
        now_s = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        assert lease_row[0] > now_s, (
            "lease is not active — the freeze has nothing to freeze")

        # A second writer under the same lease must fail closed (CutoverBusy).
        with pytest.raises(module.CutoverBusy):
            module._acquire_cutover_lease(store.conn, "second", 300)
    finally:
        module._release_cutover_lease(store.conn)
        store.close()


# ---------------------------------------------------------------------------
# Fixture 8 — A stale agent self-heals.
#
# Production line: ``_write_shim(tasks_path)`` in ``perform_cutover``. Break
# by not writing the shim and a stale agent reading tasks.md finds no notice
# and has no path to the store.
# ---------------------------------------------------------------------------
def test_stale_agent_finds_notice_and_deprecation_after_cutover(module, tmp_path):
    td = _setup_target(tmp_path)
    module.perform_cutover(str(td), out=io.StringIO())

    # A stale agent reads tasks.md — it must find the #458 notice.
    shim_text = (td / "tasks.md").read_text()
    fields = migration_notice.parse_notice(shim_text)
    assert fields is not None, (
        "no #458 notice in the shim — a stale agent has no path to the store")
    assert fields["migration"] == module._NOTICE_MIGRATION

    # The deprecation block names the canonical access + recovery.
    deprecated_text = (td / "tasks.md.deprecated").read_text()
    assert deprecated_text.startswith("---\n"), "no YAML deprecation block"
    assert "deprecated: true" in deprecated_text
    assert "canonical-access:" in deprecated_text
    assert "recovery:" in deprecated_text

    # Precondition: the original content survived verbatim in .deprecated.
    assert "a clean open entry" in deprecated_text, (
        "original content lost — the content he said never to delete is gone")


# ---------------------------------------------------------------------------
# Fixture 9 — Rollback never restores a legacy writer.
#
# Production line: the ``if ledger_parse.is_cut_over(target_dir):`` guard in
# ``guard_markdown_write``. Break by removing it and a direct Markdown
# mutation succeeds, reintroducing the single-writer-by-convention hazard.
# ---------------------------------------------------------------------------
def test_rollback_never_restores_legacy_writer(module, tmp_path):
    td = _setup_target(tmp_path)
    module.perform_cutover(str(td), out=io.StringIO())
    backup = str(td / "migration-backup")

    module.perform_rollback(backup, str(td), out=io.StringIO())

    # Precondition: the store still has the watermark after rollback —
    # rollback re-ran forward and wrote it again.
    assert ledger_parse.is_cut_over(str(td)), (
        "watermark missing after rollback — version gate has nothing to check")

    # A direct Markdown mutation must be refused by the version gate.
    with pytest.raises(module.VersionMismatchError):
        module.guard_markdown_write(str(td))


# ---------------------------------------------------------------------------
# Fixture 10 — The chain verifies over synthetic + live events.
#
# Production line: the ``SELECT * FROM task_event ORDER BY ordinal`` loop in
# ``verify_task_event_chain`` iterates ALL rows regardless of actor. Break by
# adding ``WHERE actor != 'migration:git'`` and a mutated synthetic row passes
# — a silent forgery.
# ---------------------------------------------------------------------------
def test_chain_verifies_over_synthetic_and_live_events(module, tmp_path):
    from test_tasks_migrate_history import SNAPSHOTS, CURRENT
    from test_tasks_migrate_import import _scratch, _import

    db = _scratch(tmp_path)
    _import(module, CURRENT[2], db)
    a = module.build_analysis(CURRENT[2], ledger_path="synthetic.md")
    module.import_history_into_db(CURRENT[2], a, db, SNAPSHOTS)

    # Precondition: there ARE synthetic migration:git events.
    conn = sqlite3.connect(db)
    n_synth = conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE actor = 'migration:git'"
    ).fetchone()[0]
    assert n_synth > 0, (
        "no synthetic events — the chain has nothing synthetic to verify")

    # Append one live event (simulate a filed transition), chained after
    # the synthetic ones so the chain spans both actors.
    row = conn.execute(
        "SELECT hash FROM task_event ORDER BY ordinal DESC LIMIT 1"
    ).fetchone()
    prev_hash = row[0] if row else module.genesis_hash()
    conn.close()

    live = {"task_id": 8, "at": "2026-07-29T10:00:00Z",
            "cause": "filed_from_command", "from_state": None,
            "to_state": "open", "actor": "coordinator",
            "receipt_id": None, "detail": "filed by the coordinator"}
    canonical = module.canonical_event_bytes(live)
    h = module.hash_event(prev_hash, canonical)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO task_event(task_id, at, cause, from_state, to_state,"
        " actor, receipt_id, detail, prev_hash, hash)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (8, live["at"], live["cause"], None, "open", "coordinator",
         None, "filed by the coordinator", prev_hash, h))
    conn.commit()
    conn.close()

    # The chain must verify clean over synthetic + live.
    assert module.verify_task_event_chain(db) == [], (
        "clean chain (synthetic + live) must verify")

    # Mutate a synthetic row — the chain must break.
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE task_event SET detail = detail || ' TAMPERED' "
        "WHERE ordinal = (SELECT MIN(ordinal) FROM task_event "
        "WHERE actor = 'migration:git')")
    conn.commit()
    conn.close()
    fails = module.verify_task_event_chain(db)
    assert fails, (
        "mutated synthetic row must break the chain — "
        "a verifier that exempts migration:git rows is a silent forgery")
