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

A LEAF MODULE: it imports only `ledger_parse` and `user_events.sqlite`
(both stdlib-only transitively), never `watch.py`, so the deploy snapshot
imports it without a cycle exactly as it imports `ledger_parse`.

WHAT IS DERIVED (the only rendered field the store owns):

  queue.in_progress / queue.pending   the store is the source for the OPEN
                                      COUNT (queue depth); `in_progress` is
                                      the live-lane count the loop's
                                      `dreamers` roster carries — the pruned,
                                      liveness-checked lane set `status_sync`
                                      derives (#965; `agents` is the empty
                                      loop-claim the derivation once misread).
                                      The derivation mirrors `status_sync`'s
                                      split: in_progress + pending == the
                                      store's open count, so the total is the
                                      #362 truth, not the hand-maintained
                                      claim. When the roster is unreadable
                                      (absent/non-list) `queue` is `None`,
                                      not a borrowed 0 (#868).

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
its `-wal` sibling, but NOT `-shm` (#620: a read moves the shared-memory
index, so watching it made serving `/data.json` schedule the next refetch;
`-wal` and the db file carry every real write, measured) — so a store write
changes a file mtime, the `/mtime` value moves, and the next `collect()`
re-derives. The module itself
is STATELESS: a pure function of (dreamwork_dir, status), so there is no cache
HERE to invalidate — the /mtime→collect() poll is the cache, and it already
covers the store. Request-path cost is two read-only sqlite3 reads —
`store_ids_by_state` over the ledger, and `pending_event_count`'s single
`events_since_cursor` over the journal (#655); no subprocess (file-formats.md
rejected an ~18ms/entry `git log` on this path — sqlite reads are fine).

THE JOURNAL READ'S COST SCALES WITH THE BACKLOG, and that is stated rather
than hidden because the obvious cheaper form is the one this must not take.
`events_since_cursor` materialises each pending receipt's `exact_payload_bytes`
and the count is `len()` of that — measured on btrfs: 100 pending ≈ 3.7 ms,
1 000 ≈ 8.2 ms, 5 000 with 4 KB bodies ≈ 76 ms. A `SELECT COUNT(*)` would be
flat, and is REFUSED anyway: it would be a second implementation of "what is
pending", free to drift from the drain (and to forget the projection's
`receipt.created` kind filter). The drain runs every tick, so the steady-state
backlog is a handful of rows; a backlog large enough for this to matter is
itself the thing the count exists to show. Neither read moves `watched_mtime`
(measured 0/8 `collect()` calls on a real filesystem, with and without a
journal) — #620's refetch loop is not reintroduced.
"""

from __future__ import annotations

from pathlib import Path

from ledger_parse import source_of_truth, store_ids_by_state
# #655 — the durable user-event journal is a second store under `.dreamwork/`,
# and the count of undrained receipts is a store-derivable status field, so it
# lives in this ONE leaf module beside the ledger derivation. `open_journal` is
# the same public API `dev/journal_consume.py` (the drain) and `watch.py`
# (the receiver) already use; importing it here keeps a single cursor reader.
from user_events.sqlite import open_journal


def queue_depth(open_count: int, live_count: int) -> dict:
    """``{in_progress, pending}`` mirroring status_sync's split.

    The store owns the open COUNT (queue depth); the live-lane count is the
    `dreamers` roster (the pruned, liveness-checked lane set `status_sync`
    derives and maintains — #965). ``in_progress`` is clamped to the open
    count — a stale roster cannot name more lanes in flight than there are
    open tasks — so ``in_progress + pending == open_count`` always, which is
    exactly the #362 invariant the hand-maintained claim broke.

    Note: an UNREADABLE roster (absent/non-list) is handled one call up in
    ``status_from_store`` as ``queue is None`` — it must not reach this clamp,
    which would manufacture a plausible 0 for a count never taken (#868).
    """
    in_progress = max(0, min(live_count, open_count))
    pending = max(0, open_count - in_progress)
    return {"in_progress": in_progress, "pending": pending}


def status_from_store(dreamwork_dir, status):
    """Return ``status`` with store-derivable fields regenerated (#560).

    Post-cutover (the store's cutover watermark is present, per
    ``source_of_truth``): returns a shallow copy of ``status`` with ``queue``
    set from the store's open count + the live-lane count the ``dreamers``
    roster carries. When the roster is absent/non-list (unreadable), ``queue``
    is set to ``None`` — "there and unreadable", not a borrowed 0. The
    loop-claim remainder (agents, push, deployed, prose) is passed through
    untouched.

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
    # live-lane count comes from the `dreamers` roster — the pruned,
    # liveness-checked lane set `status_sync` DERIVES and maintains (#965).
    # `agents` is the author-owned loop-claim and is EMPTY in production; this
    # derivation once read it and rendered `0 in flight` while lanes worked.
    # `status_sync`'s split, with the store as the open-count source and the
    # `dreamers` roster as the live source — the same field `status_sync`
    # computes `current_task_ids` from, so the two cannot disagree.
    open_ids, _landed = store_ids_by_state(str(dreamwork_dir))
    open_count = len(open_ids)
    dreamers = status.get("dreamers")
    out = dict(status)
    if not isinstance(dreamers, list):
        # No roster to measure: the live count is UNREADABLE, not zero. The
        # clamp (`min(live, open)`) would otherwise manufacture a plausible 0
        # — the #868 degrade-to-zero shape inside this very arithmetic, and
        # why nobody noticed the empty-`agents` read. `queue is None` says
        # "there and unreadable" (the `== null` idiom the panel runs for
        # `pending_events`) rather than borrowing zero's pixels for a count
        # that was never taken. An EMPTY list is a genuine measurement (0
        # lanes running) and takes the branch below; only an absent/non-list
        # roster degrades here.
        out["queue"] = None
        return out
    live = [d for d in dreamers if isinstance(d, dict)]
    out["queue"] = queue_depth(open_count, len(live))
    return out


# --- #655 — undrained journal receipts as a status count -------------------
#
# The dashboard journals a durable receipt for every write route, and the
# coordinator drains them each tick with `dev/journal_consume.py`: `pending`
# lists everything after the cursor, the coordinator processes each one, then
# `consume --through <ordinal>` advances the cursor. The number he wants on
# the status section is the count of receipts after the cursor — the SAME set
# `pending` prints.
#
# The single consumer this drain serves (delivery-modes.md §"How an agent
# consumes the cursor in batched mode") — the literal the cursor row is keyed
# by, identical to `dev/journal_consume.py`'s `CONSUMER` (and
# `dev/reconcile_submissions.py`'s). The cursor row the count reads is keyed
# by this string, so a second spelling would read a different (empty) cursor
# and silently report zero forever; it is reused verbatim, not re-derived.
CONSUMER = "coordinator"


def pending_event_count(journal_path):
    """Count of ``receipt.created`` events in ``(coordinator_cursor, head]`` (#655).

    Returns an ``int`` when the journal was read, ``None`` when it exists but
    could NOT be read. See "THREE STATES" below — the distinction is the point,
    not a nicety.

    This is the set ``dev/journal_consume.py pending`` lists — the receipts the
    coordinator has not yet drained. It is computed by the SAME public read the
    drain composes, ``Journal.events_since_cursor(CONSUMER)`` (the projection in
    ``user_events/sqlite.py`` that resolves the cursor lower bound and the head
    upper bound), so the count and the drain agree by construction: two
    independent implementations of "what is pending" would disagree the first
    time the schema moved, and a count that disagrees with the drain is worse
    than no count because it would be trusted. Read-only: never advances the
    cursor, never writes (the projection's own contract).

    THREE STATES, DISTINGUISHABLE FROM THE DATA — the `push` idiom this very
    panel already runs on (file-formats.md: *"Three states are distinguishable
    from the data"*), and the correction of this function's first shape:

      no journal      → ``0``.    A target that has never received a write has
                                  nothing pending. This is a MEASUREMENT, not a
                                  fallback: the drain agrees (``cmd_pending``
                                  returns EX_OK printing nothing).
      read            → ``int``.  The count, from the drain's own projection.
      exists, unread  → ``None``. NOT ``0``.

    The last one is the half that had to change. Reading ``0`` there is a
    FALSE GREEN in the reassuring direction, and it is not symmetric with the
    drain: measured on a journal with three genuinely-pending receipts, a
    ``schema_version`` mismatch and a corrupt header BOTH made the old code
    answer ``0`` while ``journal_consume.py pending`` over the same file raised
    ``VersionMismatchError`` and refused to open. The drain fails CLOSED and
    shouts; a count that fails OPEN and reassures does not "agree with the
    drain by construction" — it agrees on the happy path and diverges maximally
    on the unhappy one. Worse, the renderer is quiet at zero, so "I could not
    read it" was painted as the same zero pixels as "there is nothing to
    drain", forever: a schema drift or a torn file is PERMANENT, not a blink
    the next tick clears. ``None`` is rendered as its own fact instead.

    Still degrade, never throw: the request path must not 500 over a derivation
    (``status_from_store``'s posture — note that function has no ``except`` at
    all; it degrades by BRANCHING on absent preconditions, and the narrow
    ``except sqlite3.Error`` in ``ledger_parse.store_ids_by_state`` is the
    reader idiom this follows). The catch stays broad on purpose now that it no
    longer lies: a refactor that makes the projection raise ``TypeError`` also
    lands here, and under the old shape that read as a permanent silent zero.

    ``len()`` is taken rather than a COUNT query so the projection is the single
    reader — a second query would be a second thing that could disagree with the
    drain, and it would not carry the projection's ``receipt.created`` kind
    filter (transitions, claims, finishes, health marks and the cutover
    watermark share the chain's ordinals and are NOT receipts to drain).

    ``journal_path`` is the resolved path (``watch._journal_path(target)``,
    built from ``watch.JOURNAL_FILENAME``) so the filename stays single-source
    in ``watch.py`` and is not copied here.
    """
    p = Path(journal_path)
    if not p.exists():
        return 0
    try:
        with open_journal(p) as j:
            return len(j.events_since_cursor(CONSUMER))
    except Exception:
        # No derivation may refuse a /data.json over a store it cannot read.
        # But it must not claim a number it does not have either: `None` says
        # "unread", which the panel renders as its own fact. A zero here would
        # be the dashboard's most reassuring answer given for its least
        # reassuring reason.
        return None
