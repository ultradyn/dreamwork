# 2026-07-25 — file formats are stated, and questions.md is seeded

## What changed

Some files the loop writes are parsed by a tool, and until now the only
specification of their shape lived in the parser. The loop was told what
each file *means* and never what it must *look like*, so a perfectly
reasonable file could be unreadable — and the failure is silent, because
zero parsed entries renders identically to nothing to report.

- **`file-formats.md`** (new, skill root) states the shapes. It fully
  specifies `.dreamwork/questions.md` — literal `## Open` and
  `## Answered` headings, `- **Title**` entries whose titles may
  hard-wrap, threaded sub-bullets, the closed set of author tags — and
  maps the remaining files to their readers, marking honestly which
  contracts are not yet written down.
- **SKILL.md** gains a Formats bullet in durable state, and the
  questions.md bullet now says its shape is a contract rather than a
  style.
- **Init step 7 seeds `.dreamwork/questions.md`** with its skeleton when
  absent, so the first entry appends into an existing structure instead
  of deciding the format blind.

## Why

On 2026-07-25 the dreamwork instance running on ez-feedback-pipeline
opened its dashboard to zero questions over a `questions.md` holding
six, four genuinely open — two of them privacy defaults that must not
ship on a guess. It had written `##` headings *as* the questions. The
badge read 0, `/questions` was empty, nothing was logged, and the loop
believed it had escalated. The guardrail SKILL.md relies on — *never
propose something needing the human's response without writing it to
questions.md, they may be afk or miss the message* — was defeated by the
mechanism meant to enforce it.

It also could not have been answered from the dashboard even if found
another way: `/answer` and `/comment` walk the same section rules, so an
unreadable file is also an unwritable one.

## What targets should do

Nothing is required. Existing targets whose `questions.md` already
parses are unaffected.

If your dashboard shows no questions and the file is not empty, that is
this bug: compare against `file-formats.md` and the canonical example at
`dev/capture/fixture/.dreamwork/questions.md`, and rewrite the structure
— the content is fine. Do it deliberately rather than in passing; the
file is live state for undecided questions, and rewriting it underneath
a running dashboard deserves saying out loud first.

## What this does not fix

Two halves are still open, both by design rather than oversight:

- **The reader still cannot complain** (#136). A non-empty file yielding
  zero entries should say so in the UI and the log; today it renders as
  all-clear. That fix matters for every file the writer-side never sees
  — another machine, another project, a hand edit after the fact.
- **This is prose, and prose drifts** (#137). A third description of a
  format is a third thing that can disagree with the parser, which is
  the very failure being fixed. The intended end state is a linter that
  *calls* the actual readers, so the check cannot drift from what it
  checks; then this file explains and the linter enforces.
