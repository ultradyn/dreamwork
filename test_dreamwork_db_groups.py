"""First-class task-group records, exact membership, and progress (#824)."""

from __future__ import annotations

import json
import sqlite3

import pytest

from dreamwork_db import Access, NotFound, ValidationError, open_database
from dreamwork_db.groups import EmptyGroup
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


def _create_group(store, *, kind="epic", title="Store grouping"):
    with store.transaction() as tx:
        return tx.groups.create(
            kind=kind, title=title, description="group description",
            actor="test", at="2026-08-01T00:00:00Z",
        )


def _add(store, group_id, *task_ids):
    for task_id in task_ids:
        with store.transaction() as tx:
            tx.groups.add_task(
                group_id, task_id, actor="test", at="2026-08-01T00:00:01Z"
            )


def test_lanes_epics_and_milestones_are_first_class_records(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        ids = [
            _create_group(store, kind="lane", title="Storage lane"),
            _create_group(store, kind="epic", title="Task grouping"),
            _create_group(store, kind="milestone", title="Release one"),
        ]
        with store.transaction() as tx:
            groups = tx.groups.list()

    assert ids == [1, 2, 3]
    assert [(group.id, group.kind, group.title) for group in groups] == [
        (1, "lane", "Storage lane"),
        (2, "epic", "Task grouping"),
        (3, "milestone", "Release one"),
    ]


def test_progress_names_exact_task_membership_not_only_counts(store_path):
    _insert_tasks(store_path, [(101, "landed"), (102, "open"),
                               (103, "landed"), (104, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store)
        _add(store, group_id, 101, 102, 103)
        with store.transaction() as tx:
            progress = tx.groups.progress(group_id)

    # These expected identities are literal fixture facts, not produced by the
    # same membership helper as the subject (#820's self-comparison trap).
    assert progress.member_task_ids == (101, 102, 103), (
        f"epic #{group_id} has wrong task membership: "
        f"expected tasks (101, 102, 103), got {progress.member_task_ids}"
    )
    assert progress.landed_task_ids == (101, 103), (
        f"epic #{group_id} has wrong landed membership: "
        f"expected tasks (101, 103), got {progress.landed_task_ids}"
    )
    assert (progress.completed_count, progress.total_count, progress.completed) \
        == (2, 3, False)


def test_add_task_dry_run_resolves_disposition_without_writing(store_path):
    _insert_tasks(store_path, [(105, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store)
        with store.transaction() as tx:
            status = tx.groups.add_task(
                group_id, 105, actor="test", at="2026-08-01T00:00:01Z",
                apply=False,
            )

    assert status == "added"
    conn = sqlite3.connect(store_path)
    try:
        membership_count = conn.execute(
            "SELECT COUNT(*) FROM task_group_member"
        ).fetchone()[0]
    finally:
        conn.close()
    assert membership_count == 0, (
        "a dry-run disposition must not create membership")


def test_equal_size_wrong_membership_cannot_false_green(store_path):
    """Direction 2(a): task 102 swapped for 104 keeps count three."""
    _insert_tasks(store_path, [(101, "landed"), (102, "open"),
                               (103, "landed"), (104, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store)
        _add(store, group_id, 101, 103, 104)
        with store.transaction() as tx:
            actual = tx.groups.progress(group_id).member_task_ids

    # The two demonstrated false-green shapes both pass on this broken input:
    # same cardinality, and an "expected" set derived from the subject itself.
    assert len(actual) == 3
    derived_expected = set(actual)
    assert set(actual) == derived_expected
    with pytest.raises(AssertionError, match=r"task 102.*task 104"):
        assert actual == (101, 102, 103), (
            f"epic #{group_id} membership lost task 102 and gained task 104; "
            f"actual membership is {actual}"
        )


def test_empty_group_cannot_report_zero_or_complete(store_path):
    """Direction 2(b): no denominator means the computation did not judge."""
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store, kind="lane", title="No tasks yet")
        # Both plausible naive formulas confidently answer an empty population.
        assert all([]) is True
        assert (0 / 1) == 0
        with store.transaction() as tx:
            with pytest.raises(
                EmptyGroup,
                match=r"lane #1 'No tasks yet'.*0 member tasks",
            ):
                tx.groups.progress(group_id)
        with store.transaction() as tx:
            with pytest.raises(EmptyGroup, match=r"0 member tasks"):
                tx.groups.ready_triggers(group_id)


def test_completion_is_derived_from_durable_task_state(store_path):
    _insert_tasks(store_path, [(201, "landed"), (202, "landed")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store, kind="lane", title="Durable lane")
        _add(store, group_id, 201, 202)
        with store.transaction() as tx:
            progress = tx.groups.progress(group_id)

    assert progress.member_task_ids == (201, 202)
    assert progress.landed_task_ids == (201, 202)
    assert progress.completed is True


def test_completion_trigger_is_inert_until_group_completes(store_path):
    _insert_tasks(store_path, [(301, "landed"), (302, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store, kind="epic", title="Reviewable epic")
        _add(store, group_id, 301, 302)
        with store.transaction() as tx:
            trigger_id, disposition = tx.groups.register_completion_task(
                group_id, title="Review epic: Reviewable epic", priority="P1",
                task_type="task", actor="test", at="2026-08-01T00:00:02Z",
            )
        assert (trigger_id, disposition) == (1, "registered")
        with store.transaction() as tx:
            assert tx.groups.ready_triggers(group_id) == ()

    # Land through the canonical task repository. The grouping repository only
    # reads the transition; it does not file or mutate another task.
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        with store.transaction() as tx:
            tx.tasks.land(302, note="completed", actor="test")
        with store.transaction() as tx:
            ready = tx.groups.ready_triggers(group_id)
            records = tx.tasks.records()

    assert [(item.id, item.group_id, item.task_title) for item in ready] == [
        (1, group_id, "Review epic: Reviewable epic")
    ]
    assert [record["id"] for record in records] == [301, 302], (
        "reading a ready lifecycle trigger must not auto-file into the ledger"
    )


def test_unknown_group_kind_is_named_before_sql(store_path):
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        # #841 moved the vocabulary from an inline CHECK into
        # `task_group_kind`, so the refusal quotes the DEFINED kinds (sorted)
        # rather than a Python literal.
        with pytest.raises(
            ValidationError,
            match=r"unknown group kind 'squad'.*epic.*lane.*milestone",
        ):
            _create_group(store, kind="squad")


def _remove(store, group_id, task_id, *, why="dependency-not-membership"):
    with store.transaction() as tx:
        return tx.groups.remove_task(
            group_id, task_id, actor="test", at="2026-08-01T00:00:02Z",
            why=why,
        )


def _member_rows(path, group_id):
    conn = sqlite3.connect(path)
    try:
        return [
            int(row[0]) for row in conn.execute(
                "SELECT task_id FROM task_group_member"
                " WHERE group_id = ? ORDER BY task_id", (group_id,)
            ).fetchall()
        ]
    finally:
        conn.close()


def _audit_events(path, task_id):
    """Read the chained task_event log for one task — the audit home."""
    conn = sqlite3.connect(path)
    try:
        return [
            {"cause": row[0], "actor": row[1], "detail": row[2]}
            for row in conn.execute(
                "SELECT cause, actor, detail FROM task_event"
                " WHERE task_id = ? ORDER BY ordinal", (task_id,)
            ).fetchall()
        ]
    finally:
        conn.close()


def test_remove_task_drops_membership_and_reduces_denominator(store_path):
    """#1037: removing a member shrinks both the membership set and the
    progress denominator. Asserts the actual consequence (total_count) rather
    than the return code — a no-op success passes a return-code check."""
    _insert_tasks(store_path, [(601, "landed"), (602, "open"),
                               (603, "landed")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store, kind="goal", title="Removable goal")
        _add(store, group_id, 601, 602, 603)
        with store.transaction() as tx:
            before = tx.groups.progress(group_id)
        status = _remove(store, group_id, 602)
        with store.transaction() as tx:
            after = tx.groups.progress(group_id)

    assert status == "removed", f"remove_task returned {status!r}, expected removed"
    # Precondition asserted at runtime, not a literal: three were added.
    assert before.total_count == 3, (
        f"precondition broken: expected 3 members before removal, "
        f"got {before.total_count}")
    assert before.member_task_ids == (601, 602, 603)
    assert after.total_count == 2, (
        f"denominator did not shrink: expected 2 after removing 602, "
        f"got {after.total_count}")
    assert after.member_task_ids == (601, 603), (
        f"removed task 602 still present in membership: {after.member_task_ids}")
    # The membership row is GONE — the designed property (hard delete, not a
    # tombstone). Asserting this specifically distinguishes the choice.
    assert _member_rows(store_path, group_id) == [601, 603], (
        "the membership row for task 602 should be hard-deleted")


def test_remove_task_records_auditable_event_readable_back(store_path):
    """#1037 auditability: after a removal a reader can still discover the
    task was once a member and on whose judgement it left. Reads the chained
    event log back — an audit trail nobody can read is not an audit trail."""
    _insert_tasks(store_path, [(611, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store, kind="epic", title="Audited epic")
        _add(store, group_id, 611)
        status = _remove(
            store, group_id, 611, why="re-scoped: dependency not membership",
        )

    assert status == "removed"
    # Read the audit trail back directly from the chained event log.
    events = _audit_events(store_path, 611)
    assert len(events) >= 1, (
        f"removal must append an audit event, found {len(events)}")
    detail = events[-1]
    assert detail["cause"] == "reconciled"
    assert detail["actor"] == "test", (
        f"audit event must name who removed it; got actor={detail['actor']!r}")
    assert str(group_id) in detail["detail"], (
        f"audit event must name which group: {detail['detail']!r}")
    assert "dependency not membership" in detail["detail"], (
        f"audit event must carry the stated reason: {detail['detail']!r}")


def test_remove_task_refuses_non_member_not_silent_noop(store_path):
    """#1037: a no-op success is indistinguishable from a removal that worked.
    Removing a non-member must be a clear refusal, because that is exactly
    where a silent no-op hides."""
    _insert_tasks(store_path, [(621, "open"), (622, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store, kind="epic", title="Selective epic")
        _add(store, group_id, 621)  # 622 is NOT a member
        with pytest.raises(NotFound, match=r"not a member.*must not read as success"):
            with store.transaction() as tx:
                tx.groups.remove_task(
                    group_id, 622, actor="test",
                    at="2026-08-01T00:00:02Z", why="never belonged",
                )
    # The refused removal left membership untouched.
    assert _member_rows(store_path, group_id) == [621]


def test_remove_task_refuses_missing_group(store_path):
    """#1037: removing from a group that does not exist must refuse, not
    silently succeed."""
    _insert_tasks(store_path, [(631, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        with pytest.raises(NotFound, match=r"no task group #999"):
            with store.transaction() as tx:
                tx.groups.remove_task(
                    999, 631, actor="test",
                    at="2026-08-01T00:00:02Z", why="no such group",
                )


def test_remove_task_dry_run_resolves_without_writing(store_path):
    _insert_tasks(store_path, [(641, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store)
        _add(store, group_id, 641)
        with store.transaction() as tx:
            status = tx.groups.remove_task(
                group_id, 641, actor="test", at="2026-08-01T00:00:02Z",
                why="dry run", apply=False,
            )

    assert status == "removed"
    assert _member_rows(store_path, group_id) == [641], (
        "a dry-run removal must not delete the membership row")


def _cli(store_path, capsys, *argv):
    rc = ledger_cli.main([
        "groups", *argv, "--ledger", str(store_path.parent / "tasks.md")
    ])
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_groups_cli_exposes_exact_membership_and_progress(store_path, capsys):
    _insert_tasks(store_path, [(401, "landed"), (402, "open")])
    rc, out, err = _cli(store_path, capsys, "create", "epic", "CLI epic")
    assert rc == 0 and "created epic #1" in out
    for task_id in (401, 402):
        rc, out, err = _cli(store_path, capsys, "add-task", "1", str(task_id))
        assert rc == 0, f"failed adding task #{task_id}: {err}"

    rc, out, err = _cli(store_path, capsys, "get", "1", "--json")
    assert rc == 0, err
    record = json.loads(out.splitlines()[0])
    assert record["progress"]["member_task_ids"] == [401, 402], (
        f"epic #1 CLI returned wrong task membership: {record['progress']}"
    )
    assert record["progress"]["landed_task_ids"] == [401]
    assert record["progress"]["completed_count"] == 1
    assert record["progress"]["total_count"] == 2


def test_groups_cli_empty_progress_is_a_nonzero_did_not_judge(store_path, capsys):
    rc, out, err = _cli(store_path, capsys, "create", "lane", "Empty lane")
    assert rc == 0, err
    rc, out, err = _cli(store_path, capsys, "get", "1")
    assert rc == 2
    assert "progress: DID NOT JUDGE" in out
    assert "0 member tasks" in out


def test_groups_cli_registers_inert_trigger_without_filing_task(store_path, capsys):
    _insert_tasks(store_path, [(501, "landed")])
    _cli(store_path, capsys, "create", "milestone", "Release")
    _cli(store_path, capsys, "add-task", "1", "501")
    rc, out, err = _cli(
        store_path, capsys, "add-trigger", "1", "Review release",
        "--priority", "P1",
    )
    assert rc == 0, err
    assert "inert; no task filed" in out
    conn = sqlite3.connect(store_path)
    try:
        task_ids = [row[0] for row in conn.execute("SELECT id FROM task")]
    finally:
        conn.close()
    assert task_ids == [501], "adding a trigger must not auto-file into task"
