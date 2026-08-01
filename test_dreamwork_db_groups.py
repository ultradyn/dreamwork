"""First-class task-group records, exact membership, and progress (#824)."""

from __future__ import annotations

import sqlite3

import pytest

from dreamwork_db import Access, ValidationError, open_database
from dreamwork_db.groups import EmptyGroup
from dreamwork_db.tasks import task_store_spec


@pytest.fixture
def store_path(tmp_path):
    path = tmp_path / "ledger.sqlite3"
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


def test_equal_size_wrong_membership_cannot_false_green(store_path):
    """Direction 2(a): task 102 swapped for 104 keeps count three."""
    _insert_tasks(store_path, [(101, "landed"), (102, "open"),
                               (103, "landed"), (104, "open")])
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store)
        _add(store, group_id, 101, 103, 104)
        with store.transaction() as tx:
            actual = tx.groups.progress(group_id).member_task_ids

    with pytest.raises(AssertionError, match=r"task 102.*task 104"):
        assert actual == (101, 102, 103), (
            f"epic #{group_id} membership lost task 102 and gained task 104; "
            f"actual membership is {actual}"
        )


def test_empty_group_cannot_report_zero_or_complete(store_path):
    """Direction 2(b): no denominator means the computation did not judge."""
    with open_database(task_store_spec(store_path), access=Access.WRITE) as store:
        group_id = _create_group(store, kind="lane", title="No tasks yet")
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
        with pytest.raises(ValidationError, match=r"lane.*epic.*milestone"):
            _create_group(store, kind="squad")
