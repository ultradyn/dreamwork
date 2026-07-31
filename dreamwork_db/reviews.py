"""Review-file and typed-link repository (#645 increment 9).

A review file is a row whose logical key is its canonical path relative to
``.dreamwork/review/`` (a root-level ``.html`` artifact); a content hash is a
revision fact, not identity, so editing a review must never sever its links
(design §Schema).  A typed link connects one review to exactly one task,
issue or question and CARRIES ITS KIND — ``related`` or ``blocking`` — which
is what lets a "related tasks" list say which it is.

This module writes only the v3 ``review_file`` / ``issue`` / ``review_link``
tables.  It does NOT write the ``question`` table, so registering a review or
linking one creates no second writer path for ``questions.md`` — the
pre-cutover refusal (#645 increment 9) constrains mutating *question* verbs,
and ``reviews register``/``reviews link`` are deliberately on the other side
of that line (design §446: no steady-state dual read or dual write *for
questions*; reviews are a new domain with no legacy markdown writer to
conflict with).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from .core import NotFound, ValidationError


# ─── path validation ────────────────────────────────────────────────────────

def canonical_review_path(arg: str) -> str:
    """Canonicalise a review path argument to its root-level ``.html`` name.

    Accepts a review-relative name (``design.html``) or a repo-relative path
    (``.dreamwork/review/design.html``) and returns the canonical name stored
    as ``review_file.path``: a single root-level component under
    ``.dreamwork/review/``.  Validates per design §Schema: relative,
    non-empty, no ``..``, a single component, ending ``.html``.  ``PurePosixPath``
    is used because the stored path is a logical key, not a filesystem path —
    the canonical form must not depend on the host OS separator.
    """
    if not isinstance(arg, str) or not arg.strip():
        raise ValidationError(
            f"review path must be a non-empty string, got {arg!r}")
    p = PurePosixPath(arg)
    if p.is_absolute() or any(part == ".." for part in p.parts):
        raise ValidationError(
            f"review path must be relative with no '..': got {arg!r}")
    parts = [part for part in p.parts if part not in (".", "")]
    # Strip a leading .dreamwork/review/ or review/ prefix so callers may pass
    # either the repo-relative or review-relative form.
    if len(parts) >= 2 and parts[0] == ".dreamwork" and parts[1] == "review":
        parts = parts[2:]
    elif parts and parts[0] == "review":
        parts = parts[1:]
    if len(parts) != 1:
        raise ValidationError(
            f"review path must be a single root-level name under "
            f".dreamwork/review/ (got {arg!r}); nested paths are not "
            f"registerable review artifacts")
    name = parts[0]
    if not name.endswith(".html"):
        raise ValidationError(
            f"review path must end with '.html': got {arg!r}")
    return name


# ─── link-kind parsing ──────────────────────────────────────────────────────

_LINK_KINDS = ("related", "blocking")


def split_link_target(value: str) -> tuple[str, str]:
    """Split ``<ref>:<kind>`` into ``(ref, kind)`` on the LAST colon.

    ``rpartition`` takes the last colon so an issue ref that itself contains a
    colon parses correctly: ``github:owner/repo#5:related`` →
    ``('github:owner/repo#5', 'related')``.
    """
    ref, sep, kind = value.rpartition(":")
    if not sep:
        raise ValidationError(
            f"expected '<target>:<related|blocking>', got {value!r}")
    if kind not in _LINK_KINDS:
        raise ValidationError(
            f"link kind must be one of {_LINK_KINDS}, got {kind!r}")
    return ref, kind


def parse_issue_ref(ref: str) -> tuple[str, str, str]:
    """Split ``github:owner/repo#5`` into ``(tracker, repository, external_id)``."""
    tracker, sep, rest = ref.partition(":")
    if not sep or not tracker:
        raise ValidationError(
            f"issue ref must be '<tracker>:<repository>#<id>': got {ref!r}")
    repository, hsep, external_id = rest.rpartition("#")
    if not hsep or not repository or not external_id:
        raise ValidationError(
            f"issue ref must be '<tracker>:<repository>#<id>': got {ref!r}")
    return tracker, repository, external_id


# ─── read-back DTOs ─────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class StoredReview:
    """One ``review_file`` row read back from the store."""

    id: int
    path: str
    content_sha256: str
    size_bytes: int
    registered_at: str
    registered_by: str
    revision: int


@dataclass(frozen=True, slots=True)
class StoredLink:
    """One ``review_link`` row read back from the store."""

    id: int
    review_path: str
    link_kind: str
    task_id: int | None
    issue_id: int | None
    question_id: int | None
    decision: str | None


# ─── repository ─────────────────────────────────────────────────────────────

class ReviewRepository:
    """Review-file and typed-link writes over one handle-owned connection.

    Bound into the store spec alongside :class:`TaskRepository` and
    :class:`QuestionRepository`.  All writes require an active WRITE
    transaction (enforced by ``dreamwork_db.core``'s session).  Writes touch
    only ``review_file`` / ``issue`` / ``review_link`` — never ``question``.
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    # ── reads ──────────────────────────────────────────────────────────────

    def get_by_path(self, name: str) -> StoredReview | None:
        canonical = canonical_review_path(name)
        row = self._session.execute(
            "SELECT id, path, content_sha256, size_bytes,"
            " registered_at, registered_by, revision"
            " FROM review_file WHERE path = ?", (canonical,)
        ).fetchone()
        return _stored_review(row) if row else None

    def list_reviews(self) -> tuple[StoredReview, ...]:
        rows = self._session.execute(
            "SELECT id, path, content_sha256, size_bytes,"
            " registered_at, registered_by, revision"
            " FROM review_file ORDER BY path"
        ).fetchall()
        return tuple(_stored_review(r) for r in rows)

    def links(self, name: str) -> tuple[StoredLink, ...]:
        canonical = canonical_review_path(name)
        rows = self._session.execute(
            "SELECT rl.id, rf.path, rl.link_kind, rl.task_id,"
            " rl.issue_id, rl.question_id, rl.decision"
            " FROM review_link rl JOIN review_file rf ON rl.review_id = rf.id"
            " WHERE rf.path = ? ORDER BY rl.id", (canonical,)
        ).fetchall()
        return tuple(StoredLink(
            id=int(r[0]), review_path=r[1], link_kind=r[2],
            task_id=_int(r[3]), issue_id=_int(r[4]),
            question_id=_int(r[5]), decision=r[6],
        ) for r in rows)

    # ── writes ─────────────────────────────────────────────────────────────

    def register(
        self, name: str, content: bytes, *, actor: str, at: str,
    ) -> tuple[int, str]:
        """Register or refresh a review file; idempotent on same content.

        Returns ``(review_id, disposition)`` where disposition is
        ``'registered'`` (new), ``'unchanged'`` (same path + same hash —
        nothing written) or ``'refreshed'`` (same path + changed hash —
        revision bumped).  The caller supplies the EXACT bytes to hash; the
        integrity-critical rule (design §Schema) is that the stored hash
        covers those same bytes, so hashing lives here rather than at the
        caller.
        """
        canonical = canonical_review_path(name)
        sha = hashlib.sha256(content).hexdigest()
        size = len(content)
        existing = self._session.execute(
            "SELECT id, content_sha256 FROM review_file WHERE path = ?",
            (canonical,)
        ).fetchone()
        if existing is None:
            cur = self._session.execute(
                "INSERT INTO review_file"
                " (path, content_sha256, size_bytes, registered_at,"
                "  registered_by, revision)"
                " VALUES (?, ?, ?, ?, ?, 1)",
                (canonical, sha, size, at, actor))
            return int(cur.lastrowid), "registered"
        rid, old_sha = int(existing[0]), existing[1]
        if old_sha == sha:
            return rid, "unchanged"
        self._session.execute(
            "UPDATE review_file SET content_sha256 = ?, size_bytes = ?,"
            " revision = revision + 1 WHERE id = ?",
            (sha, size, rid))
        return rid, "refreshed"

    def link(
        self, name: str, *, kind: str,
        task_id: int | None = None, issue_ref: str | None = None,
        question_id: int | None = None, actor: str = "loop", at: str | None = None,
    ) -> tuple[int, str]:
        """Create a typed review link to exactly one task, issue or question.

        ``kind`` is ``'related'`` or ``'blocking'`` and is what a "related
        tasks" list shows beside each row.  Exactly one of ``task_id``,
        ``issue_ref`` or ``question_id`` must be set (the schema's CHECK
        enforces one target per link, and the repository states the same
        constraint before the INSERT so a misuse is named, not a traceback).
        Returns ``(link_id, disposition)``; disposition is ``'linked'`` (new)
        or ``'unchanged'`` (the exact link already exists).
        """
        if kind not in _LINK_KINDS:
            raise ValidationError(
                f"link kind must be one of {_LINK_KINDS}, got {kind!r}")
        targets = [t for t in (task_id, issue_ref, question_id)
                   if t is not None]
        if len(targets) != 1:
            raise ValidationError(
                "exactly one of task_id / issue_ref / question_id must be set "
                f"(got {len(targets)}); a review link has one target")
        review = self._session.execute(
            "SELECT id FROM review_file WHERE path = ?",
            (canonical_review_path(name),)
        ).fetchone()
        if review is None:
            raise NotFound(
                f"no registered review named {name!r}; register it first with"
                f" `reviews register`")
        review_id = int(review[0])
        issue_id = None
        if issue_ref is not None:
            tracker, repository, external_id = parse_issue_ref(issue_ref)
            issue_id = self._upsert_issue(tracker, repository, external_id)
        # Idempotent on the exact (review, target, kind) triple: report
        # 'unchanged' rather than erroring on the unique index.
        existing = self._existing_link(
            review_id, task_id=task_id, issue_id=issue_id,
            question_id=question_id)
        if existing is not None:
            return existing, "unchanged"
        cur = self._session.execute(
            "INSERT INTO review_link"
            " (review_id, link_kind, task_id, issue_id, question_id)"
            " VALUES (?, ?, ?, ?, ?)",
            (review_id, kind, task_id, issue_id, question_id))
        return int(cur.lastrowid), "linked"

    def _existing_link(
        self, review_id: int, *, task_id=None, issue_id=None, question_id=None,
    ) -> int | None:
        """The id of an existing link for this review+target, else None."""
        if task_id is not None:
            row = self._session.execute(
                "SELECT id FROM review_link WHERE review_id = ? AND task_id = ?",
                (review_id, task_id)).fetchone()
        elif issue_id is not None:
            row = self._session.execute(
                "SELECT id FROM review_link WHERE review_id = ? AND issue_id = ?",
                (review_id, issue_id)).fetchone()
        else:
            row = self._session.execute(
                "SELECT id FROM review_link WHERE review_id = ? AND question_id = ?",
                (review_id, question_id)).fetchone()
        return int(row[0]) if row else None

    def _upsert_issue(
        self, tracker: str, repository: str, external_id: str,
    ) -> int:
        existing = self._session.execute(
            "SELECT id FROM issue WHERE tracker = ? AND repository = ?"
            " AND external_id = ?",
            (tracker, repository, external_id)).fetchone()
        if existing is not None:
            return int(existing[0])
        cur = self._session.execute(
            "INSERT INTO issue (tracker, repository, external_id)"
            " VALUES (?, ?, ?)",
            (tracker, repository, external_id))
        return int(cur.lastrowid)


def _stored_review(row) -> StoredReview:
    return StoredReview(
        id=int(row[0]), path=row[1], content_sha256=row[2],
        size_bytes=int(row[3]), registered_at=row[4],
        registered_by=row[5], revision=int(row[6]),
    )


def _int(value) -> int | None:
    return int(value) if value is not None else None
