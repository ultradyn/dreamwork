"""Tests for the #645 increment 9 CLI unit — questions/reviews verbs.

Three things this suite proves, and each test names what it would catch:

1. **The refusal is the increment.** A mutating question verb invoked
   pre-watermark REFUSES and names the cutover command — so no second
   writer path exists (design §446).
2. **The positive case succeeds.** With the watermark set, the same verb
   performs the real transition. A guard never observed letting anything
   through has not been shown to be a guard (#755).
3. **Reviews register/link work pre-watermark.** They write the review
   tables, not the question tables, so they create no second question-
   writer path and are deliberately on the other side of the refusal line.

Direction 1 red-proof injects the real defect (remove the watermark check)
and watches a test red on a DISCRIMINATING message — one that says a pre-
watermark mutation was accepted, not a bare exit-code mismatch.  Direction
2 constructs the case where the verb is broken (so it refuses for the wrong
reason) and shows the positive case still exposes it.
"""

from __future__ import annotations

import datetime
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Make the worktree root importable so `import dev.ledger` / `import watch` work.
import os
_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dreamwork_db import Access, Conflict, NotFound, ValidationError, open_database
from dreamwork_db.questions import (
    QuestionRepository,
    question_store_spec,
    questions_cut_over,
    QUESTIONS_WATERMARK_KEY,
)
from dreamwork_db.reviews import (
    ReviewRepository,
    canonical_review_path,
    split_link_target,
)


# ─── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def scratch_store():
    """A fresh empty store with the full schema, cleaned up after.

    Mirrors the test_dreamwork_db_import fixture: first WRITE open creates
    the schema through the migration ladder.  Tests are exempt from the
    no-raw-connect guard — their purpose is to corrupt and tamper, which
    is what setting a watermark or asserting a refusal requires.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.sqlite3"
        with open_database(question_store_spec(path), access=Access.WRITE) as db:
            with db.transaction():
                pass  # trigger schema creation
        yield path


def _set_watermark(path: str) -> None:
    """Set the questions cutover watermark via raw SQL (test-only)."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (QUESTIONS_WATERMARK_KEY, "2026-08-01T00:00:00+00:00"))
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ─── watermark check ────────────────────────────────────────────────────────

class TestWatermarkCheck:
    """The precondition the refusal gate depends on."""

    def test_fresh_store_is_not_cut_over(self, scratch_store):
        """A store with no watermark row returns False.

        This is the DEFAULT — the refusal fires on a fresh store. A test
        that relies on the refusal must not also set the watermark, or the
        refusal is for the wrong reason.
        """
        with open_database(question_store_spec(scratch_store),
                           access=Access.READ) as db:
            assert questions_cut_over(db) is False

    def test_watermarked_store_is_cut_over(self, scratch_store):
        """A store with the watermark row returns True.

        This is the POSITIVE case — the verb must succeed. A guard that
        has never been observed letting anything through is not a guard.
        """
        _set_watermark(str(scratch_store))
        with open_database(question_store_spec(scratch_store),
                           access=Access.READ) as db:
            assert questions_cut_over(db) is True


# ─── mutating question verbs: refuse pre-watermark, succeed post ───────────

class TestQuestionRefusal:
    """Direction 1 and 2 of the red-proof for the refusal."""

    def test_post_refuses_pre_watermark(self, scratch_store):
        """post refuses and names the cutover command.

        Direction 1: this is the test that goes red if you remove the
        watermark check. The assertion is on a DISCRIMINATING message —
        it checks that a pre-watermark mutation was REFUSED (not accepted),
        not a bare exit code.
        """
        rc, out, err = _run_cli("questions-post", scratch_store,
                       ["a question title", "--body-file", "-"],
                       stdin="the body")
        assert rc == 2, "pre-watermark post must refuse (exit 2)"
        assert "refusing" in err, (
            "the refusal message must say 'refusing' — a bare exit code "
            "is indistinguishable from a verb that is broken")
        assert "cutover" in err.lower(), (
            "the refusal must name the cutover command so the reader "
            "knows what to run")
        # The verb must NOT have written: no question row exists.
        n = _question_count(scratch_store)
        assert n == 0, (
            f"pre-watermark post wrote {n} question(s) — the refusal "
            f"must prevent the write, not just report it")

    def test_post_succeeds_post_watermark(self, scratch_store):
        """With the watermark set, post SUCCEEDS and creates a row.

        Direction 2: this is the test that goes red if the verb is broken
        (unreachable, misspelled, or the watermark is never checked). A
        refusal that fires because nothing works proves nothing (#671).
        """
        _set_watermark(str(scratch_store))
        rc, out, err = _run_cli("questions-post", scratch_store,
                       ["posted via CLI", "--body-file", "-", "--priority", "P1"],
                       stdin="the body text")
        assert rc == 0, (
            "post-watermark post must succeed (exit 0); a refusal that "
            f"fires because the verb is broken is not a guard. stderr: {err}")
        n = _question_count(scratch_store)
        assert n == 1, (
            f"post-watermark post should have created exactly 1 question, "
            f"found {n}")

    def test_answer_refuses_pre_watermark(self, scratch_store):
        rc, out, err = _run_cli("questions-answer", scratch_store,
                       ["1", "--body-file", "-"], stdin="an answer")
        assert rc == 2
        assert "refusing" in err
        # No message row written.
        assert _message_count(scratch_store) == 0

    def test_answer_succeeds_post_watermark(self, scratch_store):
        _set_watermark(str(scratch_store))
        _post_question(scratch_store, "to be answered", "body")
        rc, out, err = _run_cli("questions-answer", scratch_store,
                       ["1", "--body-file", "-"], stdin="the answer")
        assert rc == 0
        assert _message_count(scratch_store) == 1

    def test_comment_refuses_pre_watermark(self, scratch_store):
        rc, out, err = _run_cli("questions-comment", scratch_store,
                       ["1", "--body-file", "-"], stdin="a note")
        assert rc == 2
        assert "refusing" in err

    def test_fold_refuses_pre_watermark(self, scratch_store):
        rc, out, err = _run_cli("questions-fold", scratch_store,
                       ["1", "--why", "because"])
        assert rc == 2
        assert "refusing" in err

    def test_retitle_refuses_pre_watermark(self, scratch_store):
        rc, out, err = _run_cli("questions-retitle", scratch_store,
                       ["1", "new title", "--why", "because", "--revision", "1"])
        assert rc == 2
        assert "refusing" in err


# ─── state transitions succeed post-watermark ──────────────────────────────

class TestPostWatermarkTransitions:
    """The real transitions the CLI performs when authorised."""

    def test_post_creates_unanswered_question(self, scratch_store):
        _set_watermark(str(scratch_store))
        rc, out, err = _run_cli("questions-post", scratch_store,
                       ["new question", "--body-file", "-", "--priority", "P2"],
                       stdin="body here")
        assert rc == 0
        q = _read_question(scratch_store, 1)
        assert q["status"] == "unanswered"
        assert q["title"] == "new question"
        assert q["priority"] == "P2"

    def test_answer_advances_to_answered_pending_fold(self, scratch_store):
        _set_watermark(str(scratch_store))
        _post_question(scratch_store, "to answer", "body")
        rc, out, err = _run_cli("questions-answer", scratch_store,
                       ["1", "--body-file", "-"], stdin="the answer")
        assert rc == 0
        q = _read_question(scratch_store, 1)
        assert q["status"] == "answered_pending_fold"
        assert _message_count(scratch_store) == 1

    def test_comment_does_not_change_status(self, scratch_store):
        _set_watermark(str(scratch_store))
        _post_question(scratch_store, "to comment", "body")
        rc, out, err = _run_cli("questions-comment", scratch_store,
                       ["1", "--body-file", "-"], stdin="a note")
        assert rc == 0
        q = _read_question(scratch_store, 1)
        assert q["status"] == "unanswered", (
            "a comment annotates; it does not resolve")
        assert _message_count(scratch_store) == 1

    def test_fold_requires_an_answer(self, scratch_store):
        _set_watermark(str(scratch_store))
        _post_question(scratch_store, "no answer yet", "body")
        rc, out, err = _run_cli("questions-fold", scratch_store,
                       ["1", "--why", "folded"])
        assert rc == 2, "fold must refuse on a question with no answer"
        assert "no answer" in err.lower()

    def test_fold_advances_to_answered(self, scratch_store):
        _set_watermark(str(scratch_store))
        _post_question(scratch_store, "to fold", "body")
        _run_cli("questions-answer", scratch_store,
                 ["1", "--body-file", "-"], stdin="the answer")
        rc, out, err = _run_cli("questions-fold", scratch_store,
                       ["1", "--why", "resolved"])
        assert rc == 0
        q = _read_question(scratch_store, 1)
        assert q["status"] == "answered"

    def test_retitle_compare_and_swap(self, scratch_store):
        _set_watermark(str(scratch_store))
        _post_question(scratch_store, "old title", "body")
        rc, out, err = _run_cli("questions-retitle", scratch_store,
                       ["1", "new title", "--why", "clarity", "--revision", "1"])
        assert rc == 0
        q = _read_question(scratch_store, 1)
        assert q["title"] == "new title"
        assert q["revision"] == 2

    def test_retitle_revision_mismatch_refuses(self, scratch_store):
        _set_watermark(str(scratch_store))
        _post_question(scratch_store, "old title", "body")
        rc, out, err = _run_cli("questions-retitle", scratch_store,
                       ["1", "new title", "--why", "x", "--revision", "99"])
        assert rc == 2
        assert "revision" in err.lower()


# ─── reviews register/link: allowed pre-watermark ──────────────────────────

class TestReviewsRegisterLink:
    """Reviews write the review tables, not the question tables — no refusal."""

    def test_register_creates_review_file(self, scratch_store, tmp_path):
        """register works pre-watermark (no question-table write)."""
        dw = _make_dw(tmp_path, scratch_store)
        _make_review_file(dw, "design.html", "<html>content</html>")
        rc, out, err = _run_cli_dw("reviews-register", dw, ["design.html"])
        assert rc == 0, (
            "reviews register must succeed pre-watermark — it writes the "
            "review tables, not the question tables")
        rev = _read_review(scratch_store, "design.html")
        assert rev is not None
        assert rev["registered_by"] == "coordinator"

    def test_register_is_idempotent(self, scratch_store, tmp_path):
        dw = _make_dw(tmp_path, scratch_store)
        _make_review_file(dw, "design.html", "<html>content</html>")
        _run_cli_dw("reviews-register", dw, ["design.html"])
        rc, out, err = _run_cli_dw("reviews-register", dw, ["design.html"])
        assert rc == 0
        assert "unchanged" in out

    def test_link_to_task(self, scratch_store, tmp_path):
        dw = _make_dw(tmp_path, scratch_store)
        _create_task(scratch_store, 645)
        _make_review_file(dw, "design.html", "<html>x</html>")
        _run_cli_dw("reviews-register", dw, ["design.html"])
        rc, out, err = _run_cli_dw("reviews-link", dw,
                         ["design.html", "--task", "645:related"])
        assert rc == 0
        links = _read_links(scratch_store, "design.html")
        assert len(links) == 1
        assert links[0]["link_kind"] == "related"
        assert links[0]["task_id"] == 645

    def test_link_blocking_kind(self, scratch_store, tmp_path):
        dw = _make_dw(tmp_path, scratch_store)
        _create_task(scratch_store, 100)
        _make_review_file(dw, "design.html", "<html>x</html>")
        _run_cli_dw("reviews-register", dw, ["design.html"])
        rc, out, err = _run_cli_dw("reviews-link", dw,
                         ["design.html", "--task", "100:blocking"])
        assert rc == 0
        links = _read_links(scratch_store, "design.html")
        assert links[0]["link_kind"] == "blocking"

    def test_link_to_issue(self, scratch_store, tmp_path):
        dw = _make_dw(tmp_path, scratch_store)
        _make_review_file(dw, "design.html", "<html>x</html>")
        _run_cli_dw("reviews-register", dw, ["design.html"])
        rc, out, err = _run_cli_dw("reviews-link", dw,
                         ["design.html",
                          "--issue", "github:owner/repo#5:related"])
        assert rc == 0
        links = _read_links(scratch_store, "design.html")
        assert links[0]["issue_id"] == 1

    def test_link_unregistered_review_refuses(self, scratch_store, tmp_path):
        dw = _make_dw(tmp_path, scratch_store)
        rc, out, err = _run_cli_dw("reviews-link", dw,
                         ["missing.html", "--task", "1:related"])
        assert rc == 1
        assert "register" in err.lower()


# ─── repository-level unit tests (the verbs delegate to these) ─────────────

class TestQuestionRepository:
    """Direct repository calls for the transitions the CLI exposes."""

    def test_post_and_answer(self, scratch_store):
        _set_watermark(str(scratch_store))
        at = _now()
        with open_database(question_store_spec(scratch_store),
                           access=Access.WRITE) as db:
            with db.transaction() as tx:
                qid = tx.questions.post(
                    title="repo test", body_markdown="body",
                    actor="test", at=at)
            assert qid == 1
            with db.transaction() as tx:
                tx.questions.answer(qid, body_markdown="ans",
                                    author="watch", at=at)
        q = _read_question(scratch_store, qid)
        assert q["status"] == "answered_pending_fold"

    def test_fold_without_answer_refuses(self, scratch_store):
        _set_watermark(str(scratch_store))
        at = _now()
        with open_database(question_store_spec(scratch_store),
                           access=Access.WRITE) as db:
            with db.transaction() as tx:
                qid = tx.questions.post(
                    title="no answer", body_markdown="b",
                    actor="test", at=at)
            with pytest.raises(ValidationError, match="no answer"):
                with db.transaction() as tx:
                    tx.questions.fold(qid, why="x", actor="t", at=at)

    def test_retitle_cas_mismatch(self, scratch_store):
        _set_watermark(str(scratch_store))
        at = _now()
        with open_database(question_store_spec(scratch_store),
                           access=Access.WRITE) as db:
            with db.transaction() as tx:
                qid = tx.questions.post(
                    title="t", body_markdown="b", actor="t", at=at)
            with pytest.raises(Conflict, match="revision"):
                with db.transaction() as tx:
                    tx.questions.retitle(
                        qid, title="t2", why="x",
                        expected_revision=99, actor="t", at=at)

    def test_retitle_unknown_question(self, scratch_store):
        _set_watermark(str(scratch_store))
        at = _now()
        with open_database(question_store_spec(scratch_store),
                           access=Access.WRITE) as db:
            with pytest.raises(NotFound):
                with db.transaction() as tx:
                    tx.questions.retitle(
                        999, title="t", why="x",
                        expected_revision=1, actor="t", at=at)


class TestReviewRepository:
    """Direct repository calls for review register/link."""

    def test_register_and_get(self, scratch_store):
        at = _now()
        with open_database(question_store_spec(scratch_store),
                           access=Access.WRITE) as db:
            with db.transaction() as tx:
                rid, disp = tx.reviews.register(
                    "design.html", b"<html>x</html>", actor="t", at=at)
            assert disp == "registered"
            assert rid == 1
        with open_database(question_store_spec(scratch_store),
                           access=Access.READ) as db:
            rev = db.reviews.get_by_path("design.html")
        assert rev is not None
        assert rev.path == "design.html"

    def test_register_refresh(self, scratch_store):
        at = _now()
        with open_database(question_store_spec(scratch_store),
                           access=Access.WRITE) as db:
            with db.transaction() as tx:
                rid1, d1 = tx.reviews.register(
                    "a.html", b"v1", actor="t", at=at)
            with db.transaction() as tx:
                rid2, d2 = tx.reviews.register(
                    "a.html", b"v2", actor="t", at=at)
        assert rid1 == rid2
        assert d1 == "registered"
        assert d2 == "refreshed"

    def test_link_idempotent(self, scratch_store):
        at = _now()
        _create_task(scratch_store, 5)
        with open_database(question_store_spec(scratch_store),
                           access=Access.WRITE) as db:
            with db.transaction() as tx:
                tx.reviews.register("a.html", b"x", actor="t", at=at)
            with db.transaction() as tx:
                lid1, d1 = tx.reviews.link(
                    "a.html", kind="related", task_id=5, actor="t", at=at)
            with db.transaction() as tx:
                lid2, d2 = tx.reviews.link(
                    "a.html", kind="related", task_id=5, actor="t", at=at)
        assert lid1 == lid2
        assert d1 == "linked"
        assert d2 == "unchanged"


# ─── path/link parsing ─────────────────────────────────────────────────────

class TestPathValidation:
    def test_canonical_simple(self):
        assert canonical_review_path("design.html") == "design.html"

    def test_canonical_strips_prefix(self):
        assert canonical_review_path(".dreamwork/review/design.html") == "design.html"
        assert canonical_review_path("review/design.html") == "design.html"

    def test_canonical_rejects_nested(self):
        with pytest.raises(ValidationError, match="single root-level"):
            canonical_review_path("sub/dir.html")

    def test_canonical_rejects_dotdot(self):
        with pytest.raises(ValidationError, match=r"\.\."):
            canonical_review_path("../escape.html")

    def test_canonical_rejects_non_html(self):
        with pytest.raises(ValidationError, match="html"):
            canonical_review_path("file.txt")


class TestLinkParsing:
    def test_split_simple(self):
        assert split_link_target("645:related") == ("645", "related")

    def test_split_issue_with_colon(self):
        ref, kind = split_link_target("github:owner/repo#5:related")
        assert ref == "github:owner/repo#5"
        assert kind == "related"

    def test_split_bad_kind(self):
        with pytest.raises(ValidationError):
            split_link_target("1:wrong")


# ─── helpers ───────────────────────────────────────────────────────────────

def _run_cli(cmd, store_path, argv, stdin=None):
    """Invoke a ledger verb against a scratch store via subprocess.

    Uses the WORKTREE's dev/ledger.py (not the skill-dir symlink), so it
    runs the code under test, not the unfixed main checkout.  Returns
    ``(rc, stdout, stderr)`` so tests can assert on the message content,
    not just the exit code.
    """
    ledger = str(Path(store_path).parent / "tasks.md")
    full = [sys.executable, "dev/ledger.py", cmd] + argv + ["--ledger", ledger]
    proc = subprocess.run(
        full, capture_output=True, text=True, input=stdin,
        cwd=_ROOT, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def _run_cli_dw(cmd, dw_dir, argv):
    """Invoke a verb against a .dreamwork dir. Returns ``(rc, out, err)``."""
    ledger = str(Path(dw_dir) / "tasks.md")
    full = [sys.executable, "dev/ledger.py", cmd] + argv + ["--ledger", ledger]
    proc = subprocess.run(
        full, capture_output=True, text=True, input=None,
        cwd=_ROOT, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def _question_count(store_path) -> int:
    conn = sqlite3.connect(str(store_path))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM question").fetchone()[0])
    finally:
        conn.close()


def _message_count(store_path) -> int:
    conn = sqlite3.connect(str(store_path))
    try:
        return int(conn.execute(
            "SELECT COUNT(*) FROM question_message").fetchone()[0])
    finally:
        conn.close()


def _read_question(store_path, qid) -> dict:
    conn = sqlite3.connect(str(store_path))
    try:
        row = conn.execute(
            "SELECT id, status, title, priority, revision"
            " FROM question WHERE id = ?", (qid,)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "status": row[1], "title": row[2],
                "priority": row[3], "revision": row[4]}
    finally:
        conn.close()


def _read_review(store_path, name) -> dict | None:
    conn = sqlite3.connect(str(store_path))
    try:
        row = conn.execute(
            "SELECT path, registered_by FROM review_file WHERE path = ?",
            (name,)).fetchone()
        if row is None:
            return None
        return {"path": row[0], "registered_by": row[1]}
    finally:
        conn.close()


def _read_links(store_path, name) -> list[dict]:
    conn = sqlite3.connect(str(store_path))
    try:
        rows = conn.execute(
            "SELECT rl.link_kind, rl.task_id, rl.issue_id, rl.question_id"
            " FROM review_link rl JOIN review_file rf ON rl.review_id = rf.id"
            " WHERE rf.path = ?", (name,)).fetchall()
        return [{"link_kind": r[0], "task_id": r[1], "issue_id": r[2],
                 "question_id": r[3]} for r in rows]
    finally:
        conn.close()


def _post_question(store_path, title, body):
    """Helper: post a question via the CLI (assumes watermark is set)."""
    _run_cli("questions-post", store_path,
             [title, "--body-file", "-"], stdin=body)


def _create_task(store_path, task_id):
    """Insert a task row so review_link FKs are satisfied (test-only)."""
    conn = sqlite3.connect(str(store_path))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO task"
            " (id, state, title, body, priority, priority_uncertain,"
            " origin, body_digest)"
            " VALUES (?, 'open', ?, '', NULL, 0, 'loop', '')",
            (task_id, f"task {task_id}"))
        conn.commit()
    finally:
        conn.close()


def _make_dw(tmp_path, store_path):
    """Create a .dreamwork dir with the store symlinked in and a tasks.md."""
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text("")
    # Symlink the store so both the CLI and the raw read see the same DB.
    (dw / "ledger.sqlite3").symlink_to(store_path)
    return dw


def _make_review_file(dw_dir, name, content):
    review_dir = dw_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / name).write_text(content)
