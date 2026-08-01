"""Golden vector for the task_event chain byte format (#549).

Filed from the #460 merge gate: the coordinator's independent red-run swapped
``from_state``/``to_state`` in ``ledger_store.canonical_event_bytes`` and ALL
66 replay/store/writer tests PASSED, because every check hashes through the
SAME shared construction (``canonical_event_bytes`` / ``hash_event`` /
the journal-local genesis). A self-consistent corruption of the chain's byte format is
therefore invisible everywhere: the format is exercised everywhere and pinned
nowhere. This file is the owed pin.

The contract it pins is `file-formats.md` § "The `task_event` journal
`.jsonl` — portable export/replay of the transition log (#460)" (landed
`4161f0e1`), which points at the field set and field order in
``ledger_store.canonical_event_bytes``:

    length_framed( str(task_id), at, cause,
                   from_state or "", to_state or "",
                   actor, detail or "" )

where ``length_framed`` is an 8-byte big-endian length prefix per part
followed by that part's utf-8 bytes (``receipt_id`` is stored on the row but
NOT part of the hash).

==========================================================================
MIGRATION WARNING — these literals ARE the chain format.
Changing any recorded literal below DELIBERATELY is a FORMAT MIGRATION and
must come with a `file-formats.md` contract edit in the SAME commit. The
file-formats.md #460 section already states the format is the one recomputed
from the shared construction; this test makes that statement checkable.
Accidental drift (a swap, a dropped field) must turn a literal RED — never
silently green, which is the failure mode this file exists to close.
==========================================================================

Named production line whose change must red this suite:
- canonical_event_bytes field order (from_state before to_state, 7 parts)
      -> test_canonical_event_bytes_matches_independently_built_contract_bytes
      -> test_canonical_sha256_matches_recorded_literal
      -> test_hash_event_matches_recorded_literal
- frozen v1 legacy genesis literal (new journals store their own random root)
      -> test_legacy_genesis_hash_matches_recorded_literal

A green red-run is a finding, never a relief. The exact-bytes test builds its
expected bytes with the test's OWN framing helper (never _length_framed /
canonical_event_bytes), so a swap or a dropped field in the production
function moves bytes the expectation does not move — a diff on failure names
WHICH field moved, not merely "a hash changed".
"""

from __future__ import annotations

import hashlib

import ledger_store

# --------------------------------------------------------------------------
# ONE fixed event — every field value DISTINCT, so a swap of any two adjacent
# canonical fields moves the bytes (the precondition the red proof depends on;
# asserted at runtime in test_golden_event_has_all_distinct_field_values).
# Valid task states are used so the vector also round-trips through the store.
# --------------------------------------------------------------------------
EVENT = {
    "task_id": 549,
    "at": "2026-07-30T10:11:12",
    "cause": "started_from_backlog",
    "from_state": "pending",
    "to_state": "in_progress",
    "actor": "loop",
    "detail": "golden-vector-549",
}

# Contract field order (see module docstring): the 7 canonical parts, each as
# a string exactly as canonical_event_bytes would pass them (str(task_id); the
# `or ""` fallback is exercised with all-non-empty values here, and from_state
# / to_state are kept distinct so a swap is detectable).
_CANON_PARTS = [
    str(EVENT["task_id"]),          # str(task_id)
    EVENT["at"],                    # at
    EVENT["cause"],                 # cause
    EVENT["from_state"],            # from_state (non-None here)
    EVENT["to_state"],              # to_state (distinct from from_state)
    EVENT["actor"],                 # actor
    EVENT.get("detail"),            # detail
]


def _frame(part: str) -> bytes:
    """The contract's length framing, written out explicitly in the TEST.

    8-byte big-endian length prefix + utf-8 bytes. This is an INDEPENDENT copy
    of the framing rule: it must never import or call ``_length_framed`` /
    ``canonical_event_bytes`` — calling the production framing to build the
    expectation is exactly the self-consistency trap this test exists to close
    (a swap there would be replicated here and the test would pass green over
    the bug, as all 66 other tests did at the #460 gate).
    """
    data = part.encode("utf-8")
    return len(data).to_bytes(8, "big") + data


# The expected canonical bytes, built ONLY from _frame (test-local), in the
# contract's field order. This is the independent expectation the production
# function is cross-checked against.
EXPECTED_CANONICAL = b"".join(_frame(p) for p in _CANON_PARTS)


def test_golden_event_has_all_distinct_field_values():
    """Precondition: every canonical field value is DISTINCT.

    A swap of two equal values moves no bytes, so the red proof (swap
    from_state/to_state) is only meaningful when the values differ. Derived at
    runtime over the actual parts, never a literal tuned to this fixture.
    """
    assert len(_CANON_PARTS) == len(set(_CANON_PARTS)), (
        "precondition violated: a repeated canonical field value would make a "
        "field-swap undetectable; every part must be distinct, got "
        f"{_CANON_PARTS!r}")
    # from_state / to_state distinct is the specific pair the red proof swaps.
    assert EVENT["from_state"] != EVENT["to_state"]


def test_canonical_event_bytes_matches_independently_built_contract_bytes():
    """THE pin. Production framing is cross-checked against the test's own
    independent framing (two different code paths).

    Named production line: ``ledger_store.canonical_event_bytes`` field order
    (from_state before to_state; 7 parts; each 8-byte-big-endian length
    framed). Break by swapping from_state/to_state, or dropping one part ->
    production bytes diverge from EXPECTED_CANONICAL and a diff names the field
    that moved. This is the assertion that was hollow everywhere else.
    """
    assert ledger_store.canonical_event_bytes(EVENT) == EXPECTED_CANONICAL


# --- Recorded golden digests ----------------------------------------------
# Each literal below was computed ONCE from the independently built expectation
# (this module's _frame / hashlib), NEVER from the production function. The
# provenance comment above each gives the exact one-liner a reviewer runs to
# recompute it from the contract. They are exercised through the production
# functions in the tests below, so a drift in production turns them RED.

# SHA-256 of the canonical bytes (contract field order, length-framed).
# Recompute: python3 -c "import hashlib;p=['549','2026-07-30T10:11:12','started_from_backlog','pending','in_progress','loop','golden-vector-549'];b=b''.join((len(x.encode()).to_bytes(8,'big')+x.encode()) for x in p);print(hashlib.sha256(b).hexdigest())"
GOLDEN_CANON_SHA256 = (
    "747e81af02784d7c392cf61952b08558083b72ece4e0befeca9394dbfb85f5d2")

# Historical H_0 = SHA-256(journal_id || creation schema version).  The live
# journal was created at v1, and v006 freezes that root as the legacy format
# literal instead of moving it with SCHEMA_VERSION.  New journals persist a
# journal-local root. New journals default to the same root so portable replay
# remains deterministic; a future re-seed must be an explicit format change.
# Recompute: python3 -c "import hashlib;print(hashlib.sha256(b'ud-dreamwork.task-ledger1').hexdigest())"
GOLDEN_GENESIS = (
    "dbb5fcbf8ada5ef7945a7175b9f2c206145f148dc6e4e1afa7567d485096f51d")

# H_i = SHA-256(domain_tag || H_(i-1) || length_framed(canonical_event_i));
# domain_tag=b"ud-dreamwork.task-event.v1" (DOMAIN_TAG), prev=genesis.
# prev_hash is GOLDEN_GENESIS above, so this literal MOVES IN LOCKSTEP with the
# legacy genesis pin. Recomputed here by hand from the contract one-liner.
# Recompute: python3 -c "import hashlib;p=['549','2026-07-30T10:11:12','started_from_backlog','pending','in_progress','loop','golden-vector-549'];c=b''.join((len(x.encode()).to_bytes(8,'big')+x.encode()) for x in p);g=hashlib.sha256(b'ud-dreamwork.task-ledger1').hexdigest();print(hashlib.sha256(b'ud-dreamwork.task-event.v1'+g.encode()+c).hexdigest())"
GOLDEN_HASH_EVENT = (
    "a185495232c8d769890c253238e69330319ab87d53548538c4e0b967a1c5d6d0")


def test_legacy_genesis_hash_matches_recorded_literal():
    """Pin the v1 root used by journals that predate stored genesis metadata."""
    assert ledger_store.LEGACY_GENESIS_HASH == GOLDEN_GENESIS


def test_canonical_sha256_matches_recorded_literal():
    """Pin the canonical bytes by a recorded digest of the production output.

    Redundant-but-documentary alongside the exact-bytes test (a digest cannot
    say WHICH field moved; the bytes test can). It earns its place because the
    literal is independently derived and recomputable from the contract, so a
    reviewer can confirm the recorded value without reading the production
    function. Break the production framing -> the digest of production output
    diverges from this literal.
    """
    assert hashlib.sha256(
        ledger_store.canonical_event_bytes(EVENT)).hexdigest() == GOLDEN_CANON_SHA256


def test_hash_event_matches_recorded_literal():
    """Pin hash_event: the domain tag and the chaining construction.

    Named production line: ``ledger_store.hash_event`` ->
    ``DOMAIN_TAG + prev_hash + canonical``. Break by editing DOMAIN_TAG, or the
    canonical framing (via canonical_event_bytes) -> the head disagrees with
    this literal. prev_hash is fixed to the genesis literal above.
    """
    assert ledger_store.hash_event(
        GOLDEN_GENESIS,
        ledger_store.canonical_event_bytes(EVENT)) == GOLDEN_HASH_EVENT
