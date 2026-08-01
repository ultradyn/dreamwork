"""Frozen pre-repository captures for #645 increment 3 task-store reads."""

from __future__ import annotations

from pathlib import Path

from dev import ledger as dev_ledger
import ledger_parse
import ledger_store
import task_origins


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
        next_up_events = [
            (1, "next_up_set", "mark Alpha"),
            (2, "next_up_set", "landed tasks cannot remain next-up"),
            (3, "next_up_set", "mark Gamma"),
            (3, "next_up_cleared", "start Gamma"),
        ]
        for n, (task_id, cause, detail) in enumerate(next_up_events, 5):
            conn.execute(
                "INSERT INTO task_event(task_id,at,cause,from_state,to_state,actor,"
                "detail,prev_hash,hash) VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, f"zz-next-up-{n}", cause, "open", "open",
                 "fixture", detail, f"prev-{n}", f"hash-{n}"),
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


def test_all_eight_task_store_reads_preserve_their_behaviours(tmp_path):
    actual = _read_all(_fixture_store(tmp_path))
    assert len(actual) == 8, f"read denominator changed: expected 8, got {len(actual)}"

    assert actual["meta_value"] == "fixture-cutover"
    assert actual["entries"] == [
        ([1], "- **#1** — Alpha · P1 · task · origin: **human**\n  headed body"),
        ([2], "- **#2** — Beta · origin: **unknown** ·\nheadless note"),
        ([3], "- **#3** — Gamma · P2 · bug · origin: **loop** ·\nheadless third"),
    ]

    records = actual["records"]
    assert len(records) == 3, f"record denominator changed: {records!r}"
    stable_fields = [
        (1, "open", "Alpha", "P1", "task", "human", None,
         "2026-01-01T00:00:00+00:00"),
        (2, "landed", "Beta", None, None, None, "task #1",
         "2026-01-02T00:00:00+00:00"),
        (3, "open", "Gamma", "P2", "bug", "loop", None, "not-a-date"),
    ]
    assert [
        (r["id"], r["state"], r["title"], r["priority"], r["type"],
         r["origin"], r["blocked_on"], r["date"])
        for r in records
    ] == stable_fields
    assert [r["body"] for r in records] == [
        "- **#1** — Alpha · P1 · task · origin: **human**\n  headed body",
        "headless note",
        "headless third",
    ]
    assert [r["next_up"] for r in records] == [5, None, None], (
        "the latest next-up event marks open Alpha; landed Beta is excluded; "
        "Gamma's later clear wins"
    )

    assert actual["ids_by_state"] == (["1", "3"], ["2"])
    assert [
        (d["artifact"], d["question_title"], d["decision"], d["decided_at"],
         d["actor"])
        for d in actual["review_decisions"]
    ] == [
        ("a.html", "Question A", "pending", "2026-01-01T00:00:00+00:00",
         "fixture"),
        ("z.html", "Question Z", "accepted", "2026-01-04T00:00:00+00:00",
         "fixture"),
    ]

    series = actual["series_raw"]
    assert series["arrived"] == {"1": 1767225600, "2": 1767312000}
    assert series["landed"] == {"2": 1767398400}
    assert series["first_sight"] == {"1": "human", "2": "unknown", "3": "loop"}
    assert series["latest_open"] == {"1", "3"}
    assert series["commit_times"] == [1767225600, 1767312000, 1767398400]

    assert [
        (r["id"], r["origin"], r["first_commit"], r["first_seen"], r["title"])
        for r in actual["origins"]
    ] == [
        (1, "human", "abcdef1", 1767225600, ""),
        (2, "unknown", "bbbbbbb", 1767312000, ""),
        (3, "loop", "deadbee", 0, ""),
    ]
    assert actual["incomplete_counts"] == (1, 1)
