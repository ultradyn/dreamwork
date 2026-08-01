"""One canonical store composition serves tasks, questions, and reviews."""

from __future__ import annotations

from dreamwork_db import Access, open_database
from dreamwork_db.questions import question_store_spec
from dreamwork_db.store import dreamwork_store_spec
from dreamwork_db.tasks import task_store_spec


def test_domain_named_specs_delegate_to_one_complete_store_definition(tmp_path):
    path = tmp_path / "ledger.sqlite3"

    canonical = dreamwork_store_spec(path)
    task_compat = task_store_spec(path)
    question_compat = question_store_spec(path)

    for label, spec in (
        ("canonical", canonical),
        ("task compatibility facade", task_compat),
        ("question compatibility facade", question_compat),
    ):
        assert tuple(spec.repositories) == ("tasks", "questions", "reviews"), (
            f"{label} describes a partial or differently ordered store: "
            f"{tuple(spec.repositories)!r}"
        )
        assert spec.initializer is canonical.initializer, (
            f"{label} drifted to a second schema ladder"
        )


def test_domain_named_builders_call_the_canonical_composer(monkeypatch, tmp_path):
    """Equal duplicate specs are still two truths; bind actual delegation."""

    from dreamwork_db import store

    sentinel = object()
    calls = []

    def canonical(path):
        calls.append(path)
        return sentinel

    monkeypatch.setattr(store, "dreamwork_store_spec", canonical)
    path = tmp_path / "ledger.sqlite3"

    assert task_store_spec(path) is sentinel
    assert question_store_spec(path) is sentinel
    assert calls == [path, path], (
        "domain builders reproduced an equal-looking StoreSpec instead of "
        "delegating to the canonical store composer"
    )


def test_task_and_question_paths_share_one_handle_and_transaction(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    spec = dreamwork_store_spec(path)

    with open_database(spec, access=Access.WRITE) as db:
        with db.transaction() as tx:
            task_id = tx.tasks.file(
                "existing task path", "task body", actor="test",
                at="2026-08-01T00:00:00+00:00",
            )
            question_id = tx.questions.post(
                title="new question path",
                body_markdown="question body",
                actor="test",
                at="2026-08-01T00:00:01+00:00",
            )

    with open_database(spec, access=Access.READ) as db:
        tasks = db.tasks.records()
        questions = db.questions.snapshot().questions

    assert [row["id"] for row in tasks] == [task_id]
    assert [row.id for row in questions] == [question_id]
    assert tasks[0]["title"] == "existing task path"
    assert questions[0].title == "new question path"
