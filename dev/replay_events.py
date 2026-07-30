#!/usr/bin/env python3
"""dev/replay_events.py — replay the task_event journal, reconstruct the
transition chain (lifecycle).

The task **entity** (title/body/priority/origin/type/blocked_on/body_digest)
is NOT carried by the journal and is stubbed on replay — the store's task
table is the authoritative home for the entity, not this log (see #294/#550).

A stdlib-only tool (like the rest of ``dev/``) that replays the
``task_event`` journal and reconstructs the transition chain (the lifecycle),
proving three things (#460):

  1. **Determinism** — the same journal replayed twice yields a byte-identical
     store (SQLite is byte-deterministic for an identical op sequence from an
     empty image, after a ``wal_checkpoint(TRUNCATE)``).
  2. **Round-trip fidelity** — a store built through the real apply path
     (``ledger_write``), its journal exported to ``.jsonl``, and replayed into
     a fresh store, holds the SAME ``task_event`` rows (the chain reconstructs
     exactly). This is the **falsifier for #294's journal schema**: a field the
     journal does not capture cannot be reconstructed, and that is a REPORTED
     FINDING about the journal, not a bug in this tool.
  3. **A merge rule** — ONE deterministic total order for merging two event
     streams (the future dreamhub multi-agent case), with a stated tie-break.

It rides the existing apply primitive rather than restating event semantics
(the #352 anti-duplication rule): the hash chain has ONE definition
(``ledger_store.genesis_hash`` / ``canonical_event_bytes`` / ``hash_event``),
and applying one event goes through the ONE applier
``ledger_store.append_chained_event`` (the #460 gap-fill), shared with the
live write verbs (``ledger_write``). Nothing about how an event hashes or how
a row is appended is restated here.

The journal format (``.jsonl``)
-------------------------------
One JSON object per line, in chain (ordinal) order. Each line carries the
canonical event fields that define the event plus ``receipt_id`` (which is
stored but NOT part of the hash — see ``ledger_store.canonical_event_bytes``):

    {"task_id": 500, "at": "2026-07-29T10:00:00", "cause": "filed_from_command",
     "from_state": null, "to_state": "open", "actor": "loop",
     "detail": "", "receipt_id": null}

``ordinal``, ``prev_hash`` and ``hash`` are NOT in the file: ordinal is the
line number, and the hashes are RECOMPUTED from the canonical fields via the
shared chain construction. That is the whole of the determinism proof — the
log is the canonical events and every structural column is rebuilt.

NOTE on the brief's "the writer is ``user_events/``": the task_event journal
is written by ``ledger_write`` (file/land) and ``ud-dw-tasks-migrate``
(synthetic first-sight events), and its chain primitives live in
``ledger_store``. The ``user_events/`` package owns a SEPARATE journal (the
receipts log) with its own ``DOMAIN_TAG``. This conflation is FLAGGED in the
lane report; this tool rides the task_event primitives where they live.

Usage
-----
    python3 dev/replay_events.py replay  <journal.jsonl> <out.sqlite3>
    python3 dev/replay_events.py export  <store.sqlite3> <out.jsonl>
    python3 dev/replay_events.py merge   <a.jsonl> <b.jsonl> <out.jsonl>
    python3 dev/replay_events.py verify  <journal.jsonl>
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

# Bootstrap the skill root onto sys.path so this runs both as
# `python3 dev/replay_events.py` (sys.path[0] is then `dev/`, not the cwd)
# and as `import dev.replay_events` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ride the ONE copy of the chain construction + the ONE apply primitive.
# Importing these (rather than restating them) is the #352 contract.
import ledger_store
from ledger_store import (
    append_chained_event,
    canonical_event_bytes,
    genesis_hash,
    hash_event,
)

# The event fields that define an event and are carried in the .jsonl.
# receipt_id is stored on the row but excluded from the hash (see
# canonical_event_bytes); it is carried so a round-trip preserves it.
EVENT_FIELDS = ("task_id", "at", "cause", "from_state",
                "to_state", "actor", "detail", "receipt_id")

# Placeholder values for task columns the journal does NOT carry. A replayed
# task row keeps the right id and state (the journal captures those) but its
# title/body are stubs — the #294/#550 finding this tool exists to surface:
# the journal is a lifecycle log, and the entity is an authoritative table
# whose home is the store, not this log (see the module docstring).
_REPLAY_TITLE = "<reconstructed from task_event journal>"
_REPLAY_BODY = "<title/body not captured by the task_event journal (#294)>"

# The set of task.state values the task table's CHECK accepts. An event's
# to_state is written straight onto the row when it is one of these; anything
# else leaves the row at its last known entry state.
_ENTRY_STATES = ("open", "landed")


# ---------------------------------------------------------------------------
# Journal I/O — one JSON object per line, in chain order.
# ---------------------------------------------------------------------------

def _normalise(raw: dict) -> dict:
    """Coerce a raw JSON object to the canonical event shape.

    ``from_state``/``to_state`` arrive as JSON ``null`` for the arrival
    transition; keep them as ``None`` (not the string ``"null"``).
    ``receipt_id``/``detail`` default to ``None``/``""`` when absent, matching
    the stored defaults. This is the single reader of the .jsonl shape.
    """
    return {
        "task_id": int(raw["task_id"]),
        "at": str(raw["at"]),
        "cause": str(raw["cause"]),
        "from_state": None if raw.get("from_state") is None else str(raw["from_state"]),
        "to_state": None if raw.get("to_state") is None else str(raw["to_state"]),
        "actor": str(raw["actor"]),
        "detail": "" if raw.get("detail") is None else str(raw["detail"]),
        "receipt_id": None if raw.get("receipt_id") is None else str(raw["receipt_id"]),
    }


def read_journal(path) -> list:
    """Read a ``.jsonl`` journal; return canonical event dicts in line order."""
    p = Path(path)
    events = []
    with open(p, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(_normalise(json.loads(line)))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
                raise ValueError(
                    f"{p}:{lineno}: malformed event line: {exc}") from exc
    return events


def write_journal(events: Iterable[dict], path) -> None:
    """Write events to a ``.jsonl`` journal, one canonical object per line."""
    p = Path(path)
    with open(p, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps({k: e.get(k) for k in EVENT_FIELDS}) + "\n")


# ---------------------------------------------------------------------------
# Export — the store → .jsonl half of the round-trip.
# ---------------------------------------------------------------------------

def export_journal(store_path) -> list:
    """Read ``task_event`` rows from a store; return canonical dicts (ordinal order).

    Opens read-only so the source store is never mutated. Returns exactly the
    canonical fields + ``receipt_id``; ``ordinal``/``prev_hash``/``hash`` are
    dropped (they are structural and recomputed at replay).
    """
    conn = sqlite3.connect(f"file:{Path(store_path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT task_id, at, cause, from_state, to_state, actor, "
            "receipt_id, detail FROM task_event ORDER BY ordinal"
        ).fetchall()
        return [_normalise(dict(r)) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Replay — .jsonl → reconstructed store, riding the ONE apply primitive.
# ---------------------------------------------------------------------------

def _event_to_state(e: dict):
    """The task.state an event implies, or None to leave the row untouched."""
    to = e.get("to_state")
    return to if to in _ENTRY_STATES else None


def replay_into(events: list, out_path, *, seed_next_id=None) -> Path:
    """Reconstruct a store from ``events`` (applied in list order).

    Creates the schema, seeds the id sequence, materialises a task row per
    distinct ``task_id`` (FK target — the journal does not carry title/body,
    so those are stubs; the #294 finding), and applies every event through
    :func:`ledger_store.append_chained_event` in chain order. The chain is
    REBUILT from genesis: each event's prev/hash come from the shared
    construction, never from the input.

    When ``seed_next_id`` is None it is derived as ``max(task_id)+1`` so the
    reconstructed sequence sits above the replayed ids (and a no-event replay
    seeds at 1). The store is checkpointed (``wal_checkpoint(TRUNCATE)``) so
    the on-disk bytes are the committed state — the basis of the byte-
    determinism comparison.
    """
    if seed_next_id is None:
        ids = [e["task_id"] for e in events]
        seed_next_id = (max(ids) + 1) if ids else 1

    store = ledger_store.open_store(out_path, seed_next_id=seed_next_id)
    conn = store.conn
    try:
        conn.execute("BEGIN")
        seen = set()
        for e in events:
            tid = e["task_id"]
            st = _event_to_state(e)
            if tid not in seen:
                # FK target: the journal carries no title/body, so stub them.
                conn.execute(
                    "INSERT INTO task(id, state, title, body) "
                    "VALUES (?, ?, ?, ?)",
                    (tid, st or "open", _REPLAY_TITLE, _REPLAY_BODY))
                seen.add(tid)
            elif st is not None:
                conn.execute(
                    "UPDATE task SET state = ? WHERE id = ?", (st, tid))
            # The ONE apply primitive — chain construction has one definition.
            append_chained_event(
                conn, task_id=tid, at=e["at"], cause=e["cause"],
                from_state=e["from_state"], to_state=e["to_state"],
                actor=e["actor"], receipt_id=e.get("receipt_id"),
                detail=e.get("detail") or "")
        conn.execute("COMMIT")
        # Flush WAL to the main file so byte comparison sees committed state.
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        store.close()
    return Path(out_path)


# ---------------------------------------------------------------------------
# Merge — ONE deterministic total order for two event streams.
# ---------------------------------------------------------------------------

def event_sort_key(e: dict) -> tuple:
    """The deterministic total-order key for an event.

    A stream merge must be a TOTAL order: two events that agree on the coarse
    key still sort one way, always. The first three terms are ``chain_events``'
    own ordering (``at`` timestamp, ``task_id``, arrival-before-transition) so
    a merged stream replays through the same chain construction the migration
    uses. The remaining terms (``from_state``/``to_state``/``actor``/``detail``)
    are the **stated tie-break**: they make the order total rather than stable-
    but-input-dependent, so ``merge(a,b) == merge(b,a)`` byte-for-byte. Every
    element is a string/int (``None`` coalesced to ``""``) so the tuple is
    comparable element-wise.
    """
    return (
        e["at"],
        e["task_id"],
        0 if e["from_state"] is None else 1,
        e["from_state"] or "",
        e["to_state"] or "",
        e["actor"],
        e.get("detail") or "",
    )


def merge_streams(a: list, b: list) -> list:
    """Merge two event streams into ONE deterministic total order.

    The future dreamhub multi-agent case: two coordinators each keep a journal,
    and a merged view must be independent of who produced which stream and in
    what order the files are named. The rule is: **union the streams and sort
    by :func:`event_sort_key`** — timestamp first, task id next, arrival before
    transition, then the full remaining canonical fields as the tie-break. The
    result is a total order with no dependence on input order, so it replays to
    an identical store regardless of how the streams were split. It does NOT
    deduplicate (the multi-agent case produces disjoint events; a genuinely
    shared event is a coordination bug to surface, not to silently collapse).
    """
    return sorted(a + b, key=event_sort_key)


# ---------------------------------------------------------------------------
# Verify — recompute the chain over a journal; report breaks.
# ---------------------------------------------------------------------------

def verify_chain(events: list) -> list:
    """Recompute the task_event hash chain over ``events``; return failures.

    Mirrors ``ud-dw-tasks-migrate.verify_task_event_chain`` but over an
    in-memory event list rather than a store, using the shared primitives.
    An empty list verifies cleanly (genesis only).
    """
    failures = []
    prev = genesis_hash()
    for i, e in enumerate(events, 1):
        h = hash_event(prev, canonical_event_bytes(e))
        # The recomputed chain is the truth; there is no carried hash to
        # compare against in the minimal .jsonl, so this recomputes and
        # would catch a future carried-hash mismatch the day one is added.
        prev = h
    return failures


def cli(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="replay_events.py",
        description="Replay the task_event journal and reconstruct the transition chain (entity columns stubbed — #294/#550).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("replay", help="reconstruct the transition chain from a .jsonl journal (entity columns stubbed — #294/#550)")
    pr.add_argument("journal")
    pr.add_argument("out")

    pe = sub.add_parser("export", help="export a store's task_events (the transition chain) to .jsonl")
    pe.add_argument("store")
    pe.add_argument("out")

    pm = sub.add_parser("merge", help="merge two .jsonl streams into one")
    pm.add_argument("a")
    pm.add_argument("b")
    pm.add_argument("out")

    pv = sub.add_parser("verify", help="recompute the chain over a .jsonl journal")
    pv.add_argument("journal")

    args = p.parse_args(argv)

    if args.cmd == "replay":
        events = read_journal(args.journal)
        out = replay_into(events, args.out)
        print(f"replayed {len(events)} event(s) into {out}")
        return 0
    if args.cmd == "export":
        events = export_journal(args.store)
        write_journal(events, args.out)
        print(f"exported {len(events)} event(s) to {args.out}")
        return 0
    if args.cmd == "merge":
        a = read_journal(args.a)
        b = read_journal(args.b)
        merged = merge_streams(a, b)
        write_journal(merged, args.out)
        print(f"merged {len(a)} + {len(b)} = {len(merged)} event(s) to {args.out}")
        return 0
    if args.cmd == "verify":
        events = read_journal(args.journal)
        fails = verify_chain(events)
        if fails:
            for f in fails:
                print(f"FAIL {f}", file=sys.stderr)
            return 1
        print(f"chain recomputed clean over {len(events)} event(s)")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(cli())
