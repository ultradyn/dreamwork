"""Goal schema and repository contract for task #888."""

from __future__ import annotations

import importlib
import json
import sqlite3

import pytest

from dreamwork_db import (
    Access, NotFound, SchemaMismatch, ValidationError, open_database,
)
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
        assert version == "9", (
            "migrate.py must advance the ordered ladder through v009_goal_bypass; "
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
        assert "bypassed_by" in {
            row[1] for row in conn.execute("PRAGMA table_info(goal_claim)")
        }
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
    conn.execute(
        "UPDATE meta SET value=? WHERE key='current_goal_id'", (str(group_id),)
    )
    conn.commit()
    conn.execute("BEGIN")
    try:
        with pytest.raises(SchemaMismatch) as caught:
            v008_goals.downgrade(conn)
        message = str(caught.value)
        # Every fact v008 added is populated here, so every one must be named:
        # a rollback that lists three of six still discards the other three.
        for expected in (
            "goal_claim=1", "goal_verdict=1", "goal_state values=1",
            "goal_rank values=1", "current_goal_id pointer=1",
            "goal task_group rows=1",
        ):
            assert expected in message, (
                "v008_goals.downgrade must name every destructive population; "
                f"missing {expected!r} from {message!r}"
            )
    finally:
        conn.execute("ROLLBACK")
        conn.close()
    conn = sqlite3.connect(store_path)
    try:
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == ("9",), "a refused downgrade must not move the version"
        assert conn.execute("SELECT COUNT(*) FROM goal_claim").fetchone() == (1,)
    finally:
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


def test_a_real_v007_store_upgrades_in_place_to_v008(store_path):
    """Red on Migration(7, 8, v008_goals.upgrade), against the v007 target."""
    v008_goals = importlib.import_module(
        "dreamwork_db.migrations.v008_goals"
    )
    conn = sqlite3.connect(store_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")
    v008_goals.downgrade(conn)
    conn.execute(
        "INSERT INTO task_group (kind,title,created_by,created_at)"
        " VALUES ('epic','existing group','test','now')"
    )
    conn.execute(
        "INSERT INTO user_setting (userid,key,value)"
        " VALUES ('local','gfx.dither','false')"
    )
    conn.execute("COMMIT")
    conn.close()

    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        with db.transaction():
            pass

    conn = sqlite3.connect(store_path)
    try:
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == ("9",)
        assert conn.execute(
            "SELECT kind,title FROM task_group"
        ).fetchall() == [("epic", "existing group")], (
            "v007 -> v008 must preserve the existing group population"
        )
        assert conn.execute(
            "SELECT userid,key,value FROM user_setting"
        ).fetchall() == [("local", "gfx.dither", "false")], (
            "v007 -> v008 must preserve #584's user-setting rows"
        )
    finally:
        conn.close()


def test_v008_rows_upgrade_with_null_bypass_attribution(store_path):
    """v008 history remains panel history after the v009 additive migration."""
    v009 = importlib.import_module("dreamwork_db.migrations.v009_goal_bypass")
    conn = sqlite3.connect(store_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")
    v009.downgrade(conn)
    conn.execute(
        "INSERT INTO task_group (kind,title,created_by,created_at) "
        "VALUES ('goal','old','test','now')"
    )
    group_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO goal_claim "
        "(group_id,claimed_by,claimed_at,summary,details_sha,outcome,round) "
        "VALUES (?,?,?,?,?,'complete',1)",
        (group_id, "loop", "now", "panel", "details"),
    )
    conn.execute("COMMIT")
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        with db.transaction():
            pass
    conn = sqlite3.connect(store_path)
    try:
        assert conn.execute(
            "SELECT outcome,bypassed_by FROM goal_claim"
        ).fetchone() == ("complete", None)
    finally:
        conn.close()


def test_bypass_attribution_round_trips_and_downgrade_refuses(store_path):
    """The actor is distinct from the panel outcome and cannot be discarded."""
    v009 = importlib.import_module("dreamwork_db.migrations.v009_goal_bypass")
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Bypass")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="waived",
                base_sha=None, details_sha="details", round=1,
                outcome="complete", bypassed_by="principal",
            )
            assert claim.bypassed_by == "principal"
            assert tx.goals.claims(goal_id)[0].bypassed_by == "principal"
    conn = sqlite3.connect(store_path)
    conn.execute("BEGIN")
    try:
        with pytest.raises(SchemaMismatch, match=r"bypassed_by values=1"):
            v009.downgrade(conn)
    finally:
        conn.execute("ROLLBACK")
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
                if state == "complete":
                    tx.goals.append_claim(
                        goal_id, claimed_by="loop", claimed_at="now",
                        summary="panel complete", base_sha=None,
                        details_sha="details", round=1, outcome="complete",
                    )
                assert tx.goals.set_state(goal_id, state) == "changed"
        with db.transaction() as tx:
            assert tx.goals.state(goal_id) == "complete"
        with db.transaction() as tx:
            with pytest.raises(
                ValidationError, match=r"illegal goal state transition complete -> open"
            ):
                tx.goals.set_state(goal_id, "open")


def test_goal_cannot_be_completed_without_a_recorded_claim(store_path):
    """A bare state write must not erase panel-versus-bypass history."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Claim required")
        with db.transaction() as tx:
            with pytest.raises(
                ValidationError,
                match=r"cannot complete goal .* without a completed claim",
            ):
                tx.goals.set_state(goal_id, "complete")


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


def test_claim_all_open_refusal_uses_the_whole_goal_subtree(store_path):
    """Direct membership would answer the wrong question for nested goals."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        root = _goal(db, "Root")
        child = _goal(db, "Child", parent_id=root)
        with db.transaction() as tx:
            direct_open = tx.tasks.file("direct open", "body", actor="test", at="now")
            descendant_landed = tx.tasks.file(
                "descendant landed", "body", actor="test", at="now"
            )
            tx.tasks.land(descendant_landed, note="landed", actor="test")
            tx.groups.add_task(root, direct_open, actor="test", at="now")
            tx.groups.add_task(child, descendant_landed, actor="test", at="now")
            claim = tx.goals.append_claim(
                root, claimed_by="loop", claimed_at="now", summary="panel",
                base_sha=None, details_sha="details", round=1,
            )
            assert claim.group_id == root

        root2 = _goal(db, "Root 2")
        child2 = _goal(db, "Child 2", parent_id=root2)
        with db.transaction() as tx:
            direct_open = tx.tasks.file("direct open", "body", actor="test", at="now")
            descendant_open = tx.tasks.file(
                "descendant open", "body", actor="test", at="now"
            )
            tx.groups.add_task(root2, direct_open, actor="test", at="now")
            tx.groups.add_task(child2, descendant_open, actor="test", at="now")
            with pytest.raises(
                ValidationError,
                match=rf"cannot claim goal #{root2}: every member task is still open",
            ):
                tx.goals.append_claim(
                    root2, claimed_by="loop", claimed_at="now", summary="panel",
                    base_sha=None, details_sha="details", round=1,
                )


def test_rank_collisions_and_all_null_still_have_total_preorder(store_path):
    """Direction 2(5): red on GoalRepository.ranked_children's ORDER BY."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        root_a = _goal(db, "Root A")
        root_b = _goal(db, "Root B")
        root_c = _goal(db, "Root C")
        child_a = _goal(db, "Child A", parent_id=root_a)
        child_b = _goal(db, "Child B", parent_id=root_a)
        with db.transaction() as tx:
            tx.goals.set_rank(root_c, 5)
            tx.goals.set_rank(child_a, 7)
            tx.goals.set_rank(child_b, 7)
        with db.transaction() as tx:
            # Two preconditions this expectation depends on, derived rather
            # than assumed. The ranked root must hold the LATEST id, or plain
            # id order yields the same answer and NULL-last is never
            # exercised; the siblings must genuinely collide, or the tie is
            # never reached.
            assert root_c > root_a and root_c > root_b, (
                f"the ranked root must sort after the NULL roots by id: "
                f"{root_c} vs {(root_a, root_b)}"
            )
            assert tx.goals.rank(child_a) == tx.goals.rank(child_b) is not None, (
                "the sibling ranks must collide for the tie-break to decide"
            )
        # Ranked roots first, NULL roots last by id; colliding children by id.
        with db.transaction() as tx:
            assert tx.goals.preorder() == (
                root_c, root_a, child_a, child_b, root_b
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


#: Both-zero alone cannot tell ``or`` from ``and`` in the examined guard, and
#: the mixed rows are the dangerous ones: a panel that read three criteria and
#: zero members looks busy in every field a reader checks.
ZERO_EXAMINED = (
    {"criteria": 0, "members": 0},
    {"criteria": 3, "members": 0},
    {"criteria": 0, "members": 3},
)


def test_any_zero_examined_is_did_not_judge_not_a_pass(store_path):
    """Direction 2(1): red on append_verdict's examined precondition."""
    assert any(
        0 in case.values() and any(case.values()) for case in ZERO_EXAMINED
    ), (
        "ZERO_EXAMINED must contain a PARTIAL zero, or an `and` between the "
        "two counts passes this test while storing an unexamined population"
    )
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Non-vacuous")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="done",
                base_sha="abc", details_sha="def", round=1,
            )
        for examined in ZERO_EXAMINED:
            with db.transaction() as tx:
                with pytest.raises(
                    ValidationError,
                    match=(
                        r"DID NOT JUDGE.*criteria=%d.*members=%d"
                        % (examined["criteria"], examined["members"])
                    ),
                ):
                    tx.goals.append_verdict(
                        claim.id, lens="criteria", refuted=False, findings=[],
                        corroborated=[{"criterion": "C1", "sha": "abc"}],
                        examined=examined,
                    )
        with db.transaction() as tx:
            real = tx.goals.append_verdict(
                claim.id, lens="criteria", refuted=False, findings=[],
                corroborated=[{"criterion": "C1", "sha": "abc"}],
                examined={"criteria": 1, "members": 1},
            )
        assert real.refuted is False
        with db.transaction() as tx:
            assert len(tx.goals.verdicts(claim.id)) == 1, (
                "only the examined verdict may have been stored; a refused one "
                "that still landed is the vacuous pass this guard exists for"
            )


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
        # The mirror: an enumeration is the refuter's product, so a refutation
        # that found nothing to say is malformed for the same reason.
        with db.transaction() as tx:
            with pytest.raises(
                ValidationError, match=r"malformed refutation.*findings.*empty"
            ):
                tx.goals.append_verdict(
                    claim.id, lens="evidence", refuted=True, findings=[],
                    corroborated=[], examined={"criteria": 1, "members": 1},
                )
        with db.transaction() as tx:
            assert tx.goals.verdicts(claim.id) == (), (
                "neither malformed verdict may have reached the table"
            )


def test_a_malformed_verdict_row_is_refused_on_read(store_path):
    """Direction 2(2): red on GoalRepository.verdicts' stored-shape guards.

    ``append_verdict`` is not the only writer a real store will ever see — a
    hand-patched row, or a future writer, reaches the same table.  An uncited
    pass must not become a pass by having been written some other way.
    """
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Hand-patched")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="done",
                base_sha="abc", details_sha="def", round=1,
            )
    conn = sqlite3.connect(store_path)
    try:
        conn.execute(
            "INSERT INTO goal_verdict"
            " (claim_id,lens,refuted,findings,corroborated,examined)"
            " VALUES (?,'criteria',0,'[]','[]','{\"criteria\":2,\"members\":2}')",
            (claim.id,),
        )
        conn.commit()
        # The row is a well-formed PASS in every column the table constrains:
        # only the corroboration rule makes it malformed.
        assert conn.execute(
            "SELECT refuted, examined FROM goal_verdict"
        ).fetchone() == (0, '{"criteria":2,"members":2}'), (
            "the fixture must be an examined pass, or the read fails on the "
            "examined precondition instead of on the missing corroboration"
        )
    finally:
        conn.close()
    with open_database(dreamwork_store_spec(store_path), access=Access.READ) as db:
        with pytest.raises(
            SchemaMismatch, match=r"malformed pass with no corroboration"
        ):
            db.goals.verdicts(claim.id)


def test_the_pointer_makes_a_second_current_unrepresentable(store_path):
    """Direction 2(3): the design's claim, tested rather than restated.

    The mechanism is v001's ``meta.key TEXT PRIMARY KEY`` — v008 adds a row to
    a table that already refuses a second one.  A *dangling* pointer is still
    representable, so the second half asserts that it reads loudly.
    """
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Only current")
        with db.transaction() as tx:
            tx.goals.set_current_goal_id(goal_id)

    conn = sqlite3.connect(store_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match=r"meta\.key"):
            conn.execute(
                "INSERT INTO meta (key,value) VALUES ('current_goal_id','999')"
            )
        conn.rollback()
        assert conn.execute(
            "SELECT COUNT(*) FROM meta WHERE key='current_goal_id'"
        ).fetchone() == (1,)
        # Representable, and the point of the test: nothing stops the goal row
        # going away underneath a live pointer.
        conn.execute("DELETE FROM task_group WHERE id=?", (goal_id,))
        conn.commit()
    finally:
        conn.close()

    with open_database(dreamwork_store_spec(store_path), access=Access.READ) as db:
        with pytest.raises(NotFound, match=rf"no task group #{goal_id}"):
            db.goals.current_goal_id()


def test_every_claim_round_is_kept_with_its_verdicts(store_path):
    """Direction 2: goal_claim/goal_verdict are append-only across rounds.

    Round 2 must be able to read round 1's gaps, so round 1 has to survive
    round 2 being written — findings and all.
    """
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Two rounds")
        with db.transaction() as tx:
            first = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="t1", summary="round 1",
                base_sha=None, details_sha="d1", round=1, outcome="refuted",
            )
            tx.goals.append_verdict(
                first.id, lens="criteria", refuted=True,
                findings=["criterion 3 has no evidence"], corroborated=[],
                blocking="none", examined={"criteria": 3, "members": 2},
            )
        with db.transaction() as tx:
            second = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="t2", summary="round 2",
                base_sha="abc", details_sha="d2", round=2,
            )
        with db.transaction() as tx:
            assert tx.goals.claims(goal_id) == (first, second), (
                "a second round must append; round 1 is what round 2 reads"
            )
            round_one = tx.goals.verdicts(first.id)
            assert [v.findings for v in round_one] == [
                ("criterion 3 has no evidence",)
            ], "round 1's enumeration must survive round 2 verbatim"
            assert tx.goals.verdicts(second.id) == ()


def _append_panel_verdict(tx, claim_id, lens, *, refuted=False, findings=()):
    return tx.goals.append_verdict(
        claim_id, lens=lens, refuted=refuted,
        findings=list(findings),
        corroborated=[] if refuted else [{"criterion": "C1", "sha": lens}],
        examined={"criteria": 1, "members": 1},
    )


def test_claim_outcome_is_written_once_and_a_new_round_preserves_it(store_path):
    """Red on GoalRepository.resolve_claim's conditional UPDATE."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Settles once")
        with db.transaction() as tx:
            first = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="t1", summary="round 1",
                base_sha="abc", details_sha="d1", round=1,
            )
            settled = tx.goals.resolve_claim(first.id, "refuted")
            assert settled.outcome == "refuted"
            with pytest.raises(
                ValidationError,
                match=r"outcome is already 'refuted'; terminal outcomes are write-once",
            ):
                tx.goals.resolve_claim(first.id, "complete")
            second = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="t2", summary="round 2",
                base_sha="def", details_sha="d2", round=2,
            )
            assert tx.goals.claims(goal_id) == (settled, second)


def test_panel_requires_all_three_lenses_and_unanimity(store_path):
    """Red on finalize_panel's complete-lens set and any-refute reduction."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Three lenses")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="done",
                base_sha="abc", details_sha="d1", round=1,
            )
            _append_panel_verdict(tx, claim.id, "criteria")
            _append_panel_verdict(tx, claim.id, "evidence")
            with pytest.raises(
                ValidationError,
                match=r"PANEL INCOMPLETE.*missing lenses \('use',\).*FAIL CLOSED AND ASK HUMAN",
            ):
                tx.goals.finalize_panel(claim.id)
            assert tx.goals.claims(goal_id)[0].outcome is None
            _append_panel_verdict(tx, claim.id, "use")
            assert tx.goals.finalize_panel(claim.id).outcome == "complete"

        with db.transaction() as tx:
            refuted = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="later", summary="again",
                base_sha="def", details_sha="d2", round=2,
            )
            _append_panel_verdict(tx, refuted.id, "criteria")
            _append_panel_verdict(
                tx, refuted.id, "evidence", refuted=True,
                findings=("proof never reached the seam", "red run was green"),
            )
            _append_panel_verdict(tx, refuted.id, "use")
            assert tx.goals.finalize_panel(refuted.id).outcome == "refuted", (
                "one evidence refutation must sink the unanimous panel"
            )
            evidence = tx.goals.verdicts(refuted.id)[1]
            assert evidence.findings == (
                "proof never reached the seam", "red run was green"
            ), "the full enumeration is the product and must survive finalization"


def test_panel_cannot_all_clear_after_examining_zero_criteria(store_path):
    """Direction 2: three stored passes with a partial zero must not finalize."""
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        goal_id = _goal(db, "Vacuous panel")
        with db.transaction() as tx:
            claim = tx.goals.append_claim(
                goal_id, claimed_by="loop", claimed_at="now", summary="done",
                base_sha="abc", details_sha="d1", round=1,
            )
    conn = sqlite3.connect(store_path)
    try:
        for lens in ("criteria", "evidence", "use"):
            conn.execute(
                "INSERT INTO goal_verdict"
                " (claim_id,lens,refuted,findings,corroborated,examined)"
                " VALUES (?,?,0,'[]','[\"claimed evidence\"]',"
                " '{\"criteria\":0,\"members\":3}')",
                (claim.id, lens),
            )
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) FROM goal_verdict WHERE claim_id=? AND refuted=0",
            (claim.id,),
        ).fetchone() == (3,), "fixture must be a unanimous stored all-clear"
    finally:
        conn.close()
    with open_database(dreamwork_store_spec(store_path), access=Access.WRITE) as db:
        with db.transaction() as tx:
            with pytest.raises(
                ValidationError,
                match=r"DID NOT JUDGE.*criteria=0.*members=3",
            ):
                tx.goals.finalize_panel(claim.id)
            assert tx.goals.claims(goal_id)[0].outcome is None
