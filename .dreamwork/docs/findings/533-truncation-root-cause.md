# Findings — #533 questions.md rewrite-truncation root cause (P1, data loss)

Ledger id: **#533** (bug, P1). Filed 2026-07-30 09:33; investigated by
lane-533trunc. Builds on lane-509sig's root-cause commit `2364a2a2` (merged
`feceeef`), which exonerated the signature and proved the loss was real.

## Headline

At **07:44:39 on 2026-07-30** the working-tree `.dreamwork/questions.md` lost
**122 lines** of the #229 thread — the 16:12 loop follow-up, the 16:35 human
note carrying a **nested ASCII table** (the grok architecture review), the
16:48 follow-up, and the 17:10 answer, plus the whole #202 entry below it;
the retained 16:12 human note was cut mid-sentence (`/chat route too.` →
`/chat route `). The act that wrote the truncated content was a
**coordinator full-file rewrite of questions.md from a partial read** (the
`write` tool, holding content whose tail had been dropped at a size
boundary). **watch.py is exonerated** by code analysis (below); no fold/groom
script exists. The fix is a **lint guard** that compares the working tree to
HEAD and ERRORs on a net line-loss over a threshold — red-proved.

## Timeline (committed spine + working-tree forensics)

| time (2026-07-30) | what | evidence |
|---|---|---|
| 07:06:44 | `61d4cc11` commits the #505 Open entry. **Full #229 intact** (3057 lines). The append is a **clean single-hunk search_replace** — `@@ -3,6 +3,42 @@`, +36/−0, 0 matches for any #229 content. | `git show 61d4cc11 -- .dreamwork/questions.md` |
| ~07:06 | The truncation enters the **working tree** (uncommitted). The truncated form's digest (`3886be13…`) is an exact match for the value `question-sigs.json` has held **since the 07:06 phantom**, `updated_at` matching "that event to the ms". | 509sig commit `2364a2a2` message |
| 07:44:39 | A background monitor catches the loss live: **#229 follows dropped 7→4** (body unchanged). | 509sig commit `2364a2a2` message |
| 07:44/46/48 | His three answers (#505/#510/#504) appended **via watch** onto the already-truncated file; each append also fires a spurious `question-updated` for #229 (the signature correctly detecting the loss). | `segment_010.md` lines 3631-3632, 3774-3775 |
| 08:10:41 | `0f97df03` commits the truncated file: **+8/−130**, 2935 lines. | `git show 0f97df03 --numstat` |
| 09:33:13 | `fd53d82a` restores the 122 lines (recovered from `fdf30ba7`): +122/−1. | `git show fd53d82a --numstat` |

## The named act and mechanism

**Act:** a coordinator full-file `write` of `.dreamwork/questions.md` from a
partial read, in the session turns immediately following the `61d4cc11`
#505-append commit (~07:06). The content the coordinator held had its tail
dropped at a size boundary; the `write` overwrote the file with that
truncated content.

The verbatim tool call that performed it is **not recoverable from the
compaction segments**: `segment_009.md` is itself truncated — it ends turn
271 with the literal marker `[... TRUNCATED at 524288 bytes, 29 turns
omitted ...]`, and `segment_010.md` begins at turn 279 (~07:41). The
truncating turns (≈272-278) fall in that gap. The act is triangulated
instead from four independent witnesses:

1. **The #509 brief** ties the data-loss detection to "immediately after the
   coordinator appended the #505 Open entry" at 07:06 (`.dreamwork/docs/briefs/509-spurious-229-event.md`).
2. **509sig's live monitor** caught the loss at 07:44:39 (follows 7→4) and
   recorded "the coordinator was actively truncating #229 during the
   investigation (follows 7->4->3); the signature correctly fired on each
   real content loss" (`2364a2a2`).
3. **The shape of the loss** is a **tail-cut**: the file ends mid-entry at
   `/chat route ` (was `route too.`), 122 lines gone from the end. This is
   the signature of a full-file write from content truncated at a size
   boundary — **not** a `read_file` default-limit read (1000 lines), which
   would have lost ~2050 lines, not 122; and **not** a parse-reserialize
   (no such script exists — see below).
4. **The `61d4cc11` #505 append itself is innocent**: a clean search_replace
   (`@@ -3,6 +3,42 @@`, +36/−0, zero #229 matches), so the truncation is a
   *separate* coordinator write that followed it.

**Why it reached a commit undetected:** at `segment_010.md` turn 321 the
coordinator inspected the unexpected `M .dreamwork/questions.md` with
`git diff .dreamwork/questions.md | head -30`. The three answer insertions
sit at the **top** of the file (lines 38/78/113); the −130 tail deletion sits
at the **bottom** (line 2925+). `head -30` showed only the answers, so the
coordinator committed `0f97df03` believing the change was the answers alone.

## watch.py is exonerated (code evidence)

- `collect()` (`watch.py:13331`) only **reads** questions.md (`questions =
  read_text(...)`); it never writes it. The signature path
  `track_question_updates` (`watch.py:13265`) writes only
  `question-sigs.json`, never the ledger.
- Every questions.md writer is an `append_*` handler
  (`_handle_answer` `watch.py:14623`, `_handle_comment` `:14660`,
  `_handle_ask` `:14598`). Each calls a **pure** append helper then
  `atomic_write_text`. `append_subbullet` (`watch.py:12696`) iterates
  **every line** (`for line in lines: … out.append(line)`) and rejoins
  (`"\n".join(out) + "\n"`) — it cannot drop the tail. The answers were
  appended to the #505/#510/#504 entries (top of file), nowhere near #229
  (line 2925).
- No fold/groom script re-serializes questions.md: every earlier fold on the
  committed spine **preserved the #229 tail** (verified across `07ee4f87`,
  `56d891c6`, `ec87a632`, `3a78b45b`, `6d0af807`, `a3524c05`, `4f5aa002` —
  all carry the 17:10 answer), and the fold at `8e19b091` (+103/−100) ran on
  the *already-truncated* 2935-line file and did not touch #229.

This confirms lane-509sig's conclusion ("watch.py never truncates
questions.md … the truncation is the coordinator's rewrite"). The truncator
is a usage error (full-file write from a partial read), not a script bug —
so the fix is a **guard**, not a script repair.

## The fix: a lint guard (red-proved)

`check_questions_truncation` (`lint.py`) compares the working-tree
questions.md to HEAD. A **net** line-loss over `QUESTIONS_TRUNCATION_THRESHOLD`
(50) is not any normal act — a fold is line-neutral (cut from `## Open`,
paste + ruling summary into `## Answered`); an answer/note/entry append adds
lines; the loop never bulk-deletes — so it ERRORs. The one legitimate net
loss (a deliberate archive) is allowed by a `groom:` marker in the last
questions.md commit. The guard fires where the loss happens: the PostToolUse
hook runs `lint.py` after every Write/Edit to questions.md.

- **Threshold is measured, not guessed:** the incident lost 122; the largest
  real fold on this repo (`8e19b091`, +103/−100) is net +3. 50 sits clear of
  every real change and well under the loss it exists to catch.
- **Production line:** `lint.py` `if lost > threshold and not groom:` inside
  `questions_truncation_guard`.
- **Red-proof:** the test `test_a_tail_truncation_is_an_error` builds a real
  git fixture (full questions.md with a #229-style nested-table entry
  committed, then the working tree truncated at the table — mimicking the
  `route too.`→`route ` cut), asserts the loss clears the threshold **derived
  at runtime**, and asserts the guard ERRORs. Sabotaging the production line
  (`if False and lost > threshold`) makes that test FAIL (the truncation
  passes silently — a hollow guard); restoring byte-identical makes it PASS.
  `test_a_line_neutral_fold_is_not_flagged` proves no false positive on a
  real fold; `test_the_groom_marker_allows_a_deliberate_archive` proves the
  escape hatch; `test_no_git_baseline_is_silent` proves a non-repo target
  never faults. `test_lint.py` 391 passed.

## Interim rule (standing until verified in dogfood)

Until the guard has caught (or not) a real truncation across several loop
ticks: the coordinator writes questions.md **only** via `search_replace`
(anchored, minimal-span), never full-file write, never parse-serialize. The
guard is the backstop; this is the practice.

## Noticed but not fixed

- The `git diff … | head -30` habit at `segment_010.md:6272` is what hid the
  loss from the coordinator at commit time. A fuller diff view (or the guard
  firing at write-time) would have caught it earlier; not in this lane's
  scope.
- The compaction segment file is truncated at 524288 bytes
  (`segment_009.md`), which dropped the verbatim turns containing the
  truncating tool call. That is a tooling limitation, not a code bug.
