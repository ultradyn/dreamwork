# Do `answers.md` records need durable file-format IDs? (#248)

Decision document for the question the #248 ledger entry poses: the late #238
review flagged that "exact-content twins cannot retain distinct identity
through reorder without a durable file-format id" and asked whether real
workflows justify a migration, or whether this is "solving a semantically
invisible distinction by default" — which the entry itself warns against.

This document is the analysis only. It changes no code, no contract, ships no
migration. The coordinator and the human rule on it.

## 1. The concrete failure, stated as a scenario a human would notice

**Finding: I could not construct one, and that is the recommendation.**

The attempt, in full: an exact-content twin pair is two `## Open` or two
`## Answered` entries whose `(title, body)` — or `(title, when, body, follows)`
for Answered — are equal after the parser's normalization. Two such entries
are byte-identical in every field the schema regards as the record. The
only consumer of record identity today is the `/answers` page's open-state
restore (#238): which `<details>` disclosures were expanded at the last tick
must survive a `data.json` refresh. That consumer is documented (#247) to
**fail closed** — when a survivor's aid changes (e.g. an earlier twin was
deleted and ordinals renumbered), the disclosure closes rather than reopen
onto the wrong body.

So the candidate "human would notice" outcomes reduce to two:

- **Reorder.** A twin pair is reordered within `## Answered`. With no durable
  id, the reader cannot say which physical line is which record.
  *Consequence:* I reproduced this against the real parser. For two
  byte-identical entries the reorder is a **no-op on the file itself** —
  swapping two identical blocks of source text leaves the file byte-equal to
  what it was (`reordered == original` is `True`). The page renders the same
  two disclosures in the same two states. There is nothing for the human to
  notice, because the thing he would notice *is the same bytes* before and
  after. The ledger's literal claim ("cannot retain distinct identity through
  reorder") is true at the level of the abstract ordinal but has no
  observable consequence: the two records ARE the same identity, by every
  field the schema defines as identity.
- **Deletion of one twin.** The survivor's ordinal goes 1→0, its aid
  changes, open-restore fails closed, the disclosure closes. This is the
  #247-documented behavior and is the safe one. The deleted record's content
  is byte-identical to the survivor's, so no semantic information was lost.

The only scenario I can construct in which a human notices anything at all
is the documented fail-closed collapse on twin deletion — a visible but
correct behavior, on content that was by definition duplicated. The wrong
outcome the durable id would prevent — a wrong record opening — does not
happen, because the open-restore already prefers to miss.

A scenario I specifically looked for and ruled out: a human re-asks the
same question on the same day, and the loop treats the two as intentionally
distinct threads. `append_human_question` (watch.py:2667) builds the title
as `{stamp} — {first-sentence}` with `stamp = %Y-%m-%d`, so a same-day,
same-text re-ask is the one realistic producer of an Open exact-content
twin. Even in that case, the two entries render identical titles and
identical bodies; the human sees two indistinguishable cards, and whether
the "first" or "second" one carries its open state across a refresh is not
something he can tell apart. For `## Answered`, a twin requires identical
resolution text AND identical `when` down to the minute — outside realistic
coordinator behavior.

## 2. Measurement, not speculation

Read directly from `.dreamwork/answers.md` via the real parsers:

```
OPEN entries:     0
ANSWERED entries: 6
OPEN exact-content twin pairs:    0
ANSWERED exact-content twin pairs: 0
```

Every answered entry has a distinct title (each carries a distinct date and
topic), a distinct body, and a distinct resolution stamp. There are no
exact-content twins in the real file today.

What the code does today when it meets twins (read at watch.py:6403–6490):

- `parse_open_answers` keys the twin by `(title.strip(), body.strip())`.
- `parse_answered_answers` keys the twin by `(title, when, body, follows)`,
  all normalized through `_answer_aid_parts`.
- Each member of a twin group gets a 0-based ordinal **by current file
  position**, folded into the SHA-256 payload alongside the content.
- Result: distinct-content records keep stable `aid`s across reorder and
  deletion of peers (the ordinal stays 0 because the key never repeats).
  Twin records get distinct `aid`s that are positional: shuffling the file
  shuffles which physical row carries which ordinal, and deleting an earlier
  twin renumbers later ones.

The limit is exactly what the ledger says it is. It is bounded by fail-closed
restore: a renumbered survivor's disclosure closes, never opens onto the
wrong body.

## 3. The options, with costs

### A. Do nothing in the file format; keep the documented limit (#247 as-shipped)

The current state. `aid` is content-derived plus positional ordinal; the
limit is documented in `answer_record_aid`'s docstring, in
`watch-design.md` (#247 paragraphs), and in `dev/capture/answers.mjs`.

- **What breaks for an existing install:** nothing. No migration; no
  reader change; no writer change.
- **What the reader must tolerate:** an exact-content twin's `aid` is
  positional and may change on deletion of an earlier twin. Open-restore
  fails closed in that case — the disclosure the user had open closes
  rather than reopening on a different body.
- **New failure mode introduced:** none. This is the baseline.

### B. Derive a stable id from content plus a stable ordinal (still no file change)

This is option A described differently: the `aid` already *is* content plus
ordinal. The only way to make the ordinal "stable" without a file-format
change is to derive it from something durable in the record itself — but
the record's only fields are content fields, and the content is by
definition equal across the twin. There is no second signal.

- **What breaks for an existing install:** nothing — this is A.
- **What the reader must tolerate:** same as A.
- **New failure mode introduced:** none. The option is empty as stated: it
  either reduces to A or it requires a file-format change (option C).

A genuine non-positional stable ordinal cannot be derived from content
alone; that is the thing the ledger entry correctly identifies. So this
option exists only to be ruled out.

### C. Add an explicit id to the file format, with a migration

An `id: a1f2` (or similar) marker on every entry, read by the parsers and
preferred over content-derived keys. Requires:

- Writers mint and persist the id: `append_human_question` (the `/ask`
  POST path), and the loop-side fold step that moves Open → Answered.
- Readers prefer the explicit id: `_parse_entries`,
  `parse_open_answers`, `parse_answered_answers`.
- `lint.py` enforces presence and shape of the id, so a missing or
  malformed one is loud rather than silent.
- `file-formats.md` gains the id as part of the entry grammar.
- A migration file under `migrations/` instructs every existing target to
  retrofit ids into every existing entry — and every installed target must
  run it, because a reader that expects ids meets a pre-migration file
  that does not have them. (See `migrations/README.md`: "any change to
  state shape or loop-visible behavior ships with a migration entry in
  the same commit.")

- **What breaks for an existing install:** every target must run the
  migration. A pre-migration file opened by a post-migration reader must
  degrade (synthesize content aids as today) or be rejected — and the
  repo's stance ("nothing fails quietly") means the choice between silent
  fallback and a loud error must be made explicitly and documented.
- **What the reader must tolerate:** a new field on every entry, a new
  writer obligation, and a new way for the file to be malformed (duplicate
  id, missing id, malformed id). Each is a checkable shape — but each is
  also a new check that has to be kept red-true, per the CLAUDE.md rule.
- **New failure mode introduced:** id collision (two entries minted the
  same id, e.g. by a buggy writer or a hand-edit). This is strictly worse
  than the current twin limit, because a colliding explicit id is *sticky*
  — it does not self-correct on the next write, the way a positional
  ordinal does. It also introduces a new class of bug: an id pointing at
  the wrong record, which the content-derived key cannot do because the
  content *is* the record.

## 4. Recommendation

**Defer. Do not migrate. Keep the #247 design as-shipped.**

The premise that asks for a durable file-format id — "exact-content twins
cannot retain distinct identity through reorder" — is technically true but
semantically empty for this schema: an `answers.md` record IS its content
(title, body, when, follows), and two records equal on all of those are the
same record by every field the file treats as meaning. The one consumer of
record identity (open-state restore) already fails closed on the only case
that matters (deletion of an earlier twin renumbers a survivor), so the
wrong outcome a durable id would prevent — a wrong disclosure reopening —
does not occur. Measured against the cost, the migration buys positional
stability for a case the real file does not contain (0 twins today) and
the real workflow does not distinguish (the human cannot tell two
byte-identical cards apart). It also introduces a strictly worse failure
mode (sticky id collision). The ledger's own warning — "solving a
semantically invisible distinction by default" — is the correct summary of
what option C would do.

**Trigger that should make a future reader revisit:**

1. A real bug report from a human who notices an unexpected disclosure
   collapse after deleting an exact-content twin, AND who cares that the
   survivor was the "second" one rather than the "first". That is the only
   observable signature of the current limit, and if it never arrives the
   limit is theoretical.
2. A workflow emerges in which the human intentionally re-asks the same
   question on the same day and expects the two threads to track
   independently across edits and reorders (e.g. a "ask twice to
   emphasize" convention, or a future topic-chat model (#229) that
   promotes answers.md entries to first-class threadable records). At that
   point the entries are no longer semantically identical and the
   distinction becomes worth its migration cost.
3. A second consumer of record identity appears whose correctness depends
   on the positional ordinal staying stable across file edits (e.g. a
   stats/audit layer that joins on `aid` across history). Today there is
   exactly one consumer (the `/answers` open-state restore) and its
   contract is fail-closed; a second consumer with a different contract
   changes the analysis.

Until any of those, the deferral stands with the trigger on record.

## 5. What I did NOT examine

- The browser-side JS that consumes `aid` (`data-aid`, `data-keep`,
  `snapshotFolds`, `restoreFolds`, FLIP) in source detail. I read
  `watch-design.md`'s contract paragraph and the guard
  `dev/capture/answers.mjs`, and confirmed fail-closed is the documented
  behavior, but did not trace the JS execution path.
- `dreamhub.py` — confirmed it does not read `answers.md` (the
  file-formats table lists it as a reader of `status.json`, `watch-port`,
  `watch-tint`, `run-mode`; grep for `parse_open_answers` /
  `parse_answered_answers` in `dreamhub.py` returns zero), so it is not a
  second consumer of record identity.
- The submissions log (`submissions.log`) correlation: it stores the POST
  body verbatim and is independent of file identity, so it does not change
  the analysis either way.
- Future workflows under #229 (topic chats), #263 (user-event journal), or
  #264 (SQLite-backed tasks). These were read only as triggers in
  section 4, not as current consumers.
- The `questions.md` side of the same question. `questions.md` uses the
  same `_parse_entries` grammar and has its own (prior) id considerations;
  this document covers `answers.md` only, as scoped by #248.
- Whether a writer-side intervention (refusing duplicate same-day asks in
  `append_human_question`) is preferable to a file-format migration. It is
  not: refusing a duplicate is wrong (the human may genuinely re-ask), and
  auto-minting a suffix (` (2)`) is exactly the "fabricated distinction"
  the ledger warns against and would be a content change with its own
  reader-visible consequences. Mentioned here for completeness; not a
  live option.

---

Authored: 2026-07-27, task #248. Recommend defer; trigger on a real
observed collapse a human cares about, a new twin-distinguishing workflow,
or a second aid consumer with a non-fail-closed contract.
