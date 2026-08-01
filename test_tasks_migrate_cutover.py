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
    prev_hash = row[0] if row else module.genesis_hash(conn)
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


# ---------------------------------------------------------------------------
# Fixture 5 — Git first-sights match ledger_series (#294 inc 8).
#
# After a cutover, the store's per-bucket arrivals/landings (via
# ledger_parse.store_series_raw → watch.ledger_series store path) must EQUAL
# ledger_series's markdown-mode git-walk over the SAME fixture history —
# bucket for bucket. The events are written by perform_cutover's OWN code
# (first_sight_events over the planted git history), NOT hand-written.
#
# Production line: the ``_populate_events(store.conn, first_sight_events(...))``
# call in ``perform_cutover``. Break by reverting it (no events written) and
# the store path has no arrived/landed → state drops to BURN_NONE and every
# bucket goes to zero — the empty-early-buckets failure that is F3's whole
# point. (A cutover that wrote only current-entry rows + groomed rows, with
# no events, is the gap this increment closes.)
# ---------------------------------------------------------------------------
def test_cutover_first_sights_match_ledger_series(module, tmp_path):
    import os
    import shutil
    import subprocess
    import tempfile
    import watch

    T = 1784900000
    led = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
    entry = "- **#{i}** — task {i} · P2 · task · origin: **human**\n"
    landed_entry = "- **#{i}** — did it · landed `{s}`\n"
    snapshots = [
        # t=0h: #1 #2 arrive (open)
        (led.format(open=entry.format(i=1) + entry.format(i=2), done=""), T),
        # t=1h: #3 arrives, #1 lands
        (led.format(open=entry.format(i=2) + entry.format(i=3),
                    done=landed_entry.format(i=1, s="aaa1111")), T + 3600),
        # t=2h: #2 lands; #4 arrives already-landed (born-landed edge case)
        (led.format(open=entry.format(i=3),
                    done=landed_entry.format(i=1, s="aaa1111")
                    + landed_entry.format(i=2, s="bbb2222")
                    + entry.format(i=4)), T + 7200),
    ]

    def _git_repo(d, snaps):
        dw = os.path.join(d, ".dreamwork")
        os.makedirs(dw, exist_ok=True)
        base = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
        subprocess.run(["git", "-C", d, "init", "-q"], env=base, check=True,
                       capture_output=True)
        for i, (text, when) in enumerate(snaps):
            env = dict(base, GIT_AUTHOR_DATE="@%d +0000" % when,
                       GIT_COMMITTER_DATE="@%d +0000" % when)
            with open(os.path.join(dw, "tasks.md"), "w") as f:
                f.write(text)
            subprocess.run(["git", "-C", d, "add", ".dreamwork/tasks.md"],
                           env=env, check=True, capture_output=True)
            subprocess.run(["git", "-C", d, "commit", "-q", "-m", "s%d" % i],
                           env=env, check=True, capture_output=True)

    watch._LEDGER_SNAPS.clear()
    watch._LEDGER_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        _git_repo(d, snapshots)
        dw = os.path.join(d, ".dreamwork")
        # The on-disk current file needs a Next-id header so the import can
        # seed the id sequence (the git snapshots carry sections only).
        current = snapshots[-1][0]
        full = "# Task ledger\n\nNext id: **5**\n\n" + current
        (Path(dw) / "tasks.md").write_text(full)

        # Markdown-mode result (no watermark yet → git walk).
        md = watch.ledger_series(d, now=T + 7200)
        assert md["state"] == watch.BURN_OK, (
            f"markdown walk must succeed, got {md.get('state')}")

        # Precondition: the fixture yields arrivals AND landings (a fixture
        # with only arrivals makes the landed/bucket assertions vacuous —
        # the hollow-check failure this repo keeps paying for).
        assert md["arrived"] >= 3, (
            f"fixture must yield >=3 arrivals, got {md['arrived']}")
        assert md["landed"] >= 2, (
            f"fixture must yield >=2 landings, got {md['landed']}")
        # Precondition: the early buckets are non-trivial (an all-zero set
        # makes a store-with-no-events pass vacuously — the exact gap).
        early = sum(b["arrived"] for b in md["buckets"][:2])
        assert early > 0, (
            "early buckets must carry arrivals — else the no-events failure "
            "is invisible")

        # Cutover writes rows + first-sight events (from MY code) + watermark.
        module.perform_cutover(dw, out=io.StringIO())

        # Store-mode result (watermark present → store path). Clear caches so
        # the dispatch re-reads source_of_truth.
        watch._LEDGER_CACHE.clear()
        st = watch.ledger_series(d, now=T + 7200)

        assert st["state"] == watch.BURN_OK, (
            f"store series must succeed, got {st.get('state')} "
            f"note={st.get('note')}")
        assert st["arrived"] == md["arrived"], (
            f"arrived: store={st['arrived']} markdown={md['arrived']}")
        assert st["landed"] == md["landed"], (
            f"landed: store={st['landed']} markdown={md['landed']}")
        assert st["open"] == md["open"], (
            f"open: store={st['open']} markdown={md['open']}")
        assert len(st["buckets"]) == len(md["buckets"]), (
            f"bucket count: store={len(st['buckets'])} "
            f"markdown={len(md['buckets'])}")
        for i, (sb, mb) in enumerate(zip(st["buckets"], md["buckets"])):
            assert sb["arrived"] == mb["arrived"], (
                f"bucket {i} arrived: store={sb['arrived']} "
                f"markdown={mb['arrived']}")
            assert sb["landed"] == mb["landed"], (
                f"bucket {i} landed: store={sb['landed']} "
                f"markdown={mb['landed']}")
            assert sb["open"] == mb["open"], (
                f"bucket {i} open: store={sb['open']} "
                f"markdown={mb['open']}")
