# Brief — #533 questions.md rewrite-truncation root cause (P1, data loss)

Ledger id: **#533** (bug, P1). Filed 2026-07-30 09:33 after lane-509sig's
root-cause commit (`2364a2a2`, merged `feceeef`) exonerated the signature:
the phantom #229 question-updated events were the signature correctly
detecting REAL data loss.

## What is known (verified at the gate)

- At 07:44:39 on 2026-07-30 the live working-tree `.dreamwork/questions.md`
  lost **121 lines** of the #229 thread: the 16:12 loop follow-up, the 16:35
  human note carrying a nested table, the 16:48 follow-up, the 17:10 answer;
  the retained human 16:12 note was cut mid-sentence ("route too." →
  "route "). The truncated form's digest matches the question-sigs.json
  entry written at ~07:06 to the millisecond.
- Committed clean at `61d4cc11` (07:06:44, +33/−0). The truncation entered
  the WORKING TREE uncommitted between 07:06:44 and 07:44:39, and was then
  committed at `0f97df03` (08:10:41, +8/−130 — the answers commit) and
  persisted until the coordinator restored the block from `fdf30ba7` at
  `fd53d82a` (09:33).
- Lane-509sig ruled OUT watch.py: `collect()` only reads; every questions.md
  writer in watch.py is an `append_*` helper (`append_answer`,
  `append_comment` → `append_subbullet`). The lane's conclusion: "the
  truncation is the coordinator's rewrite."
- The 16:35 note's **nested table** is the likely choke point — the lost
  span starts exactly there-ish and a serializer that chokes on nested
  content drops from that point.

## The question

Which coordinator-side act wrote the truncated content? Candidates:

1. **A full-file `write` from a partial read** — `read_file` defaults to
   1000 lines; questions.md is ~2900; a read-then-full-rewrite truncates
   the tail (the #229 entry sits at the end).
2. **A fold/groom script** (the coordinator's python helpers that move
   entries Open→Answered) that parses and re-serializes entries, dropping
   content its grammar doesn't hold (nested tables in a note).
3. Something else the session record shows.

## Evidence sources (read-only forensics)

- Session rollout segments:
  `/home/xertrov/.grok/sessions/%2Fhome%2Fxertrov%2F.llm-general%2Fskills%2Fud-dreamwork/019fab09-c6a5-78b0-94ae-25ee4dedca04/compaction/segment_*.md`
  (full verbatim rollouts; INDEX.md is the table of contents). Find every
  questions.md write act between 07:06 and 07:44:39 and at 08:10.
- `git log --format="%h %ci %s" -- .dreamwork/questions.md` for the
  committed spine; `git fsck --lost-found` if needed for dangling blobs.
- The coordinator's fold tooling: search the segments for the fold scripts
  used at 8e19b091 and earlier folds — did any re-serialize entries?

## The deliverable

1. **The named act** (tool call + timestamp + the exact mechanism) that
   wrote the truncated content, with the evidence quoted.
2. **The fix**, implemented and red-proved: if a coordinator fold/groom
   script is the truncator, fix the script and add a test with a
   nested-table fixture (born-red against the old script). If the
   truncator is "coordinator used full-file write from a partial read"
   (a usage error, not a script bug), the fix is a GUARD, not a rule:
   e.g. a lint check that a questions.md-writing commit may not delete
   more than N lines without an explicit `groom:` marker in the commit
   message (red-proved: synthesize a truncating commit in a fixture repo
   and watch it fail). Choose by what the evidence shows.
3. A findings doc at `.dreamwork/docs/findings/533-truncation-root-cause.md`
   with the timeline and the quoted evidence.

## Interim rule (already standing, state it in the findings doc)

Until the fix lands: the coordinator writes questions.md ONLY via
search_replace (anchored, minimal-span), never full-file write, never
parse-serialize.

## Lane-owns

New files: the findings doc, any guard/test it specifies
(test_lint.py/lint.py if a lint guard; a fixed script if one exists).
Do NOT edit questions.md itself, watch.py, or handoffs.md beyond your
one literal Pending line. The investigation is read-only on session logs.

## Handoff

Literal Pending line in `.dreamwork/handoffs.md`
(`- **#533** · landed \`<sha>\` · … · by lane-533trunc — …`) naming the
act, the mechanism, the fix, and its red-proof. Commit with
`git commit --only <paths>` (new files need `git add` first). NEVER attn,
never pkill -f.
