"""ud-dw-tasks-migrate --import-history / R3 — #294 increment 5, the
git-history synthetic-event import.

R3 walks the git history of `.dreamwork/tasks.md` and recovers, for each
"groomed" id (a bold `**#N**` span in landed prose with no entry head in
the current file), its entry body at the last commit it had one, plus the
first-sight / landed metadata. The recovered rows are written with
synthetic `task_event` rows attributed `actor='migration:git'` (R3 ruling:
never to the human or the loop), hash-chained per the journal contract.

Every expectation is DERIVED from a synthetic history the test builds, so
a recovery that returns nothing cannot pass (the hollow-check failure).
"""

import hashlib
import importlib.machinery
import importlib.util
import io
from pathlib import Path

import pytest

import ledger_parse
import lint

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
# Synthetic history. #5 and #7 are born open, land, then get groomed into
# #9's landed prose. #6 is born as a bare span in that prose and NEVER has
# an entry head — the unrecoverable case. The CURRENT file (last snapshot)
# has #5/#6/#7 as bold spans with no head, so they parse as groomed ids.
# ---------------------------------------------------------------------------
def _snap(sha, epoch, next_id, open_ids, landed_ids=()):
    """Build a minimal ledger snapshot at one commit."""
    parts = ["# Task ledger\n", f"\nNext id: **{next_id}**\n", "\n## Open\n"]
    for line in open_ids:
        parts.append("\n" + line + "\n")
    parts.append("\n## Recently landed\n")
    for line in landed_ids:
        parts.append("\n" + line + "\n")
    return (sha, epoch, "".join(parts))


FIVE_V1 = "- **#5** — five v1 · P2 · task · origin: **human**"
FIVE_V2 = "- **#5** — five v2 UPDATED · P2 · task · origin: **human**"
SEVEN = "- **#7** — seven · P2 · bug · origin: **loop**"
EIGHT = "- **#8** — eight · P1 · task · origin: **human**"
NINE = "- **#9** — nine cites **#5** and **#6** and **#7** · P1 · task · origin: **human**"

CURRENT = _snap("ccccccc", 4000, 10, [EIGHT], [NINE])
SNAPSHOTS = [
    _snap("aaaaaaa", 1000, 8, [FIVE_V1, EIGHT]),
    _snap("bbbbbbb", 2000, 9, [FIVE_V2, SEVEN, EIGHT]),
    _snap("bbbbbb2", 3000, 10, [EIGHT], [FIVE_V2, SEVEN]),
    CURRENT,
]


def _analysis(module, text):
    return module.build_analysis(text, ledger_path="synthetic.md")


def _groomed(a):
    return {c["id"] for c in a["conflicts"].get("section id without an entry", [])}


# ---------------------------------------------------------------------------
# Recovery — bodies + first-sight / landed metadata.
# ---------------------------------------------------------------------------
def _last_head_body(target):
    """The ledger_parse body of `target` at its last-headed snapshot (raw,
    including the trailing newline ledger_parse keeps — same bytes the
    verbatim import stores, so the digest matches)."""
    want = None
    for _, _, text in SNAPSHOTS:
        heads = {i: b for ids, b in ledger_parse.ledger_entries(text) for i in ids}
        if target in heads:
            want = heads[target]
    return want


def test_recover_extracts_last_verbatim_body(module):
    a = _analysis(module, CURRENT[2])
    assert _groomed(a) == {5, 6, 7}, "fixture lost its groomed shape"
    r = module.recover_groomed_history(a, SNAPSHOTS)
    assert set(r["tasks"]) == {5, 7}, "recoverable ids wrong"
    assert r["tasks"][5]["body"] == _last_head_body(5), "must be the LAST verbatim body"
    assert r["tasks"][5]["state"] == "landed"
    assert r["tasks"][7]["body"] == _last_head_body(7)


def test_recover_marks_unrecoverable_when_no_head_ever(module):
    a = _analysis(module, CURRENT[2])
    r = module.recover_groomed_history(a, SNAPSHOTS)
    assert r["unrecoverable"] == {6}, "#6 never had a head — must be unrecoverable"
    assert 6 not in r["tasks"], "an id with no body must get no row"


def test_recover_events_are_migration_git_with_lifecycle(module):
    a = _analysis(module, CURRENT[2])
    r = module.recover_groomed_history(a, SNAPSHOTS)
    ev = {(e["task_id"], e["from_state"], e["to_state"]) for e in r["events"]}
    assert (5, None, "open") in ev and (5, "open", "landed") in ev, "#5 lifecycle"
    assert (7, None, "open") in ev and (7, "open", "landed") in ev, "#7 lifecycle"
    assert all(e["actor"] == "migration:git" for e in r["events"]), "R3 actor ruling"
    assert all(e["cause"] == "migration_git" for e in r["events"]), "R3 cause"


# ---------------------------------------------------------------------------
# first_sight_events — #294 inc 8: ALL ids, not just groomed.
#
# Production line: the ``oids | lids`` arrival set in ``first_sight_events``.
# Break by looping over ``groomed`` instead and the current-entry ids (#8 #9)
# lose their events — the exact coverage gap (groomed-only → empty burndown
# for current-entry tasks). The contrast with recover_groomed_history is the
# guard: groomed recovery yields events for {5, 7}; first_sight_events must
# yield events for {5, 7, 8, 9} — every id the markdown walk counts.
# ---------------------------------------------------------------------------
def test_first_sight_events_cover_all_ids_not_just_groomed(module):
    a = _analysis(module, CURRENT[2])
    groomed = _groomed(a)
    # Precondition: the fixture has BOTH groomed ids AND current-entry ids.
    # recover_groomed_history owns the groomed set; first_sight_events must
    # cover it PLUS the current-entry ids (8 open, 9 landed). A fixture that
    # lost either side makes the coverage check vacuous.
    assert groomed == {5, 6, 7}, "fixture lost its groomed shape"
    cur = set(a["open_ids"]) | set(a["landed_ids"])  # 8, 9
    assert cur, "fixture lost its current-entry ids"
    rec_events = module.recover_groomed_history(a, SNAPSHOTS)["events"]
    rec_ids = {e["task_id"] for e in rec_events}
    assert rec_ids == {5, 7}, "precondition: groomed recovery covers only 5, 7"
    fs_events = module.first_sight_events(a, SNAPSHOTS)
    fs_ids = {e["task_id"] for e in fs_events}
    # first_sight_events must cover groomed-AND-current-entry ids — the gap.
    assert cur <= fs_ids, (
        f"current-entry ids {cur - fs_ids} missing — first_sight_events "
        "regressed to groomed-only (the burndown gap this increment closes)")
    # #6 appears as a bold span in #9's landed body, so parse_ledger counts
    # it in the landed section and the markdown walk counts it too — so
    # first_sight_events emits for it (matching the markdown model). It has
    # no task row (unrecoverable), so _populate_events's FK-safe filter
    # drops it at write time; that filtering is tested separately.
    assert fs_ids == {5, 6, 7, 8, 9}, (
        f"first-sight ids wrong: {sorted(fs_ids)}; must cover every id "
        "parse_ledger counts in a section (the markdown walk's model)")


def test_first_sight_events_match_markdown_first_sight_model(module):
    """first_sight_events' arrived/landed epochs must equal what the markdown
    git-walk (watch.ledger_series) would derive from the same snapshots —
    the model store_series_raw replays."""
    import watch as _watch
    a = _analysis(module, CURRENT[2])
    events = module.first_sight_events(a, SNAPSHOTS)
    arrived = {e["task_id"]: int(
        __import__("datetime").datetime.fromisoformat(e["at"]).timestamp())
        for e in events if e["from_state"] is None and e["to_state"] == "open"}
    landed = {e["task_id"]: int(
        __import__("datetime").datetime.fromisoformat(e["at"]).timestamp())
        for e in events if e["to_state"] == "landed"}
    # The markdown walk's first-sight model over the same snapshots.
    md_arr, md_land = {}, {}
    for _sha, epoch, text in SNAPSHOTS:
        o, done = _watch.parse_ledger(text)
        for i in o | done:
            md_arr.setdefault(int(i), epoch)
        for i in done:
            md_land.setdefault(int(i), epoch)
    assert arrived == md_arr, (
        f"arrived epochs diverge from markdown: {arrived} vs {md_arr}")
    assert landed == md_land, (
        f"landed epochs diverge from markdown: {landed} vs {md_land}")


# ---------------------------------------------------------------------------
# Hash chain — the journal contract, applied to task_event (DOMAIN_TAG).
# ---------------------------------------------------------------------------
def test_event_chain_links_and_verifies(module):
    a = _analysis(module, CURRENT[2])
    r = module.recover_groomed_history(a, SNAPSHOTS)
    chained = module.chain_events(r["events"])
    assert len(chained) == len(r["events"])
    prev = module.genesis_hash()
    for e in chained:
        assert e["prev_hash"] == prev, "prev_hash must link to the running head"
        assert e["hash"] == module.hash_event(prev, module.canonical_event_bytes(e)), \
            "hash must recompute from prev + canonical bytes"
        prev = e["hash"]


def test_chain_prev_hash_term_is_load_bearing(module):
    """Swapping a prior event's detail must move every later hash (B3)."""
    a = _analysis(module, CURRENT[2])
    r = module.recover_groomed_history(a, SNAPSHOTS)
    base = module.chain_events(r["events"])
    tampered = list(r["events"])
    tampered[0] = dict(tampered[0], detail=tampered[0]["detail"] + " X")
    other = module.chain_events(tampered)
    assert base[0]["hash"] != other[0]["hash"], "detail change must move hash 0"
    assert base[-1]["hash"] != other[-1]["hash"], "a later hash must move too"


# ---------------------------------------------------------------------------
# Import-history — scratch DB, synthetic events, idempotent, refused in
# .dreamwork/. Tested at the function level with synthetic snapshots.
# ---------------------------------------------------------------------------
import sqlite3
from test_tasks_migrate_import import _scratch, _import


def _hist(module, text, snapshots, db):
    a = module.build_analysis(text, ledger_path="synthetic.md")
    return module.import_history_into_db(text, a, db, snapshots)


def _full(module, text, snapshots, db):
    """The real workflow: verbatim import, then history import."""
    assert _import(module, text, db) == 0
    _hist(module, text, snapshots, db)


def _ro(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def test_import_history_inserts_rows_and_events(module, tmp_path):
    a = _analysis(module, CURRENT[2])
    rec = module.recover_groomed_history(a, SNAPSHOTS)
    assert rec["tasks"], "fixture lost recoverable ids"
    db = _scratch(tmp_path)
    res = _hist(module, CURRENT[2], SNAPSHOTS, db)
    conn = _ro(db)
    rows = {r["id"] for r in conn.execute("SELECT id FROM task")}
    assert rows == set(rec["tasks"]), "only recovered ids get rows"
    for i in rec["tasks"]:
        r = conn.execute("SELECT body, body_digest, source_line FROM task WHERE id=?",
                         (i,)).fetchone()
        assert r["body"] == rec["tasks"][i]["body"], f"#{i} body not verbatim"
        assert r["body_digest"] == rec["tasks"][i]["body_digest"]
        assert r["source_line"] is None, "history rows have no line in the current ledger"
    ev = conn.execute("SELECT actor, cause FROM task_event").fetchall()
    assert len(ev) == len(rec["events"])
    assert all(r["actor"] == "migration:git" and r["cause"] == "migration_git" for r in ev)
    assert res["recovered"] == len(rec["tasks"])
    assert res["unrecoverable"] == [6]


def test_import_history_chain_validates_against_recompute(module, tmp_path):
    db = _scratch(tmp_path)
    _hist(module, CURRENT[2], SNAPSHOTS, db)
    ev = _ro(db).execute("SELECT * FROM task_event ORDER BY ordinal").fetchall()
    assert ev, "no events imported"
    prev = module.genesis_hash()
    for r in ev:
        d = dict(r)
        assert r["prev_hash"] == prev, "stored prev_hash must link the running head"
        assert r["hash"] == module.hash_event(prev, module.canonical_event_bytes(d)), \
            "stored hash must recompute from prev + canonical bytes"
        prev = r["hash"]


def test_import_history_is_idempotent(module, tmp_path):
    db = _scratch(tmp_path)
    r1 = _hist(module, CURRENT[2], SNAPSHOTS, db)
    assert r1["events"] > 0 and r1["recovered"] > 0
    assert r1["populated"] is True, "first import must report it populated"
    r2 = _hist(module, CURRENT[2], SNAPSHOTS, db)
    assert r2["populated"] is False, "second import must be a true no-op"
    conn = _ro(db)
    assert conn.execute("SELECT COUNT(*) FROM task_event").fetchone()[0] == r1["events"]
    assert conn.execute("SELECT COUNT(*) FROM task").fetchone()[0] == r1["task_rows"]
    assert r2["events"] == r1["events"]


def test_populate_events_filters_rowless_ids(module, tmp_path):
    """_populate_events is FK-safe: an id visible in history as a bold span
    but with no task row (unrecoverable groomed #6) gets NO event — honesty
    over completeness, and task_event.task_id REFERENCES task(id).

    Production line: the ``have_ids`` filter in ``_populate_events``. Break
    by removing it and writing #6's event fails the FK (IntegrityError)."""
    import ledger_store
    a = _analysis(module, CURRENT[2])
    db = _scratch(tmp_path)
    # Import current-entry rows only (8, 9) — NOT the history (no groomed
    # rows yet). #6 has no row and never will (unrecoverable).
    assert _import(module, CURRENT[2], db) == 0
    store = ledger_store.open_store(db)
    try:
        events = module.first_sight_events(a, SNAPSHOTS)
        fs_ids = {e["task_id"] for e in events}
        # Precondition: first_sight_events DOES emit for #6 (it's a bold
        # span parse_ledger counts), so the filter has something to drop.
        assert 6 in fs_ids, (
            "precondition: #6 must be in first_sight_events (bold span) "
            "— else the filter has nothing to filter")
        have_ids = {r[0] for r in
                    store.conn.execute("SELECT id FROM task")}
        assert 6 not in have_ids, (
            "precondition: #6 must have no row — else the FK test is moot")
        store.conn.execute("BEGIN IMMEDIATE")
        n = module._populate_events(store.conn, events)
        store.conn.execute("COMMIT")
    finally:
        store.close()
    conn = _ro(db)
    written = {r["task_id"] for r in conn.execute("SELECT task_id FROM task_event")}
    # Every written event has a row (FK-safe); #6 was filtered out.
    assert 6 not in written, (
        "#6 (no row) must NOT get an event — FK-safe honesty filter failed")
    assert written <= have_ids, "an event was written for a rowless id"


def test_import_history_refuses_dreamwork_target(module, tmp_path):
    db = str(tmp_path / ".dreamwork" / "h.sqlite3")
    with pytest.raises(Exception) as ei:
        module.import_history_into_db(CURRENT[2], _analysis(module, CURRENT[2]),
                                      db, SNAPSHOTS)
    assert getattr(ei.value, "code", None) == 77
    assert not Path(db).exists()


# ---------------------------------------------------------------------------
# Verify-history — post-R3 consistency. A groomed row must be backed by
# migration:git events (else fabrication); the chain must recompute; backed
# rows must match the recovered body. Each MUST fail verification naming it.
# ---------------------------------------------------------------------------
def _tamper(db, sql, params=()):
    c = sqlite3.connect(db)
    c.execute(sql, params)
    c.commit()
    c.close()


def _verifyf(module, text, db):
    a = module.build_analysis(text, ledger_path="synthetic.md")
    return module.verify_db(text, a, db, snapshots_fn=lambda: SNAPSHOTS)


def test_verify_clean_history_db_passes(module, tmp_path):
    db = _scratch(tmp_path)
    _full(module, CURRENT[2], SNAPSHOTS, db)
    assert _verifyf(module, CURRENT[2], db) == [], "a clean history import verifies"


def test_verify_history_row_without_events_is_fabrication(module, tmp_path):
    db = _scratch(tmp_path)
    _full(module, CURRENT[2], SNAPSHOTS, db)
    # keep #5's row, strip its events -> the pre-R3 fabrication shape
    _tamper(db, "DELETE FROM task_event WHERE task_id = 5")
    fails = _verifyf(module, CURRENT[2], db)
    assert any("#5" in f and "groomed id has a row" in f for f in fails), fails


def test_verify_history_chain_tamper_fails(module, tmp_path):
    db = _scratch(tmp_path)
    _full(module, CURRENT[2], SNAPSHOTS, db)
    _tamper(db, "UPDATE task_event SET detail = detail || ' X' "
                "WHERE ordinal = (SELECT MIN(ordinal) FROM task_event)")
    fails = _verifyf(module, CURRENT[2], db)
    assert any("hash does not recompute" in f or "prev_hash breaks" in f
               for f in fails), fails


def test_verify_history_body_tamper_fails(module, tmp_path):
    db = _scratch(tmp_path)
    _full(module, CURRENT[2], SNAPSHOTS, db)
    _tamper(db, "UPDATE task SET body = body || 'x' WHERE id = 5")
    fails = _verifyf(module, CURRENT[2], db)
    assert any("#5" in f and "body" in f for f in fails), fails


# ---------------------------------------------------------------------------
# Live-repo acceptance — this repo's REAL tasks.md + REAL git history.
# Everything is derived at runtime: the 74/70/4 figures are snapshots, not
# constants (the precondition rule), so the test asserts the STRUCTURE that
# must hold for any history, not today's numbers.
# ---------------------------------------------------------------------------
# Post-cutover (#294) the parseable ledger is the FROZEN deprecated file, but
# the git history of the real ledger lives on the tasks.md path (678 commits) —
# tasks.md.deprecated has exactly ONE commit (the cutover itself), so a history
# walk from it recovers nothing. History recovery needs BOTH: the frozen text
# for the current analysis AND the rich git history from the tasks.md path
# (the snapshots are byte-identical to the deprecated text up to the cutover;
# the final shim snapshot parses to empty ids and is harmless to the walk).
LIVE_LEDGER = REPO / ".dreamwork" / "tasks.md.deprecated"
LIVE_LEDGER_HISTORY = REPO / ".dreamwork" / "tasks.md"


def test_live_history_recovers_real_groomed_ids(module, tmp_path):
    text = LIVE_LEDGER.read_text()
    # Precondition: the frozen ledger is parseable (not the shim), and the
    # git-history path carries the real multi-commit history the walk needs —
    # a single-commit history (the deprecated file's own) would recover
    # nothing, making every assertion below vacuous.
    assert "## Open" in text, (
        "LIVE_LEDGER must be the frozen ledger, not the shim")
    a = module.build_analysis(text, ledger_path=str(LIVE_LEDGER))
    groomed = {c["id"] for c in
               a["conflicts"].get("section id without an entry", [])}
    assert groomed, "live ledger lost its groomed ids — test has no anchor"
    snaps = module.git_snapshots(str(LIVE_LEDGER_HISTORY))
    assert len(snaps) > 1, (
        "git-history path lost its real history — recovery has nothing to walk")
    rec = module.recover_groomed_history(a, snaps)
    # every groomed id is recovered OR unrecoverable — no third state
    assert set(rec["tasks"]) | set(rec["unrecoverable"]) == groomed
    assert set(rec["tasks"]).isdisjoint(rec["unrecoverable"])
    assert rec["tasks"], "no recoverable ids — the walk found nothing"
    # every event is synthetic migration:git (R3 ruling: never human/loop)
    assert rec["events"], "recovered ids must yield first-sight events"
    assert all(e["actor"] == "migration:git" and e["cause"] == "migration_git"
               for e in rec["events"])
    # full workflow: verbatim import (frozen ledger) + history (real git
    # history), then verify clean. The CLI's --verify walks git from its
    # --ledger path, but post-cutover that path is split (text on .deprecated,
    # history on tasks.md), so verify the scratch DB directly with the rich
    # snapshots — the full history check (groomed-row body-match against the
    # recovered bytes) runs over the real 678-commit history, not the
    # deprecated file's single commit (which would skip body-match as vacuous).
    db = _scratch(tmp_path)
    assert module.main(["--import", "--ledger", str(LIVE_LEDGER), "--to", db],
                       out=io.StringIO()) == 0
    module.import_history_into_db(text, a, db, snaps)
    fails = module.verify_db(text, a, db, snapshots_fn=lambda: snaps)
    assert not fails, fails
    conn = _ro(db)
    for i in rec["tasks"]:
        assert conn.execute("SELECT 1 FROM task WHERE id = ?", (i,)).fetchone(), \
            f"#{i} recovered but has no row"
        n = conn.execute(
            "SELECT COUNT(*) FROM task_event WHERE task_id = ? "
            "AND actor = 'migration:git'", (i,)).fetchone()[0]
        assert n >= 1, f"#{i} row has no migration:git backing event"
    for i in rec["unrecoverable"]:
        assert not conn.execute("SELECT 1 FROM task WHERE id = ?",
                                (i,)).fetchone(), \
            f"#{i} unrecoverable but has a row — fabrication"



