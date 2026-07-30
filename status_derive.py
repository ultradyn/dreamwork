#!/usr/bin/env python3
"""status_derive.py — regenerate the store-derivable halves of the status
section from the ledger store (#560).

The status panel (`statusBlock`, watch.py) renders `.dreamwork/status.json` —
a hand-maintained loop claim. Two of the fields it shows are facts the ledger
store already owns, and they had drifted: #362 measured `queue` summing to 115
against 123 open entries, because nothing compared the loop's claim to the
truth. Post-cutover the store is the ONE source for queue depth
(`file-formats.md` retires `queue` from status.json), so the panel was left
showing nothing at all — the field that drifts was removed, and the renderer
that read it had no store-backed replacement.

This module IS that replacement. It is the ONE place the store-derivable
status fields are computed (his modular-python reminder — the `ledger_parse`
idiom: one deep, leaf module, importable and testable without a server).
watch.py imports it and calls it from `collect()`; the derivation logic lives
NOWHERE else.

A LEAF MODULE: it imports only `ledger_parse` (stdlib sqlite3 transitively),
never `watch.py`, so the deploy snapshot imports it without a cycle exactly as
it imports `ledger_parse`.

WHAT IS DERIVED (the only rendered field the store owns):

  queue.in_progress / queue.pending   the store is the source for the OPEN
                                      COUNT (queue depth); `in_progress` is
                                      the live-lane count the loop's `agents`
                                      roster already carries (the loop-claim
                                      remainder that stays in status.json —
                                      see the brief). The derivation mirrors
                                      `status_sync`'s split: in_progress +
                                      pending == the store's open count, so the
                                      total is the #362 truth, not the
                                      hand-maintained claim.

WHAT STAYS FROM status.json (loop-claim remainder — never touched here):
push, awaiting_human, task, goal, agents, last_tick, last_commit, deployed,
and every key in "the rest" fold. These are live process claims, not store
facts, and this module must not pretend otherwise.

DEGRADE, NEVER THROW: no store / pre-cutover target → status returned
UNCHANGED, byte-for-byte today's rendering. The dashboard renders for targets
that never cut over. A torn/missing store or an unreadable status never
raises; the request path never 500s over a derivation.

CACHE + INVALIDATION (his words — "cached, invalidated on changes"): the
existing seam carries this with NO second mechanism. `collect()` runs fresh on
every /data.json GET, and the client re-fetches when `/mtime` moves.
`watched_mtime` walks ALL of `.dreamwork/` — including `ledger.sqlite3` and
its `-wal`/`-shm` siblings — so a store write changes a file mtime, the
`/mtime` value moves, and the next `collect()` re-derives. The module itself
is STATELESS: a pure function of (dreamwork_dir, status), so there is no cache
HERE to invalidate — the /mtime→collect() poll is the cache, and it already
covers the store. Request-path cost is one read-only sqlite3 query
(`store_ids_by_state`); no subprocess (file-formats.md rejected an ~18ms/entry
`git log` on this path — sqlite reads are fine).
"""

from __future__ import annotations

from ledger_parse import source_of_truth, store_ids_by_state


def queue_depth(open_count: int, live_count: int) -> dict:
    """``{in_progress, pending}`` mirroring status_sync's split.

    The store owns the open COUNT (queue depth); the live-lane count is the
    `agents` roster (the loop claim that stays). ``in_progress`` is clamped to
    the open count — a stale roster cannot name more lanes in flight than
    there are open tasks — so ``in_progress + pending == open_count`` always,
    which is exactly the #362 invariant the hand-maintained claim broke.
    """
    in_progress = max(0, min(live_count, open_count))
    pending = max(0, open_count - in_progress)
    return {"in_progress": in_progress, "pending": pending}


def status_from_store(dreamwork_dir, status):
    """Return ``status`` with store-derivable fields regenerated (#560).

    Post-cutover (the store's cutover watermark is present, per
    ``source_of_truth``): returns a shallow copy of ``status`` with ``queue``
    set from the store's open count + the live-agent count the roster
    already carries. The loop-claim remainder (agents, push, deployed, prose)
    is passed through untouched.

    Pre-cutover / unreadable store / ``status`` not a dict: returns
    ``status`` UNCHANGED — byte-for-byte today's rendering, so a target that
    never cut over keeps reading its hand-maintained ``queue`` exactly as it
    did. Never raises.
    """
    if not isinstance(status, dict):
        return status
    if source_of_truth(str(dreamwork_dir)) != "store":
        return status
    # The store is the ONE source for queue depth (#294 T2 / #362): it owns
    # the open count, the truth the hand-maintained claim drifted from. The
    # live-lane count comes from the `agents` roster — the loop-claim
    # remainder that stays in status.json (the brief: agents, push, deployed,
    # prose stay sourced from the file). status_sync's split, with the store
    # as the open-count source and the roster as the live source.
    open_ids, _landed = store_ids_by_state(str(dreamwork_dir))
    open_count = len(open_ids)
    agents = status.get("agents")
    live = ([a for a in agents if isinstance(a, dict)]
            if isinstance(agents, list) else [])
    out = dict(status)
    out["queue"] = queue_depth(open_count, len(live))
    return out
