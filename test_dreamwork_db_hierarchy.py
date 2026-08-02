"""Nested collections, cross-level dependencies, and batch pools (#841).

Every membership assertion here compares an ID SET, never a length: #702 and
#820 are three landed bugs where a count stood in for a set and a duplicate or
a swapped identity passed unseen.  Every tree built is at least THREE levels
deep, because a two-level fixture cannot tell a real recursive traversal from
one hard-coded to a single level.
"""

from __future__ import annotations

import sqlite3

import pytest

from dreamwork_db import Access, ValidationError, open_database
from dreamwork_db.core import SchemaMismatch
from dreamwork_db.groups import DependencyCycle, EmptyGroup
from dreamwork_db.migrate import SCHEMA_VERSION
from dreamwork_db.migrations import (
    v005_hierarchy, v008_goals, v009_goal_bypass, v010_posture_history,
)
from dreamwork_db.tasks import task_store_spec
from dev import ledger as ledger_cli


@pytest.fixture
def store_path(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    path = dw / "ledger.sqlite3"
    (dw / "tasks.md").write_text(
        "---\ndreamwork-ledger: migrated\nsource-of-truth: store\n---\n"
    )
    with open_database(task_store_spec(path), access=Access.WRITE) as store:
        with store.transaction():
            pass
    return path


def _insert_tasks(path, rows):
    conn = sqlite3.connect(path)
    try:
        for task_id, state in rows:
            conn.execute(
                "INSERT INTO task"
                " (id,state,title,body,priority,type,origin,blocked_on)"
                " VALUES (?,?,?,?,?,?,?,NULL)",
                (task_id, state, f"task {task_id}", f"body {task_id}",
                 "P2", "task", "loop"),
            )
        conn.commit()
    finally:
        conn.close()


def _make(store, kind, title, parent=None):
    with store.transaction() as tx:
        return tx.groups.create(
            kind=kind, title=title, actor="test",
            at="2026-08-01T00:00:00Z", parent_id=parent,
        )


def _add(store, group_id, *task_ids):
    for task_id in task_ids:
        with store.transaction() as tx:
            tx.groups.add_task(
                group_id, task_id, actor="test", at="2026-08-01T00:00:01Z"
            )


def _four_level_tree(store):
    """milestone > feature > epic > batch — four levels, so a traversal that
    stops early cannot pass, and the kinds include two v004 could not name."""
    milestone = _make(store, "milestone", "Release 1")
    feature = _make(store, "feature", "Hierarchy", parent=milestone)
    epic = _make(store, "epic", "Store", parent=feature)
    batch = _make(store, "batch", "Migration batch", parent=epic)
    return milestone, feature, epic, batch


# --- the vocabulary is data, not a CHECK ------------------------------------

def test_kinds_come_from_the_store_and_can_be_widened(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        with store.transaction() as tx:
            seeded = set(tx.groups.kinds())
        assert seeded == {
            "lane", "epic", "milestone", "feature", "batch", "goal"
        }, (
            "v005 seeds its hierarchy kinds plus v008's goal kind; got "
            f"{sorted(seeded)}"
        )
        with store.transaction() as tx:
            assert tx.groups.define_kind("initiative") == "defined"
            assert tx.groups.define_kind("initiative") == "unchanged"
        # The point of the lookup table: a NEW level needs no migration.
        group_id = _make(store, "initiative", "Above milestones")
        with store.transaction() as tx:
            assert tx.groups.get(group_id).kind == "initiative"
            assert "initiative" in tx.groups.kinds()


def test_feature_is_creatable_although_v004_rejected_it(store_path):
    """His request said "milestone/feature"; v004's CHECK had no `feature`."""
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _make(store, "feature", "A feature")
        with store.transaction() as tx:
            assert tx.groups.get(group_id).kind == "feature"


# --- nesting ----------------------------------------------------------------

def test_four_level_chain_is_expressible_and_traversed_to_the_bottom(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        milestone, feature, epic, batch = _four_level_tree(store)
        with store.transaction() as tx:
            assert {g.id for g in tx.groups.descendants(milestone)} == {
                feature, epic, batch
            }, "a traversal that stops at one level would omit epic and batch"
            assert [g.id for g in tx.groups.ancestors(batch)] == [
                epic, feature, milestone
            ], "ancestors must run nearest-first all the way to the root"
            assert {g.id for g in tx.groups.children(milestone)} == {feature}
            assert tx.groups.get(batch).parent_id == epic
            assert tx.groups.get(milestone).parent_id is None


def test_rollup_reaches_a_task_three_levels_below(store_path):
    _insert_tasks(store_path, [(301, "landed"), (302, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        milestone, _feature, _epic, batch = _four_level_tree(store)
        _add(store, batch, 301, 302)
        with store.transaction() as tx:
            progress = tx.groups.progress(milestone)
        assert set(progress.member_task_ids) == {301, 302}, (
            "the milestone holds no task DIRECTLY; a non-recursive rollup "
            f"would find none, got {progress.member_task_ids}"
        )
        assert set(progress.landed_task_ids) == {301}
        assert progress.completed is False


def test_a_task_in_both_a_group_and_its_ancestor_is_counted_once(store_path):
    """#702/#820: assert the ID SET. A double-counting rollup returns the same
    task twice, so `total_count` reads 3 while the real membership is 2."""
    _insert_tasks(store_path, [(401, "landed"), (402, "landed")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        milestone, feature, epic, _batch = _four_level_tree(store)
        _add(store, epic, 401, 402)
        _add(store, feature, 401)      # 401 is now in two groups in one chain
        _add(store, milestone, 401)    # ...and three
        with store.transaction() as tx:
            progress = tx.groups.progress(milestone)
        assert set(progress.member_task_ids) == {401, 402}
        assert progress.member_task_ids == (401, 402), (
            "membership must be de-duplicated and ordered, got "
            f"{progress.member_task_ids}"
        )
        assert progress.total_count == 2, (
            "the same task in three groups of one chain is ONE member; "
            f"got total_count={progress.total_count}"
        )
        assert set(progress.landed_task_ids) == {401, 402}


# --- cycles -----------------------------------------------------------------

def test_a_parent_cycle_is_refused_and_the_message_names_the_path(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        top = _make(store, "milestone", "Top")
        mid = _make(store, "epic", "Mid", parent=top)
        low = _make(store, "batch", "Low", parent=mid)
        with store.transaction() as tx:
            with pytest.raises(DependencyCycle) as caught:
                tx.groups.set_parent(top, low)
        message = str(caught.value)
        # Discriminating: WHICH group's parent was wrong, and the exact path.
        assert f"milestone #{top} 'Top'" in message, message
        assert f"batch #{low} 'Low'" in message, message
        assert f"{low} -> {mid} -> {top}" in message, message
        # And the store is unchanged: no half-applied cycle.
        with store.transaction() as tx:
            assert tx.groups.get(top).parent_id is None


def test_a_group_cannot_parent_itself(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _make(store, "epic", "Alone")
        with store.transaction() as tx:
            with pytest.raises(DependencyCycle, match=r"epic #1 'Alone' to itself"):
                tx.groups.set_parent(group_id, group_id)


def test_a_dependency_cycle_is_refused_across_three_groups(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        a = _make(store, "epic", "A")
        b = _make(store, "epic", "B")
        c = _make(store, "epic", "C")
        with store.transaction() as tx:
            tx.groups.add_dependency(
                dependent_group_id=a, needs_group_id=b,
                actor="t", at="2026-08-01T00:00:00Z")
            tx.groups.add_dependency(
                dependent_group_id=b, needs_group_id=c,
                actor="t", at="2026-08-01T00:00:00Z")
        with store.transaction() as tx:
            with pytest.raises(DependencyCycle) as caught:
                tx.groups.add_dependency(
                    dependent_group_id=c, needs_group_id=a,
                    actor="t", at="2026-08-01T00:00:00Z")
        message = str(caught.value)
        assert f"group #{a}" in message and f"group #{c}" in message, message
        assert "could ever start" in message, message


# --- the three faces of "empty" ---------------------------------------------

def test_a_transitively_empty_milestone_refuses_to_report_a_ratio(store_path):
    """Case 1. Two epics, both with zero tasks: `all([])` is vacuously true and
    `0/N` is a plausible 0%, so the only honest answer is to refuse."""
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        milestone = _make(store, "milestone", "Nothing planned")
        _make(store, "epic", "Empty one", parent=milestone)
        _make(store, "epic", "Empty two", parent=milestone)
        assert all([]) is True
        with store.transaction() as tx:
            with pytest.raises(EmptyGroup) as caught:
                tx.groups.progress(milestone)
        assert "0 member tasks anywhere in its subtree" in str(caught.value)
        assert "3 group(s)" in str(caught.value), (
            "the refusal should say how much subtree it examined, got "
            f"{caught.value}"
        )


def test_one_empty_child_withholds_completion_but_keeps_the_denominator(
        store_path):
    """Case 2. A named sub-collection nobody has filled is not evidence that
    there is no work left, so every known task landing is not completion."""
    _insert_tasks(store_path, [(501, "landed"), (502, "landed")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        milestone = _make(store, "milestone", "Release")
        done = _make(store, "epic", "Done", parent=milestone)
        unplanned = _make(store, "epic", "Not planned yet", parent=milestone)
        _add(store, done, 501, 502)
        with store.transaction() as tx:
            progress = tx.groups.progress(milestone)
        assert set(progress.member_task_ids) == {501, 502}
        assert set(progress.landed_task_ids) == {501, 502}
        assert progress.empty_group_ids == (unplanned,), (
            "the empty descendant must be NAMED, so the refusal is "
            f"discriminating; got {progress.empty_group_ids}"
        )
        assert progress.completed is False, (
            "every known task landed, but an empty sub-collection remains: "
            "reporting completion here is `all([])` one level up"
        )
        # ...and filling it flips completion, so the rule is not just "never".
        _insert_tasks(store_path, [(503, "landed")])
        _add(store, unplanned, 503)
        with store.transaction() as tx:
            after = tx.groups.progress(milestone)
        assert after.empty_group_ids == ()
        assert after.completed is True
        assert set(after.member_task_ids) == {501, 502, 503}


def test_a_fully_populated_tree_completes_exactly_as_v004_did(store_path):
    """Case 3. For a childless group the subtree rule IS v004's flat rule."""
    _insert_tasks(store_path, [(601, "landed")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        epic = _make(store, "epic", "Flat")
        _add(store, epic, 601)
        with store.transaction() as tx:
            progress = tx.groups.progress(epic)
        assert progress.completed is True
        assert progress.empty_group_ids == ()
        assert set(progress.member_task_ids) == {601}


# --- dependencies -----------------------------------------------------------

def test_task_to_task_edges_are_refused_and_pointed_at_depends(store_path):
    _insert_tasks(store_path, [(701, "open"), (702, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        with store.transaction() as tx:
            with pytest.raises(ValidationError) as caught:
                tx.groups.add_dependency(
                    dependent_task_id=701, needs_task_id=702,
                    actor="t", at="2026-08-01T00:00:00Z")
        assert "`depends`" in str(caught.value), str(caught.value)


def test_the_schema_itself_refuses_a_task_to_task_row(store_path):
    """#440 as a constraint, not a convention: even raw SQL cannot make a
    second home for an edge `depends` already owns."""
    conn = sqlite3.connect(store_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO task_group_dependency"
                " (dependent_task_id, needs_task_id, created_by, created_at)"
                " VALUES (1, 2, 't', 't')"
            )
    finally:
        conn.close()


def test_an_epic_requiring_a_milestone_blocks_every_task_inside_it(store_path):
    """Inherited blocking is what makes a GROUP-level dependency mean
    anything; without it the edge is decorative (#671)."""
    _insert_tasks(store_path, [(801, "open"), (802, "open"), (803, "open")])
    with open_database(task_system := task_store_spec(store_path),
                       access=Access.WRITE) as store:
        del task_system
        milestone = _make(store, "milestone", "Foundations")
        foundation_epic = _make(store, "epic", "Groundwork", parent=milestone)
        _add(store, foundation_epic, 801)
        blocked_epic = _make(store, "epic", "Depends on foundations")
        blocked_batch = _make(store, "batch", "Batch", parent=blocked_epic)
        _add(store, blocked_batch, 802, 803)
        with store.transaction() as tx:
            tx.groups.add_dependency(
                dependent_group_id=blocked_epic, needs_group_id=milestone,
                actor="t", at="2026-08-01T00:00:00Z")

        with store.transaction() as tx:
            # 802 sits two levels below the epic that carries the edge.
            blockers = tx.groups.blockers(task_id=802)
            assert [b.needs_id for b in blockers] == [milestone], blockers
            assert "not landed" in blockers[0].reason, blockers[0].reason
            assert tx.groups.ready_tasks(blocked_epic) == (), (
                "no task under a blocked epic may be a batch candidate"
            )
            assert set(tx.groups.ready_tasks(milestone)) == {801}

        # Landing the milestone's only task releases the whole blocked subtree.
        conn = sqlite3.connect(store_path)
        conn.execute("UPDATE task SET state='landed' WHERE id=801")
        conn.commit()
        conn.close()
        with store.transaction() as tx:
            assert tx.groups.blockers(task_id=802) == ()
            assert set(tx.groups.ready_tasks(blocked_epic)) == {802, 803}


def test_an_empty_subgoal_inherits_ancestor_prerequisites_via_group_id(store_path):
    """A subgoal with ZERO member tasks still inherits its ancestors'
    prerequisites through blockers(group_id=...).

    This is the discriminating case for group-level inheritance: the task_id
    path cannot reach it at all, because there is no member task whose
    governing-group walk would carry the ancestor blocker. A green here is
    only meaningful while the subtree is genuinely empty, so that
    precondition is asserted in the same body (#900, #655's 'assert the
    precondition the check depends on' rule)."""
    _insert_tasks(store_path, [(801, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        prerequisite = _make(store, "milestone", "Unmet foundation")
        _add(store, prerequisite, 801)  # 801 open -> prerequisite is unmet
        # `parent` carries the edge and is an ANCESTOR of the empty subgoal.
        parent = _make(store, "epic", "Carries the edge")
        with store.transaction() as tx:
            tx.groups.add_dependency(
                dependent_group_id=parent, needs_group_id=prerequisite,
                actor="t", at="2026-08-01T00:00:00Z")
        # The subgoal under `parent` has no member tasks ANYWHERE in its
        # subtree — exactly the hole #890's renderer workaround could not
        # cover, because it inherits through member tasks.
        empty_subgoal = _make(store, "goal", "No tasks", parent=parent)

        with store.transaction() as tx:
            # Precondition: nothing in the subtree can carry the task_id path.
            with pytest.raises(EmptyGroup):
                tx.groups.progress(empty_subgoal)
            blockers = tx.groups.blockers(group_id=empty_subgoal)
            # The ancestor blocker is reported with the ANCESTOR as the
            # dependent (symmetric with the task path, which records the
            # governing group — not the task — as the dependent).
            assert [(b.dependent_id, b.needs_id) for b in blockers] == [
                (parent, prerequisite)
            ], blockers
            assert "not landed" in blockers[0].reason, blockers[0].reason


def test_a_required_group_with_no_tasks_is_unmet_never_satisfied(store_path):
    _insert_tasks(store_path, [(901, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        blocked = _make(store, "epic", "Blocked")
        _add(store, blocked, 901)
        hollow = _make(store, "milestone", "Nothing in it")
        with store.transaction() as tx:
            tx.groups.add_dependency(
                dependent_group_id=blocked, needs_group_id=hollow,
                actor="t", at="2026-08-01T00:00:00Z")
        with store.transaction() as tx:
            blockers = tx.groups.blockers(group_id=blocked)
            assert [b.needs_id for b in blockers] == [hollow], blockers
            assert "holds no tasks" in blockers[0].reason
            assert tx.groups.ready_tasks(blocked) == (), (
                "an empty prerequisite must not vacuously release its dependents"
            )


def test_readiness_reads_v001_depends_for_task_to_task_edges(store_path):
    """The 23 live `depends` rows participate without being moved (#440)."""
    _insert_tasks(store_path, [(911, "open"), (912, "open")])
    conn = sqlite3.connect(store_path)
    conn.execute("INSERT INTO depends (task, needs) VALUES (912, 911)")
    conn.commit()
    conn.close()
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        epic = _make(store, "epic", "Both tasks")
        _add(store, epic, 911, 912)
        with store.transaction() as tx:
            assert set(tx.groups.ready_tasks(epic)) == {911}, (
                "912 needs 911, which is still open"
            )
            blockers = tx.groups.blockers(task_id=912)
            assert [(b.needs_kind, b.needs_id) for b in blockers] == [
                ("task", 911)
            ], blockers


def test_a_duplicate_edge_is_idempotent_not_a_second_row(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        a = _make(store, "epic", "A")
        b = _make(store, "epic", "B")
        with store.transaction() as tx:
            first, status = tx.groups.add_dependency(
                dependent_group_id=a, needs_group_id=b,
                actor="t", at="2026-08-01T00:00:00Z")
            assert status == "recorded"
        with store.transaction() as tx:
            again, status = tx.groups.add_dependency(
                dependent_group_id=a, needs_group_id=b,
                actor="t", at="2026-08-01T00:00:00Z")
        assert (again, status) == (first, "unchanged")


# --- migration --------------------------------------------------------------

def _roll_back_the_ladder_above_v005(conn):
    """Undo every step above v005 so a v005 rollback sees a genuine v5 store.

    Each version removes what it added, so this is not optional bookkeeping:
    v008 owns ``kind='goal'``, and until v008's downgrade has removed it,
    v005's downgrade correctly refuses it as a kind v004 cannot express.
    v007 has no production downgrade because #584's settings are shared user
    data; these fixtures never write one, so only that empty shape is dropped.
    """
    v010_posture_history.downgrade(conn)
    v009_goal_bypass.downgrade(conn)
    v008_goals.downgrade(conn)
    conn.execute("DROP TABLE user_setting")
    conn.execute("UPDATE meta SET value='6' WHERE key='schema_version'")


def _v004_store(path):
    """A genuine v4 store: built through the ladder, then rolled BACK to v4.

    Setting `schema_version='4'` on a current file would not do — the tables
    would still be v5-shaped, and the 4->5 step would fail on `already exists`
    rather than exercising the real upgrade.
    """
    with open_database(task_store_spec(path), access=Access.WRITE) as store:
        with store.transaction():
            pass
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN")
        _roll_back_the_ladder_above_v005(conn)
        v005_hierarchy.downgrade(conn)
        conn.execute("COMMIT")
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0] == "4"
    finally:
        conn.close()
    return path


def test_v005_preserves_tasks_members_triggers_and_the_id_sequence(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    _v004_store(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO task (id,state,title,body,priority,type,origin,blocked_on)"
        " VALUES (11,'open','t','b','P2',NULL,'loop',NULL)")
    conn.execute(
        "INSERT INTO task_group (id,kind,title,created_by,created_at)"
        " VALUES (4,'epic','Kept','t','t')")
    conn.execute(
        "INSERT INTO task_group (id,kind,title,created_by,created_at)"
        " VALUES (8,'lane','Deleted later','t','t')")
    conn.execute("DELETE FROM task_group WHERE id=8")
    conn.execute(
        "INSERT INTO task_group_member (group_id,task_id,added_by,added_at)"
        " VALUES (4,11,'t','t')")
    conn.execute(
        "INSERT INTO task_group_trigger"
        " (group_id,event,task_title,task_priority,task_type,created_by,created_at)"
        " VALUES (4,'completed','review','P2','task','t','t')")
    conn.execute("UPDATE meta SET value='4' WHERE key='schema_version'")
    conn.commit()
    before_tasks = conn.execute("SELECT * FROM task ORDER BY id").fetchall()
    conn.close()

    # Re-open through the canonical path: the ladder runs 4 through current.
    with open_database(task_store_spec(path), access=Access.WRITE) as store:
        with store.transaction():
            pass

    after = sqlite3.connect(path)
    try:
        assert after.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0] == str(SCHEMA_VERSION), (
            "the v4 fixture must migrate through the schema authority's current "
            f"version {SCHEMA_VERSION}"
        )
        assert after.execute("SELECT * FROM task ORDER BY id").fetchall() == \
            before_tasks, "v005 must not rewrite a single task row"
        assert after.execute(
            "SELECT group_id, task_id FROM task_group_member"
        ).fetchall() == [(4, 11)], "membership must survive the rebuild"
        assert after.execute(
            "SELECT group_id, task_title FROM task_group_trigger"
        ).fetchall() == [(4, "review")], "triggers must survive the rebuild"
        assert after.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='task_group'"
        ).fetchone()[0] == 8, (
            "the AUTOINCREMENT high-water must survive, or a deleted group id "
            "is reissued and old membership silently re-attaches"
        )
        assert after.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        after.close()


def test_downgrade_refuses_to_discard_nesting_or_dependencies(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    with open_database(task_store_spec(path), access=Access.WRITE) as store:
        parent = _make(store, "milestone", "Parent")
        _make(store, "epic", "Child", parent=parent)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")
    try:
        version_before = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        with pytest.raises(SchemaMismatch) as caught:
            v005_hierarchy.downgrade(conn)
        assert "nested task_group rows=1" in str(caught.value), caught.value
        conn.execute("ROLLBACK")
        version_after = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert version_after == version_before, (
            "a refused downgrade must not move the version: "
            f"before={version_before!r}, after={version_after!r}"
        )
    finally:
        conn.close()


def test_downgrade_restores_the_v004_shape_when_nothing_would_be_lost(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    with open_database(task_store_spec(path), access=Access.WRITE) as store:
        with store.transaction():
            pass
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO task (id,state,title,body,priority,type,origin,blocked_on)"
        " VALUES (21,'open','t','b','P2',NULL,'loop',NULL)")
    conn.execute(
        "INSERT INTO task_group (id,kind,title,created_by,created_at)"
        " VALUES (2,'epic','Flat','t','t')")
    conn.execute(
        "INSERT INTO task_group_member (group_id,task_id,added_by,added_at)"
        " VALUES (2,21,'t','t')")
    conn.commit()
    conn.execute("BEGIN")
    _roll_back_the_ladder_above_v005(conn)
    v005_hierarchy.downgrade(conn)
    conn.execute("COMMIT")
    try:
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0] == "4"
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(task_group)")
        }
        assert "parent_id" not in columns
        assert conn.execute(
            "SELECT group_id, task_id FROM task_group_member"
        ).fetchall() == [(2, 21)], "a rollback must keep membership"
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='task_group_dependency'"
        ).fetchone() is None
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


# --- CLI --------------------------------------------------------------------

def _cli(store_path, capsys, *argv):
    rc = ledger_cli.main([
        "groups", *argv, "--ledger", str(store_path.parent / "tasks.md")
    ])
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_cli_builds_and_renders_a_three_level_tree(store_path, capsys):
    assert _cli(store_path, capsys, "create", "milestone", "M")[0] == 0
    assert _cli(store_path, capsys, "create", "epic", "E", "--parent", "1")[0] == 0
    assert _cli(store_path, capsys, "create", "batch", "B", "--parent", "2")[0] == 0
    rc, out, err = _cli(store_path, capsys, "tree")
    assert rc == 0, err
    assert out.splitlines() == [
        "#1 milestone M", "  #2 epic E", "    #3 batch B",
    ], out


def test_cli_define_kind_then_create_with_it(store_path, capsys):
    rc, out, err = _cli(store_path, capsys, "define-kind", "initiative")
    assert rc == 0 and "defined" in out, (out, err)
    rc, out, err = _cli(store_path, capsys, "create", "initiative", "Top")
    assert rc == 0, err
    rc, out, _ = _cli(store_path, capsys, "kinds")
    assert "initiative" in out


def test_cli_refuses_a_parent_cycle_with_a_nonzero_exit(store_path, capsys):
    _cli(store_path, capsys, "create", "milestone", "M")
    _cli(store_path, capsys, "create", "epic", "E", "--parent", "1")
    rc, out, err = _cli(store_path, capsys, "set-parent", "1", "--parent", "2")
    assert rc == 2, (rc, out)
    assert "cycle" in err, err


def test_cli_ready_lists_the_candidate_pool_not_a_batch(store_path, capsys):
    _insert_tasks(store_path, [(1001, "open"), (1002, "landed")])
    _cli(store_path, capsys, "create", "epic", "E")
    _cli(store_path, capsys, "add-task", "1", "1001")
    _cli(store_path, capsys, "add-task", "1", "1002")
    rc, out, err = _cli(store_path, capsys, "ready", "1", "--json")
    assert rc == 0, err
    assert out.strip() == "[1001]", out


def test_cli_blockers_exits_nonzero_while_blocked(store_path, capsys):
    _insert_tasks(store_path, [(1101, "open")])
    _cli(store_path, capsys, "create", "epic", "Blocked")
    _cli(store_path, capsys, "add-task", "1", "1101")
    _cli(store_path, capsys, "create", "milestone", "Prereq")
    _insert_tasks(store_path, [(1102, "open")])
    _cli(store_path, capsys, "add-task", "2", "1102")
    rc, out, err = _cli(
        store_path, capsys, "require", "--group", "1", "--needs-group", "2")
    assert rc == 0, err
    rc, out, err = _cli(store_path, capsys, "blockers", "--group", "1")
    assert rc == 2, (rc, out)
    assert "group #1 needs group #2" in out, out
