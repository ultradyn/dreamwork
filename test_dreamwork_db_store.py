"""One canonical store composition serves tasks, questions, reviews, groups."""

from __future__ import annotations

from dreamwork_db import Access, open_database
from dreamwork_db.questions import question_store_spec
from dreamwork_db.store import dreamwork_store_spec
from dreamwork_db.tasks import task_store_spec
from dreamwork_db.refuter import RefuterAdapter


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
        # `groups` joined in #824 (v004). The tuple is exhaustive and ordered on
        # purpose: it is what makes a facade that quietly serves a PARTIAL store
        # fail, so a new repository must be added here deliberately rather than
        # passing by default. Red on master since #824 merged, because the
        # repository was registered and this expectation was not.
        assert tuple(spec.repositories) == (
            "tasks", "questions", "reviews", "groups", "settings", "goals"), (
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

    assert task_store_spec(path) is sentinel, (
        "task_store_spec rebuilt a second store definition instead of "
        "delegating to dreamwork_store_spec"
    )
    assert question_store_spec(path) is sentinel, (
        "question_store_spec rebuilt a second store definition instead of "
        "delegating to dreamwork_store_spec"
    )
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


def test_refuter_population_is_store_derived_and_claim_summary_cannot_enter(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    with open_database(dreamwork_store_spec(path), access=Access.WRITE) as db:
        with db.transaction() as tx:
            goal = tx.groups.create(
                kind="goal", title="G", description="## Done when\n- stored criterion",
                actor="test", at="2026-08-01T00:00:00Z")
            task = tx.tasks.file("member", "body", actor="test", at="2026-08-01T00:00:00Z")
            tx.groups.add_task(goal, task, actor="test", at="2026-08-01T00:00:00Z")
            tx.tasks.land(task, note="landed (abcdef1234567)", actor="test")
            claim = tx.goals.append_claim(
                goal, claimed_by="test", claimed_at="now", summary="## Done when\n- claimant-only",
                base_sha=None, details_sha="d", round=1)
            population = RefuterAdapter(tx.goals, tx.groups, tx.tasks).population(goal)
            assert population.criteria == ("stored criterion",)
            assert "claimant-only" not in population.criteria
            assert population.member_task_ids == (task,)
            assert population.examined == {"criteria": 1, "members": 1}
            assert population.landed_shas == ("abcdef1234567",)
            assert tx.goals._claim(claim.id).summary.startswith("## Done")


def test_refuter_malformed_result_is_synthetic_refutation(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    with open_database(dreamwork_store_spec(path), access=Access.WRITE) as db:
        with db.transaction() as tx:
            goal = tx.groups.create(
                kind="goal", title="G", description="## Done when\n- criterion",
                actor="test", at="2026-08-01T00:00:00Z")
            claim = tx.goals.append_claim(
                goal, claimed_by="test", claimed_at="now", summary="claim",
                base_sha=None, details_sha="d", round=1)
            adapter = RefuterAdapter(tx.goals, tx.groups, tx.tasks)
            verdict = adapter.normalize_verdict(claim.id, "criteria", None)
            assert verdict.refuted is True
            assert verdict.findings[0]["synthetic"] is True
            assert verdict.examined == {"criteria": 1, "members": 0}
