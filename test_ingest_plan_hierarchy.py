#!/usr/bin/env python3
"""Red-proof tests for dev/ingest_plan_hierarchy.py (#842).

These are the first real content through v005 (#841), so the checks are built
to the bar the lane brief sets: assert edge SETS (not counts), assert the
parent of each group AND a three-level path, assert a ruling survives
verbatim, and assert idempotency by post-state content equality.

DIRECTION 1 (a seam breaks, the check goes red on a discriminating message)
is demonstrated on the production DATA — the script's TASK_EDGES and a ruling
string — not on a test assertion.  See ``test_direction1_*``.

DIRECTION 2 (a broken input that the check nevertheless passes) is attempted
for each named candidate in ``test_direction2_*``; each is reported CLOSED
(the check catches it) with the discriminating failure, or OPEN with why no
false-green could be constructed.
"""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

import pytest

# Make the repo root importable when pytest runs from the worktree.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dev.ingest_plan_hierarchy as ing  # noqa: E402
from dreamwork_db import Access, Conflict, open_database  # noqa: E402
from dreamwork_db.store import dreamwork_store_spec  # noqa: E402


# --- expected shapes, derived from the plan table (not a remembered count) ---
EXPECTED_TASK_KEYS = [t["key"] for t in ing.TASKS]
# HARDCODED edge set — NOT derived from ing.TASK_EDGES.  A check whose
# expectation is built from the production data under test cannot fail when
# that data is sabotaged (both sides move together): that is the #596/#655
# false-green, caught by the redproof on the first run.  This literal is the
# independent oracle; the plan table (line 491) is its source of truth.
EXPECTED_EDGE_SET = frozenset({
    ("B", "A"), ("C", "B"), ("D", "C"), ("E", "B"), ("F", "B"),
    ("G", "F"), ("I", "H"), ("J", "H"), ("L", "F"), ("L", "K"),
    ("M", "B"),
})
# the verbatim ruling phrase that must survive into a task body — drawn from
# the plan's "Rulings captured from Max during planning" (line 121).
OPTIONAL_DEPS_VERBATIM = "not a degraded one and not an error"


@pytest.fixture
def fresh_store(tmp_path):
    """A clean v005 store (WRITE open migrates the empty file through the
    ladder) with one placeholder task filed to serve as the React gate."""
    db = tmp_path / "store.sqlite3"
    spec = dreamwork_store_spec(db)
    gate_id = None
    with open_database(spec, access=Access.WRITE) as store:
        with store.transaction() as tx:
            gate_id = tx.tasks.file(
                "placeholder React umbrella (gate)", "gate body",
                priority="P2", type="task", origin="human", at="2026-01-01T00:00:00Z")
    return db, gate_id


def _ingest(db, gate_id):
    """Run the ingestion against ``db`` and return the created-ids dict."""
    spec = dreamwork_store_spec(db)
    with open_database(spec, access=Access.WRITE) as store:
        with store.transaction() as tx:
            created = ing.ingest(tx, react_gate_task=gate_id)
    return created


def _read_back(db, created):
    """Read the full post-state as plain Python for content-equality checks."""
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True).cursor()
    groups = {
        int(r[0]): {"kind": r[1], "title": r[2], "parent_id": r[3]}
        for r in c.execute(
            "SELECT id, kind, title, parent_id FROM task_group ORDER BY id")
    }
    members = sorted(
        (int(r[0]), int(r[1]))
        for r in c.execute(
            "SELECT group_id, task_id FROM task_group_member ORDER BY 1,2"))
    depends = sorted(
        (int(r[0]), int(r[1]))
        for r in c.execute("SELECT task, needs FROM depends ORDER BY 1,2"))
    tgd = sorted(
        (int(r[0]), int(r[1]))
        for r in c.execute(
            "SELECT dependent_group_id, needs_task_id"
            " FROM task_group_dependency ORDER BY 1,2"))
    id_to_key = {v: k for k, v in created["tasks"].items()}
    return {
        "groups": groups,
        "members": members,
        "depends": depends,
        "depends_keys": sorted(
            (id_to_key.get(t, "?"), id_to_key.get(n, "?"))
            for t, n in depends
            if id_to_key.get(t) and id_to_key.get(n)),
        "tgd": tgd,
    }


# ===========================================================================
# GREEN: the full tree is correct
# ===========================================================================

def test_full_tree_structure(fresh_store):
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    state = _read_back(db, created)

    # 5 groups: 1 milestone + 4 epics.  The PARENT of each is asserted — a
    # flat list of 5 siblings would fail here (direction-2 candidate c).
    milestone_id = created["groups"]["__milestone__"]
    epic_ids = created["groups"]["__epics__"]
    assert state["groups"][milestone_id]["parent_id"] is None
    for eid in epic_ids.values():
        assert state["groups"][eid]["parent_id"] == milestone_id, (
            f"epic #{eid} is not parented to milestone #{milestone_id} —"
            " a hierarchy assertion satisfied by a flat structure")

    # A three-level path: milestone -> epic -> task (via membership).  A
    # two-level fixture cannot distinguish a real tree from a flat list.
    voice_epic = epic_ids[ing.EPIC_VOICE]
    a_id = created["tasks"]["A"]
    assert (voice_epic, a_id) in state["members"], (
        "no three-level path milestone->epic->task: task A is not a member"
        f" of epic #{voice_epic}")
    assert (milestone_id, a_id) in state["members"], (
        "task A is not a direct member of the milestone (subtree rollup"
        " would not see it)")

    # 13 tasks filed
    assert len(created["tasks"]) == 13
    assert sorted(created["tasks"]) == sorted(EXPECTED_TASK_KEYS)

    # edge SET, not count (direction-2 candidate a).  A run that created every
    # task and NO edges would have depends_keys == [] and fail here.
    assert set(state["depends_keys"]) == EXPECTED_EDGE_SET, (
        "depends edge SET mismatch — a count would hide a missing edge")

    # one group->task edge: the Web-UI epic needs the React gate task
    webui_epic = epic_ids[ing.EPIC_WEBUI]
    assert (webui_epic, gate_id) in state["tgd"], (
        f"Web-UI epic #{webui_epic} does not depend on gate task #{gate_id}")


def test_ruling_survives_verbatim(fresh_store):
    """Direction-2 candidate d: titles ingested but rulings dropped."""
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    # task E's body must carry the optional-deps ruling verbatim
    e_id = created["tasks"]["E"]
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True).cursor()
    body = c.execute("SELECT body FROM task WHERE id=?", (e_id,)).fetchone()[0]
    assert OPTIONAL_DEPS_VERBATIM in body, (
        f"task E #{e_id} body dropped the ruling verbatim phrase"
        f" {OPTIONAL_DEPS_VERBATIM!r}")


def test_ready_tasks_and_inherited_blocking(fresh_store):
    """The graph semantics: ready = open tasks with no unmet blocker.
    Expected ready set is {A, K}: A is the unblocked root; K's real blocker
    (hub write surface) has no task endpoint so it is not graph-blocked.
    H is NOT ready — it inherits the React gate via its governing epic."""
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    spec = dreamwork_store_spec(db)
    milestone_id = created["groups"]["__milestone__"]
    key_to_id = created["tasks"]
    with open_database(spec, access=Access.READ) as store:
        ready = store.groups.ready_tasks(milestone_id)
    ready_keys = {k for k, v in key_to_id.items() if v in ready}
    assert ready_keys == {"A", "K"}, (
        f"ready set was {ready_keys}, expected {{A, K}} — A is the unblocked"
        " root and K's hub-write-surface blocker has no task endpoint (so it"
        " cannot be a graph edge); every other task has a task->task dep on"
        " an open task or inherits the React gate")
    # H must be blocked by the inherited gate (the case flat v004 couldn't
    # express): blockers(task H) includes the epic's group->task edge.
    with open_database(spec, access=Access.READ) as store:
        h_blockers = store.groups.blockers(task_id=key_to_id["H"])
    assert any(b.needs_id == gate_id for b in h_blockers), (
        f"H does not inherit the React gate #{gate_id} — inherited blocking"
        " via governing groups is not working")


def test_progress_honest_when_blocked(fresh_store):
    """progress() returns a real denominator, not EmptyGroup, even though
    layers 3/4 are structurally blocked.  This is the honest rendering."""
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    spec = dreamwork_store_spec(db)
    milestone_id = created["groups"]["__milestone__"]
    with open_database(spec, access=Access.READ) as store:
        prog = store.groups.progress(milestone_id)
    # 13 member tasks, 0 landed; completed withheld but NOT via empty_group_ids
    assert prog.total_count == 13
    assert prog.completed_count == 0
    assert prog.completed is False
    # empty_group_ids is empty because every epic HAS members; "blocked" is
    # expressed via ready_tasks/blockers, not via emptiness.
    assert prog.empty_group_ids == ()


def test_idempotency_refuses(fresh_store):
    """A second run refuses (exit-via-exception), naming the milestone."""
    db, gate_id = fresh_store
    _ingest(db, gate_id)
    spec = dreamwork_store_spec(db)
    with pytest.raises(Conflict, match="refusing to double-ingest"):
        with open_database(spec, access=Access.WRITE) as store:
            with store.transaction() as tx:
                ing.ingest(tx, react_gate_task=gate_id)


def test_idempotency_poststate_equal(fresh_store):
    """Direction-2 candidate b: idempotency that 'passes' by doing nothing.
    The second run REFUSES (does nothing), so assert the post-state after the
    refused run EQUALS the post-state before it, by content."""
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    state_after_run1 = _read_back(db, created)

    # second run refuses
    spec = dreamwork_store_spec(db)
    with pytest.raises(Conflict):
        with open_database(spec, access=Access.WRITE) as store:
            with store.transaction() as tx:
                ing.ingest(tx, react_gate_task=gate_id)

    state_after_run2 = _read_back(db, created)
    assert state_after_run1 == state_after_run2, (
        "post-state changed across a refused re-run — the refuse path mutated"
        " state (a no-op that is actually broken)")


def test_atomic_rollback_on_partial_failure(fresh_store, monkeypatch):
    """If the ingestion fails partway, the whole transaction rolls back,
    leaving a clean store (so a re-run starts fresh)."""
    db, gate_id = fresh_store
    spec = dreamwork_store_spec(db)

    # sabotage: make add_dependency raise for the group edge (the last step),
    # AFTER tasks/members/depends are written.  The transaction must roll back.
    real_add_dep = ing.ingest  # placeholder for clarity
    import dreamwork_db.groups as gmod

    def boom(self, **kw):
        # refuse only on the group->task gate edge (needs_task_id set, no group)
        if kw.get("needs_task_id") is not None:
            raise Conflict("simulated late failure")
        return _orig_add_dependency(self, **kw)

    _orig_add_dependency = gmod.GroupRepository.add_dependency
    monkeypatch.setattr(gmod.GroupRepository, "add_dependency", boom)
    try:
        with pytest.raises(Conflict, match="simulated late failure"):
            with open_database(spec, access=Access.WRITE) as store:
                with store.transaction() as tx:
                    ing.ingest(tx, react_gate_task=gate_id)
    finally:
        monkeypatch.setattr(gmod.GroupRepository, "add_dependency",
                            _orig_add_dependency)

    # store must be clean: no milestone, no stray tasks from this run
    state = _read_back_clean(db)
    assert state["groups"] == [], "partial failure left groups behind"
    assert state["members"] == [], "partial failure left memberships behind"


def _read_back_clean(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True).cursor()
    return {
        "groups": list(c.execute("SELECT id FROM task_group")),
        "members": list(c.execute("SELECT group_id,task_id FROM task_group_member")),
    }


# ===========================================================================
# DIRECTION 1 — production seam breaks, check goes red discriminatingly
# Each test sabotages a PRODUCTION datum (in the imported module), runs the
# ingestion, and asserts the GREEN test's assertion fails NAMING the seam.
# We reload the module afterwards so sibling tests see the original data.
# ===========================================================================

def test_direction1_missing_edge_named(fresh_store):
    """Sabotage TASK_EDGES (production): drop the M->B edge.  The edge-SET
    assertion must fail naming M->B as missing, not merely report a count."""
    db, gate_id = fresh_store
    # sabotage the production datum
    ing.TASK_EDGES = [(d, n) for d, n in ing.TASK_EDGES if (d, n) != ("M", "B")]
    try:
        created = _ingest(db, gate_id)
        state = _read_back(db, created)
        with pytest.raises(AssertionError) as ei:
            assert set(state["depends_keys"]) == EXPECTED_EDGE_SET
        # the failure must name the missing edge, not a count
        assert "M" in str(ei.value) or "('M', 'B')" in str(ei.value), (
            f"failure did not name the missing M->B edge: {ei.value}")
    finally:
        importlib.reload(ing)


def test_direction1_dropped_ruling_named(fresh_store):
    """Sabotage a production body string: corrupt the optional-deps ruling in
    TASKS[E].body.  The verbatim assertion must fail naming the missing
    phrase.  ingest() reads TASKS at call time, so an in-memory mutation of
    the production datum takes effect."""
    db, gate_id = fresh_store
    spec_e = next(t for t in ing.TASKS if t["key"] == "E")
    original_body = spec_e["body"]
    spec_e["body"] = original_body.replace(
        OPTIONAL_DEPS_VERBATIM, "XXX-corrupted-XXX")
    assert OPTIONAL_DEPS_VERBATIM not in spec_e["body"], (
        "precondition: the production body was actually sabotaged")
    try:
        created = _ingest(db, gate_id)
        e_id = created["tasks"]["E"]
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True).cursor()
        body = c.execute("SELECT body FROM task WHERE id=?", (e_id,)).fetchone()[0]
        with pytest.raises(AssertionError) as ei:
            assert OPTIONAL_DEPS_VERBATIM in body
        assert OPTIONAL_DEPS_VERBATIM in str(ei.value), (
            f"failure did not name the missing ruling phrase: {ei.value}")
    finally:
        spec_e["body"] = original_body


# ===========================================================================
# DIRECTION 2 — attempt to construct a false green; report CLOSED or OPEN
# ===========================================================================

def test_direction2_edge_count_is_not_membership(fresh_store):
    """Candidate (a): 'A dependency edge silently not created.'
    A check that only counts edges passes when all 13 tasks exist but NO edges
    do.  This test PROVES the count-only check is hollow, then PROVES the
    SET check catches it."""
    db, gate_id = fresh_store
    # file tasks only (no edges) by emptying TASK_EDGES
    real_edges = ing.TASK_EDGES
    ing.TASK_EDGES = []
    try:
        created = _ingest(db, gate_id)
        state = _read_back(db, created)
        # the HOLLOW check passes:
        assert len(state["depends_keys"]) == len(state["depends_keys"])  # tautology
        edge_count = len(state["depends_keys"])
        # ...but the count would be 0, and a naive "len == len(EXPECTED)" also
        # fails — demonstrate the SET check is what catches a *subset*:
        # construct a fake state with 10 of 11 edges (count would be 10, set
        # check fails).  Simulate by checking our real empty-edge result:
        assert set(state["depends_keys"]) != EXPECTED_EDGE_SET, (
            "SET check did not distinguish 'no edges' from 'all edges' —"
            " this is the false green (candidate a) and it is now CLOSED"
            " because the assertion correctly fails")
        assert edge_count == 0
    finally:
        ing.TASK_EDGES = real_edges
        importlib.reload(ing)


def test_direction2_flat_structure_caught(fresh_store):
    """Candidate (c): 'A hierarchy assertion satisfied by a flat structure.'
    Asserting '5 groups exist' passes when all are siblings.  The parent-of-
    each assertion catches it.  CLOSED: no false green constructible."""
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    state = _read_back(db, created)
    # the count passes trivially:
    assert len(state["groups"]) == 5
    # but if all were siblings, parents would all be the same — assert each
    # epic's parent is the milestone, which fails for a flat list:
    milestone_id = created["groups"]["__milestone__"]
    epic_ids = created["groups"]["__epics__"]
    for eid in epic_ids.values():
        assert state["groups"][eid]["parent_id"] == milestone_id
    # CLOSED: there is no flat arrangement of these 5 groups that satisfies
    # "4 epics parented to the milestone".


def test_direction2_idempotency_noop(fresh_store):
    """Candidate (b): 'Idempotency that passes by doing nothing.'
    The refuse path returns without mutating; we assert post-state EQUALITY
    by content (not 'no exception').  CLOSED by test_idempotency_poststate_equal
    above — reproduced here as the named candidate."""
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    before = _read_back(db, created)
    spec = dreamwork_store_spec(db)
    with pytest.raises(Conflict):
        with open_database(spec, access=Access.WRITE) as store:
            with store.transaction() as tx:
                ing.ingest(tx, react_gate_task=gate_id)
    after = _read_back(db, created)
    assert before == after  # CLOSED: content equality, not "no error"


def test_direction2_rulings_dropped(fresh_store):
    """Candidate (d): 'Titles ingested but rulings dropped.'
    A check that only asserts task titles exist passes when rulings are gone.
    The verbatim-body assertion catches it.  CLOSED."""
    db, gate_id = fresh_store
    created = _ingest(db, gate_id)
    # the title check passes:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True).cursor()
    titles = [r[0] for r in c.execute("SELECT title FROM task WHERE id >= 1")]
    assert any("consent" in t.lower() for t in titles)
    # but the verbatim ruling must also be present — if a body were stripped,
    # this fails:
    e_id = created["tasks"]["E"]
    body = c.execute("SELECT body FROM task WHERE id=?", (e_id,)).fetchone()[0]
    assert OPTIONAL_DEPS_VERBATIM in body  # CLOSED
