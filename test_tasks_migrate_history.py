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
def test_recover_extracts_last_verbatim_body(module):
    a = _analysis(module, CURRENT[2])
    assert _groomed(a) == {5, 6, 7}, "fixture lost its groomed shape"
    r = module.recover_groomed_history(a, SNAPSHOTS)
    assert set(r["tasks"]) == {5, 7}, "recoverable ids wrong"
    assert r["tasks"][5]["body"] == FIVE_V2, "must be the LAST verbatim body"
    assert r["tasks"][5]["state"] == "landed"
    assert r["tasks"][7]["body"] == SEVEN


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
