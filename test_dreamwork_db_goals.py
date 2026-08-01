"""Goal schema and repository contract for task #888."""

from __future__ import annotations

import importlib
import json
import sqlite3

import pytest

from dreamwork_db import Access, SchemaMismatch, ValidationError, open_database
from dreamwork_db.store import dreamwork_store_spec


@pytest.fixture
def store_path(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    with open_database(dreamwork_store_spec(path), access=Access.WRITE) as db:
        with db.transaction():
            pass
    return path


def _goal(db, title, *, parent_id=None):
    with db.transaction() as tx:
        group_id = tx.groups.create(
            kind="goal", title=title, actor="test", at="2026-08-01T00:00:00Z",
            parent_id=parent_id,
        )
        tx.goals.set_state(group_id, "open")
    return group_id


def test_v008_upgrade_builds_the_decided_goal_shape(store_path):
    """Red on migrate.py:SCHEMA_VERSION/MIGRATIONS or v008_goals.upgrade."""
    conn = sqlite3.connect(store_path)
    try:
        version = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert version == "8", (
            "migrate.py must advance the ordered ladder through v008_goals; "
            f"stored schema_version was {version!r}"
        )
        assert conn.execute(
            "SELECT kind FROM task_group_kind WHERE kind='goal'"
        ).fetchone() == ("goal",), (
            "v008_goals.upgrade must seed kind='goal' in task_group_kind"
        )
        assert {
            row[1] for row in conn.execute("PRAGMA table_info(task_group)")
        } >= {"goal_state", "goal_rank"}, (
            "v008_goals.upgrade must add task_group.goal_state and goal_rank"
        )
        assert {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        } >= {"goal_state_kind", "goal_claim", "goal_verdict"}, (
            "v008_goals.upgrade must create all three decided goal tables"
        )
        assert conn.execute(
            "SELECT value FROM meta WHERE key='current_goal_id'"
        ).fetchone() == ("",), (
            "v008_goals.upgrade must create the single current-goal pointer"
        )
    finally:
        conn.close()


def test_v008_downgrade_names_every_nonempty_fact_before_discarding(store_path):
    """Red on v008_goals.downgrade's four destructive population counts."""
    v008_goals = importlib.import_module(
        "dreamwork_db.migrations.v008_goals"
    )
    conn = sqlite3.connect(store_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO task_group"
        " (kind,title,created_by,created_at,goal_state,goal_rank)"
        " VALUES ('goal','G','test','now','claimed',4)"
    )
    group_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO goal_claim"
        " (group_id,claimed_by,claimed_at,summary,details_sha,outcome,round)"
        " VALUES (?,?,?,?,?,'refuted',1)",
        (group_id, "test", "now", "claim", "details"),
    )
    claim_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO goal_verdict"
        " (claim_id,lens,refuted,findings,corroborated,examined)"
        " VALUES (?,?,?,?,?,?)",
        (claim_id, "criteria", 1, '["gap"]', "[]",
         '{"criteria":1,"members":1}'),
    )
    conn.commit()
    conn.execute("BEGIN")
    try:
        with pytest.raises(SchemaMismatch) as caught:
            v008_goals.downgrade(conn)
        message = str(caught.value)
        for expected in (
            "goal_claim=1", "goal_verdict=1", "goal_state values=1",
            "goal_rank values=1",
        ):
            assert expected in message, (
                "v008_goals.downgrade must name every destructive population; "
                f"missing {expected!r} from {message!r}"
            )
    finally:
        conn.execute("ROLLBACK")
        conn.close()


def test_v008_empty_downgrade_restores_v007_without_loss(store_path):
    """Red on v008_goals.downgrade's successful schema-removal branch."""
    v008_goals = importlib.import_module(
        "dreamwork_db.migrations.v008_goals"
    )
    conn = sqlite3.connect(store_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")
    v008_goals.downgrade(conn)
    conn.execute("COMMIT")
    try:
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == ("7",), (
            "v008_goals.downgrade must return the watermark to v007"
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(task_group)")
        }
        assert not ({"goal_state", "goal_rank"} & columns), (
            "v008_goals.downgrade must remove both v008 task_group columns"
        )
        assert conn.execute(
            "SELECT name FROM sqlite_master"
            " WHERE name IN ('goal_state_kind','goal_claim','goal_verdict')"
        ).fetchall() == [], (
            "v008_goals.downgrade must remove every v008-only table"
        )
    finally:
        conn.close()


def test_canonical_store_composes_the_one_goal_repository(store_path):
    """Red on store.py:dreamwork_store_spec repository composition."""
    spec = dreamwork_store_spec(store_path)
    assert tuple(spec.repositories)[-1] == "goals", (
        "dreamwork_store_spec must compose GoalRepository beside the existing "
        "repositories instead of creating another connection policy"
    )
    with open_database(spec, access=Access.READ) as db:
        assert db.goals.current_goal_id() is None


def test_current_goal_pointer_replaces_and_refuses_non_goals(store_path):
    """Red on GoalRepository.set_current_goal_id's kind='goal' guard."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        first = _goal(db, "First")
        second = _goal(db, "Second")
        with db.transaction() as tx:
            non_goal = tx.groups.create(
                kind="epic", title="Not a goal", actor="test", at="now"
            )
        with db.transaction() as tx:
            assert tx.goals.set_current_goal_id(first) == "set"
        with db.transaction() as tx:
            assert tx.goals.set_current_goal_id(second) == "set"
        with db.transaction() as tx:
            with pytest.raises(ValidationError, match=r"epic #3.*not a goal"):
                tx.goals.set_current_goal_id(non_goal)
        with db.transaction() as tx:
            assert tx.goals.current_goal_id() == second

    conn = sqlite3.connect(store_path)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM meta WHERE key='current_goal_id'"
        ).fetchone() == (1,), (
            "the meta pointer must make a stale second current unrepresentable"
        )
    finally:
        conn.close()


def test_goal_state_transitions_are_one_closed_graph(store_path):
    """Red on goals.py:LEGAL_STATE_TRANSITIONS and set_state."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Lifecycle")
        for state in ("claimed", "open", "blocked", "open", "complete"):
            with db.transaction() as tx:
                assert tx.goals.set_state(goal_id, state) == "changed"
        with db.transaction() as tx:
            assert tx.goals.state(goal_id) == "complete"
        with db.transaction() as tx:
            with pytest.raises(
                ValidationError, match=r"illegal goal state transition complete -> open"
            ):
                tx.goals.set_state(goal_id, "open")


def test_landed_members_do_not_derive_goal_complete(store_path):
    """Direction 2(4): red if GoalRepository.state derives from task state."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        with db.transaction() as tx:
            task_id = tx.tasks.file("member", "body", actor="test", at="now")
            tx.tasks.land(task_id, note="landed", actor="test")
        goal_id = _goal(db, "Panel owns completion")
        with db.transaction() as tx:
            tx.groups.add_task(goal_id, task_id, actor="test", at="now")
        with db.transaction() as tx:
            assert tx.groups.progress(goal_id).completed is True
            assert tx.goals.state(goal_id) == "open", (
                "GoalRepository.state must read task_group.goal_state; all landed "
                "members do not mean the panel completed the goal"
            )


def test_rank_collisions_and_all_null_still_have_total_preorder(store_path):
    """Direction 2(5): red on GoalRepository.preorder's id tie-break."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        root_a = _goal(db, "Root A")
        root_b = _goal(db, "Root B")
        child_a = _goal(db, "Child A", parent_id=root_a)
        child_b = _goal(db, "Child B", parent_id=root_a)
        with db.transaction() as tx:
            tx.goals.set_rank(child_a, 7)
            tx.goals.set_rank(child_b, 7)
        # Roots are all-NULL; children collide. Both ties resolve by durable id.
        with db.transaction() as tx:
            assert tx.goals.preorder() == (
                root_a, child_a, child_b, root_b
            ), "rank, NULL-last, then id must yield one deterministic total order"


def test_claim_and_verdict_append_round_trip_structured_evidence(store_path):
    """Red on GoalRepository.append_claim/append_verdict INSERT statements."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Evidence")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="done",
                base_sha=None, details_sha="details-sha", round=1,
            )
            verdict = tx.goals.append_verdict(
                claim.id, lens="criteria", refuted=False,
                findings=[], corroborated=[{"criterion": "C1", "sha": "abc"}],
                examined={"criteria": 1, "members": 2},
            )
        with db.transaction() as tx:
            assert tx.goals.claims(goal_id) == (claim,)
            assert tx.goals.verdicts(claim.id) == (verdict,)
        assert claim.base_sha is None
        assert verdict.corroborated == ({"criterion": "C1", "sha": "abc"},)
        assert verdict.examined == {"criteria": 1, "members": 2}


def test_zero_examined_is_did_not_judge_not_a_pass(store_path):
    """Direction 2(1): red on append_verdict's examined precondition."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Non-vacuous")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="done",
                base_sha="abc", details_sha="def", round=1,
            )
        with db.transaction() as tx:
            with pytest.raises(
                ValidationError,
                match=r"DID NOT JUDGE.*criteria=0.*members=0",
            ):
                tx.goals.append_verdict(
                    claim.id, lens="criteria", refuted=False, findings=[],
                    corroborated=[{"criterion": "C1", "sha": "abc"}],
                    examined={"criteria": 0, "members": 0},
                )
        with db.transaction() as tx:
            real = tx.goals.append_verdict(
                claim.id, lens="criteria", refuted=False, findings=[],
                corroborated=[{"criterion": "C1", "sha": "abc"}],
                examined={"criteria": 1, "members": 1},
            )
        assert real.refuted is False


def test_empty_corroborated_pass_is_malformed(store_path):
    """Direction 2(2): red on append_verdict's pass-evidence guard."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Cited pass")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="done",
                base_sha="abc", details_sha="def", round=1,
            )
        with db.transaction() as tx:
            with pytest.raises(
                ValidationError, match=r"malformed pass.*corroborated.*empty"
            ):
                tx.goals.append_verdict(
                    claim.id, lens="criteria", refuted=False, findings=[],
                    corroborated=[], examined={"criteria": 1, "members": 1},
                )
