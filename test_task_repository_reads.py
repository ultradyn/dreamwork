"""Frozen pre-repository captures for #645 increment 3 task-store reads."""

from __future__ import annotations

from pathlib import Path

from dev import ledger as dev_ledger
import ledger_parse
import ledger_store
import task_origins


CAPTURED_BEFORE_MOVE = {
    "meta_value": "fixture-cutover",
    "entries": [
        ([1], "- **#1** — Alpha · P1 · task · origin: **human**\n  headed body"),
        ([2], "- **#2** — Beta · origin: **unknown** ·\nheadless note"),
        ([3], "- **#3** — Gamma · P2 · bug · origin: **loop** ·\nheadless third"),
    ],
    "records": [
        {"id": 1, "state": "open", "title": "Alpha",
         "body": "- **#1** — Alpha · P1 · task · origin: **human**\n  headed body",
         "priority": "P1", "type": "task", "origin": "human",
         "blocked_on": None},
        {"id": 2, "state": "landed", "title": "Beta",
         "body": "headless note", "priority": None, "type": None,
         "origin": None, "blocked_on": "task #1"},
        {"id": 3, "state": "open", "title": "Gamma",
         "body": "headless third", "priority": "P2", "type": "bug",
         "origin": "loop", "blocked_on": None},
    ],
    "ids_by_state": (["1", "3"], ["2"]),
    "review_decisions": [
        {"artifact": "a.html", "question_title": "Question A",
         "decision": "pending", "decided_at": "2026-01-01T00:00:00+00:00",
         "actor": "fixture"},
        {"artifact": "z.html", "question_title": "Question Z",
         "decision": "accepted", "decided_at": "2026-01-04T00:00:00+00:00",
         "actor": "fixture"},
    ],
    "series_raw": {
        "arrived": {"1": 1767225600, "2": 1767312000},
        "landed": {"2": 1767398400},
        "first_sight": {"1": "human", "2": "unknown", "3": "loop"},
        "latest_open": {"1", "3"},
        "commit_times": [1767225600, 1767312000, 1767398400],
    },
    "origins": [
        {"id": 1, "origin": "human", "first_commit": "abcdef1",
         "first_seen": 1767225600, "title": ""},
        {"id": 2, "origin": "unknown", "first_commit": "bbbbbbb",
         "first_seen": 1767312000, "title": ""},
        {"id": 3, "origin": "loop", "first_commit": "deadbee",
         "first_seen": 0, "title": ""},
    ],
    "incomplete_counts": (1, 1),
}


def _fixture_store(tmp_path: Path) -> Path:
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    db = dw / ledger_parse.STORE_FILENAME
    store = ledger_store.open_store(str(db), seed_next_id=4)
    try:
        conn = store.conn
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany("INSERT INTO task_type(type) VALUES (?)",
                         [("task",), ("bug",)])
        conn.executemany(
            "INSERT INTO task(id,state,title,body,priority,type,origin,blocked_on)"
            " VALUES (?,?,?,?,?,?,?,?)",
            [
                (1, "open", "Alpha",
                 "- **#1** — Alpha · P1 · task · origin: **human**\n  headed body",
                 "P1", "task", "human", None),
                (2, "landed", "Beta", "headless note", None, None, None,
                 "task #1"),
                (3, "open", "Gamma", "headless third", "P2", "bug", "loop", None),
            ],
        )
        events = [
            (1, "2026-01-01T00:00:00+00:00", None, "open", "migration (abcdef1)"),
            (2, "2026-01-02T00:00:00+00:00", None, "open", "migration (bbbbbbb)"),
            (2, "2026-01-03T00:00:00+00:00", "open", "landed", "landed"),
            (3, "not-a-date", None, "open", "migration (deadbee)"),
        ]
        for n, (task_id, at, from_state, to_state, detail) in enumerate(events, 1):
            conn.execute(
                "INSERT INTO task_event(task_id,at,cause,from_state,to_state,actor,"
                "detail,prev_hash,hash) VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, at, "migration_git", from_state, to_state, "fixture",
                 detail, f"prev-{n}", f"hash-{n}"),
            )
        conn.executemany(
            "INSERT INTO review_decision(artifact,question_title,decision,decided_at,actor)"
            " VALUES (?,?,?,?,?)",
            [
                ("z.html", "Question Z", "accepted", "2026-01-04T00:00:00+00:00", "fixture"),
                ("a.html", "Question A", "pending", "2026-01-01T00:00:00+00:00", "fixture"),
            ],
        )
        conn.execute("INSERT INTO meta(key,value) VALUES (?,?)",
                     ("ledger_cut_over", "fixture-cutover"))
        conn.execute("COMMIT")
    finally:
        store.close()
    return dw


def _read_all(dw: Path) -> dict:
    return {
        "meta_value": ledger_parse._read_meta_value(
            ledger_parse.store_path(dw), "ledger_cut_over"),
        "entries": ledger_parse.store_entries(dw),
        "records": ledger_parse.store_records(dw),
        "ids_by_state": ledger_parse.store_ids_by_state(dw),
        "review_decisions": ledger_parse.store_review_decisions(dw),
        "series_raw": ledger_parse.store_series_raw(dw),
        "origins": task_origins._store_origins(dw),
        "incomplete_counts": dev_ledger._store_incomplete_counts(dw),
    }


def test_all_eight_task_store_reads_match_the_nontrivial_pre_move_capture(tmp_path):
    actual = _read_all(_fixture_store(tmp_path))
    assert len(actual) == 8, f"read denominator changed: captured 8, got {len(actual)}"
    for name, expected in CAPTURED_BEFORE_MOVE.items():
        value = actual[name]
        assert value not in (None, [], (), {}), f"{name} capture is vacuous: {value!r}"
        assert value == expected, (
            f"{name} parity differs:\nexpected rows={expected!r}\nactual rows={value!r}"
        )
