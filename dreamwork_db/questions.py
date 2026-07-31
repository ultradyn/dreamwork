"""Import/verify unit for the questions migration (#645 increment 8).

Imports a :class:`~dreamwork_db.question_parse.QuestionManifest` into a
scratch SQLite store through ``dreamwork_db.core``'s one connection door,
reads it back through production SQL, and verifies field-for-field against
the source manifest.

Three things this module is, and one it is not:

1. **Idempotent import.** A second import of the same manifest reports every
   entry as ``unchanged`` — it does not rewrite, refresh or touch any row.
   A second import after the store drifted reports each difference as a
   named conflict and refuses to overwrite.  Repair-by-overwrite is what a
   migration must never do: it destroys the one thing a migration preserves,
   the ability to prove the destination matches the source.

2. **Independent verification.** :func:`verify_import` compares the parser's
   manifest against a DB snapshot read through raw SQL, without trusting the
   importer's own claims.  A manifest and a snapshot are two independently
   derived representations of the same data; the comparison is between them,
   not between the importer's input and its output.  That is the ``#759``
   standard: the verifier cannot certify what the importer produced by
   asking the importer whether it did a good job.

3. **Three outcomes, never two.** Per entry: ``unchanged``, ``conflict``
   (named, specific field), or ``cannot_tell`` (the verifier could not
   establish a correspondence).  ``#136``: "imported, no change" and "could
   not determine whether this differs" must not render identically.  A
   None-valued source field against a NULL column IS a match — both carry
   nothing — and is reported as ``unchanged`` for that field, not as
   cannot-tell.  Cannot-tell is the structural inability to compare, not an
   absence.

This module is NOT reachable from a live path.  It is scratch-only: the CLI
(increment 9) and the live cutover (increment 13) are what make it live.
Nothing here opens ``questions.md`` for writing, and nothing here touches
the production store.  The ``test_no_raw_connect`` guard enforces the
connection door.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core import StoreSpec, ValidationError
from .migrate import initialize_legacy_store
from .question_parse import QuestionManifest, QuestionEntry, Contribution
from .tasks import TaskRepository


PathLike = str | Path

# Priority lives in the title prefix: ``P1 · 2026-08-01 — title``.
_PRIORITY_RE = re.compile(r"\AP([0123])\s+·\s")

# Content fields compared for idempotence and verification.  Metadata fields
# (id, created_by, created_at, updated_at, revision, action_id) are
# store-internal: the source manifest does not carry them, so comparing them
# against the manifest is meaningless, and comparing them across imports
# would flag a timestamp the importer set once as a conflict on re-import.
QUESTION_CONTENT_FIELDS = (
    "status", "title", "body_markdown", "priority",
    "asked_at", "asked_precision",
)
MESSAGE_CONTENT_FIELDS = ("kind", "author", "body_markdown", "at")


# ─── read-back DTOs ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class StoredQuestion:
    """One ``question`` row read back from the store."""

    id: int
    status: str
    title: str
    body_markdown: str
    priority: str | None
    asked_at: str | None
    asked_precision: str
    created_by: str
    created_at: str
    updated_at: str
    revision: int


@dataclass(frozen=True, slots=True)
class StoredMessage:
    """One ``question_message`` row read back from the store."""

    id: int
    question_id: int
    kind: str
    author: str
    body_markdown: str
    at: str | None


@dataclass(frozen=True, slots=True)
class StoredSnapshot:
    """The complete read-back of questions and messages, in id order."""

    questions: tuple[StoredQuestion, ...]
    messages: tuple[StoredMessage, ...]


# ─── import result DTOs ────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class FieldDelta:
    """One field that differs between the source manifest and the store."""

    field: str
    manifest_value: Any
    stored_value: Any


@dataclass(frozen=True, slots=True)
class EntryOutcome:
    """The outcome of importing or verifying one manifest entry."""

    ordinal: int
    disposition: str            # 'inserted' | 'unchanged' | 'conflict' | 'cannot_tell'
    question_id: int | None
    deltas: tuple[FieldDelta, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportResult:
    """The aggregate result of an :meth:`QuestionRepository.import_manifest`."""

    entries: tuple[EntryOutcome, ...]
    extra_question_ids: tuple[int, ...]
    extra_message_ids: tuple[int, ...]

    @property
    def inserted(self) -> tuple[EntryOutcome, ...]:
        return tuple(e for e in self.entries if e.disposition == "inserted")

    @property
    def unchanged(self) -> tuple[EntryOutcome, ...]:
        return tuple(e for e in self.entries if e.disposition == "unchanged")

    @property
    def conflicts(self) -> tuple[EntryOutcome, ...]:
        return tuple(e for e in self.entries if e.disposition == "conflict")

    @property
    def cannot_tell(self) -> tuple[EntryOutcome, ...]:
        return tuple(e for e in self.entries if e.disposition == "cannot_tell")

    @property
    def ok(self) -> bool:
        """True when no conflicts or cannot-tell outcomes exist.

        Inserted and unchanged are both acceptable; conflicts and
        cannot-tell are not.  This does NOT mean "the store matches the
        source" — only :func:`verify_import` can assert that.
        """
        return not self.conflicts and not self.cannot_tell


# ─── verification result DTOs ──────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Field-for-field comparison between a source manifest and a snapshot.

    The verifier is INDEPENDENT of the importer: it reads the snapshot
    through raw SQL (via :meth:`QuestionRepository.snapshot`) and compares
    every content field against the manifest.  It does not consult the
    importer's :class:`ImportResult` — that result is the importer's claim
    about itself, and ``#759`` forbids self-certification.
    """

    question_count_manifest: int
    question_count_stored: int
    entries: tuple[EntryOutcome, ...]
    extra_question_ids: tuple[int, ...]
    missing_ordinals: tuple[int, ...]   # manifest entries with no stored counterpart
    denominator_source_bytes: int       # from the manifest; #671: zero is a refusal

    @property
    def matching(self) -> tuple[EntryOutcome, ...]:
        return tuple(e for e in self.entries if e.disposition == "unchanged")

    @property
    def conflicts(self) -> tuple[EntryOutcome, ...]:
        return tuple(e for e in self.entries if e.disposition == "conflict")

    @property
    def cannot_tell(self) -> tuple[EntryOutcome, ...]:
        return tuple(e for e in self.entries if e.disposition == "cannot_tell")

    @property
    def ok(self) -> bool:
        """True only when every manifest entry matches and nothing is extra.

        A zero-row destination is a REFUSAL (``#671``): ``ok`` is False and
        ``denominator_source_bytes > 0`` distinguishes "examined nothing"
        from "examined and matched".  An empty manifest over an empty store
        is a legitimate match.
        """
        if self.question_count_manifest > 0 and self.question_count_stored == 0:
            return False
        return (
            not self.conflicts
            and not self.cannot_tell
            and not self.missing_ordinals
            and not self.extra_question_ids
        )

    @property
    def empty_source_refusal(self) -> bool:
        """True when the source is non-empty but the store is empty.

        ``#671``: a verifier that examined nothing must not read as passing.
        This is distinct from a legitimately empty source over an empty
        store, which is a real match.
        """
        return (
            self.question_count_manifest > 0
            and self.question_count_stored == 0
        )


# ─── priority extraction ───────────────────────────────────────────────────

def extract_priority(title: str) -> str | None:
    """Extract ``P0``–``P3`` from a title prefix, or None when absent.

    This is a simple prefix scan — it is NOT the parser's grammar.  Both
    the importer and the verifier call this same function, but on DIFFERENT
    inputs: the importer calls it on the manifest title, the verifier calls
    it on the STORED title.  If the importer wrote the wrong title, the
    title field check catches that first; if it wrote the right title but
    the wrong priority column, the priority check catches the mismatch.
    """
    m = _PRIORITY_RE.match(title)
    return ("P" + m.group(1)) if m else None


# ─── repository ────────────────────────────────────────────────────────────

class QuestionRepository:
    """Question/message reads and writes over one handle-owned connection.

    Bound into a :class:`StoreSpec` alongside :class:`TaskRepository` by
    :func:`question_store_spec`.  All writes require an active WRITE
    transaction (enforced by ``dreamwork_db.core``'s session).
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    # ── reads ──────────────────────────────────────────────────────────────

    def snapshot(self) -> StoredSnapshot:
        """Read every question and message back in id order.

        This is the INDEPENDENT route the verifier uses: raw SQL selects,
        no importer logic, no manifest reference.  The importer writes
        through :meth:`import_manifest`; this reads what landed.  If the
        two disagree, the verifier catches it.
        """
        q_rows = self._session.execute(
            "SELECT id, status, title, body_markdown, priority,"
            " asked_at, asked_precision, created_by, created_at,"
            " updated_at, revision"
            " FROM question ORDER BY id"
        ).fetchall()
        questions = tuple(
            StoredQuestion(
                id=int(r[0]), status=r[1], title=r[2], body_markdown=r[3],
                priority=r[4], asked_at=r[5], asked_precision=r[6],
                created_by=r[7], created_at=r[8], updated_at=r[9],
                revision=int(r[10]),
            )
            for r in q_rows
        )
        m_rows = self._session.execute(
            "SELECT id, question_id, kind, author, body_markdown, at"
            " FROM question_message ORDER BY question_id, id"
        ).fetchall()
        messages = tuple(
            StoredMessage(
                id=int(r[0]), question_id=int(r[1]), kind=r[2], author=r[3],
                body_markdown=r[4], at=r[5],
            )
            for r in m_rows
        )
        return StoredSnapshot(questions=questions, messages=messages)

    def count_questions(self) -> int:
        return int(self._session.execute(
            "SELECT COUNT(*) FROM question").fetchone()[0])

    # ── writes ─────────────────────────────────────────────────────────────

    def import_manifest(
        self,
        manifest: QuestionManifest,
        *,
        actor: str = "migration",
        at: str = "1970-01-01T00:00:00+00:00",
    ) -> ImportResult:
        """Import *manifest* into the store, idempotent on re-import.

        Each manifest entry is matched to an existing question by ordinal
        (the Nth entry by file order maps to the Nth question by id).  This
        matching is stable for a scratch store that starts empty and
        receives imports in the same order, which is the only context this
        scratch-only module is used in.

        Per entry, one of four dispositions:

        - ``inserted``: no stored counterpart existed; a new row was created.
        - ``unchanged``: a stored counterpart exists and every content field
          matches; nothing was written.
        - ``conflict``: a stored counterpart exists but at least one content
          field differs; the difference is NAMED and the row is NOT touched.
        - ``cannot_tell``: the stored counterpart exists but the message
          counts are so different that field-level comparison is unreliable.

        Extra stored questions (ids with no manifest counterpart) and extra
        messages are reported but never deleted — deletion is
        repair-by-overwrite by another name.
        """
        snap = self.snapshot()
        stored_by_pos = list(snap.questions)   # ordered by id
        messages_by_qid: dict[int, list[StoredMessage]] = {}
        for msg in snap.messages:
            messages_by_qid.setdefault(msg.question_id, []).append(msg)

        outcomes: list[EntryOutcome] = []
        extra_qids: list[int] = []

        for ordinal_idx, entry in enumerate(manifest.entries):
            ordinal = ordinal_idx + 1
            if ordinal_idx < len(stored_by_pos):
                sq = stored_by_pos[ordinal_idx]
                outcome = self._compare_existing(
                    ordinal, entry, sq, messages_by_qid.get(sq.id, []), at, actor,
                )
            else:
                qid = self._insert_entry(entry, ordinal_idx, at, actor)
                outcome = EntryOutcome(
                    ordinal=ordinal, disposition="inserted", question_id=qid,
                )
            outcomes.append(outcome)

        # extra stored questions with no manifest counterpart
        if len(stored_by_pos) > len(manifest.entries):
            for sq in stored_by_pos[len(manifest.entries):]:
                extra_qids.append(sq.id)

        # extra messages on matched questions are reported inside _compare_existing;
        # messages on extra questions are reported here
        extra_mids: list[int] = []
        for qid in extra_qids:
            for msg in messages_by_qid.get(qid, []):
                extra_mids.append(msg.id)

        return ImportResult(
            entries=tuple(outcomes),
            extra_question_ids=tuple(extra_qids),
            extra_message_ids=tuple(extra_mids),
        )

    def _compare_existing(
        self,
        ordinal: int,
        entry: QuestionEntry,
        sq: StoredQuestion,
        stored_msgs: list[StoredMessage],
        at: str,
        actor: str,
    ) -> EntryOutcome:
        """Compare one manifest entry against its stored counterpart.

        Never writes: this is a comparison, not an update.  If fields
        differ, the difference is named and the row is left untouched —
        repair-by-overwrite is forbidden.
        """
        manifest_priority = extract_priority(entry.title)
        deltas: list[FieldDelta] = []

        def check(name: str, mv: Any, sv: Any) -> None:
            if mv != sv:
                deltas.append(FieldDelta(name, mv, sv))

        check("status", entry.state, sq.status)
        check("title", entry.title, sq.title)
        check("body_markdown", entry.body_markdown, sq.body_markdown)
        check("priority", manifest_priority, sq.priority)
        check("asked_at", entry.asked_at, sq.asked_at)
        check("asked_precision", entry.asked_precision, sq.asked_precision)

        # message comparison: match by order within the question
        manifest_contribs = entry.contributions
        n_man = len(manifest_contribs)
        n_stored = len(stored_msgs)
        if n_man != n_stored:
            deltas.append(FieldDelta(
                "message_count", n_man, n_stored,
            ))
            # when counts are wildly different, per-field comparison is
            # unreliable — report as cannot_tell on the messages, not as
            # a cascade of misleading per-field conflicts
            if abs(n_man - n_stored) > max(n_man, n_stored, 1) // 2:
                return EntryOutcome(
                    ordinal=ordinal, disposition="cannot_tell",
                    question_id=sq.id, deltas=tuple(deltas),
                )
        else:
            for i, (mc, sm) in enumerate(zip(manifest_contribs, stored_msgs)):
                check(f"message[{i}].kind", mc.kind, sm.kind)
                check(f"message[{i}].author", mc.author, sm.author)
                check(f"message[{i}].body_markdown", mc.text, sm.body_markdown)
                check(f"message[{i}].at", mc.when, sm.at)

        if deltas:
            return EntryOutcome(
                ordinal=ordinal, disposition="conflict",
                question_id=sq.id, deltas=tuple(deltas),
            )
        return EntryOutcome(
            ordinal=ordinal, disposition="unchanged",
            question_id=sq.id,
        )

    def _insert_entry(
        self, entry: QuestionEntry, ordinal_idx: int, at: str, actor: str,
    ) -> int:
        """Insert one question and its messages.  Called only for new entries."""
        priority = extract_priority(entry.title)
        cur = self._session.execute(
            "INSERT INTO question"
            " (status, title, body_markdown, priority,"
            "  asked_at, asked_precision, created_by,"
            "  created_at, updated_at, revision)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (entry.state, entry.title, entry.body_markdown, priority,
             entry.asked_at, entry.asked_precision, actor, at, at),
        )
        qid = int(cur.lastrowid)
        for contrib in entry.contributions:
            self._session.execute(
                "INSERT INTO question_message"
                " (question_id, kind, author, body_markdown, at)"
                " VALUES (?, ?, ?, ?, ?)",
                (qid, contrib.kind, contrib.author, contrib.text, contrib.when),
            )
        return qid


# ─── independent verification ──────────────────────────────────────────────

def verify_import(
    manifest: QuestionManifest, snapshot: StoredSnapshot,
) -> VerificationResult:
    """Compare a source manifest against a DB snapshot, field-for-field.

    This is the INDEPENDENT route (``#759``): it takes the parser's manifest
    and a snapshot read through raw SQL, and compares every content field.
    It does NOT consult the importer's :class:`ImportResult` — that is the
    importer's claim about itself.  An importer that short-circuits on
    "destination already has rows" returns ``unchanged`` for everything
    without looking; this function reads the snapshot independently and
    catches any actual difference.

    What this CAN establish
    -----------------------
    For each manifest entry matched to a stored question by ordinal: whether
    every content field (status, title, body_markdown, priority, asked_at,
    asked_precision, and every message's kind/author/body/at) matches
    exactly.  For entries with no stored counterpart: missing.  For stored
    questions with no manifest counterpart: extra.

    What this CANNOT establish
    --------------------------
    - Over a ZERO-ROW destination: nothing.  An empty store imports
      "successfully" under almost any implementation (``#651``).  The
      verifier reports this as a refusal — ``ok`` is False and
      ``empty_source_refusal`` is True when the source is non-empty but the
      store has no questions.
    - Intent.  If the source itself was truncated before the cutover blob,
      the verifier compares two copies of the same truncation and reports
      a match.  It cannot recover data absent from every retained copy.
    - Metadata fields (created_at, updated_at, revision, created_by).  The
      source manifest does not carry them; comparing them against the
      manifest is meaningless.
    """
    stored_questions = snapshot.questions
    n_manifest = len(manifest.entries)
    n_stored = len(stored_questions)

    # message lookup by question position (ordinal → messages in order)
    stored_msgs_by_qid: dict[int, list[StoredMessage]] = {}
    for msg in snapshot.messages:
        stored_msgs_by_qid.setdefault(msg.question_id, []).append(msg)

    entries: list[EntryOutcome] = []
    missing_ordinals: list[int] = []
    extra_qids: list[int] = []

    for ordinal_idx, entry in enumerate(manifest.entries):
        ordinal = ordinal_idx + 1
        if ordinal_idx < n_stored:
            sq = stored_questions[ordinal_idx]
            outcome = _verify_entry(
                ordinal, entry, sq,
                stored_msgs_by_qid.get(sq.id, []),
            )
        else:
            missing_ordinals.append(ordinal)
            entries.append(EntryOutcome(
                ordinal=ordinal, disposition="cannot_tell",
                question_id=None,
                deltas=(FieldDelta("stored_counterpart", "present", "absent"),),
            ))
            continue
        entries.append(outcome)

    if n_stored > n_manifest:
        for sq in stored_questions[n_manifest:]:
            extra_qids.append(sq.id)

    return VerificationResult(
        question_count_manifest=n_manifest,
        question_count_stored=n_stored,
        entries=tuple(entries),
        extra_question_ids=tuple(extra_qids),
        missing_ordinals=tuple(missing_ordinals),
        denominator_source_bytes=manifest.source_bytes,
    )


def _verify_entry(
    ordinal: int,
    entry: QuestionEntry,
    sq: StoredQuestion,
    stored_msgs: list[StoredMessage],
) -> EntryOutcome:
    """Verify one manifest entry against its stored counterpart.

    This mirrors :meth:`QuestionRepository._compare_existing` but is
    deliberately a separate function: the importer's comparison and the
    verifier's comparison are two code paths that must agree, and keeping
    them separate means a bug in one does not hide in the other.  If they
    disagree, a test should catch it.
    """
    manifest_priority = extract_priority(entry.title)
    deltas: list[FieldDelta] = []

    def check(name: str, mv: Any, sv: Any) -> None:
        if mv != sv:
            deltas.append(FieldDelta(name, mv, sv))

    check("status", entry.state, sq.status)
    check("title", entry.title, sq.title)
    check("body_markdown", entry.body_markdown, sq.body_markdown)
    check("priority", manifest_priority, sq.priority)
    check("asked_at", entry.asked_at, sq.asked_at)
    check("asked_precision", entry.asked_precision, sq.asked_precision)

    n_man = len(entry.contributions)
    n_stored = len(stored_msgs)
    if n_man != n_stored:
        deltas.append(FieldDelta("message_count", n_man, n_stored))
        if abs(n_man - n_stored) > max(n_man, n_stored, 1) // 2:
            return EntryOutcome(
                ordinal=ordinal, disposition="cannot_tell",
                question_id=sq.id, deltas=tuple(deltas),
            )
    else:
        for i, (mc, sm) in enumerate(zip(entry.contributions, stored_msgs)):
            check(f"message[{i}].kind", mc.kind, sm.kind)
            check(f"message[{i}].author", mc.author, sm.author)
            check(f"message[{i}].body_markdown", mc.text, sm.body_markdown)
            check(f"message[{i}].at", mc.when, sm.at)

    if deltas:
        return EntryOutcome(
            ordinal=ordinal, disposition="conflict",
            question_id=sq.id, deltas=tuple(deltas),
        )
    return EntryOutcome(
        ordinal=ordinal, disposition="unchanged",
        question_id=sq.id,
    )


# ─── store spec ────────────────────────────────────────────────────────────

def question_store_spec(path: PathLike) -> StoreSpec:
    """Bind both repositories through the core's one factory seam.

    The question tables are created by the v003 migration, which runs as
    part of ``initialize_legacy_store`` on first WRITE open.  The task
    repository is included so the store is a complete ledger — the
    question foreign keys reference ``task(id)``, and a scratch store used
    for import testing should have the full schema available.
    """
    return StoreSpec(
        path,
        repositories={"tasks": TaskRepository, "questions": QuestionRepository},
        initializer=initialize_legacy_store,
    )
