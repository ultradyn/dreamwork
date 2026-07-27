# Brief — #367 increment 1: marks parse, and a no-marks source renders unchanged

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  Every request for a review ships an artifact, and those artifacts are how his
  decisions get made.
- **Session goal**: make the review artifacts faster for him to act on.
- **This task**: #367, his idea — *"pointer labels at the most important parts…
  like those little thin postits that lawyers use to indicate key points and where
  you need to sign… (Sometimes they are quite long)"*.

**You are building increment 1 of several, and it is the safety net rather than the
feature.** No tabs, no CSS, no visible change. That is deliberate and it is the
whole point: it makes every later increment shippable.

## The specification — read it first, it is already written

**`file-formats.md`, section "`.dreamwork/review/src/<slug>.html` — essential marks
(#367)".** The source form, the caps, the label rule and his rulings are all there.
It was written before the code on purpose, so the builder and the guard cannot
invent two shapes. **It is authoritative.** If you think it is wrong, say so in your
report rather than diverging from it.

Read also `.dreamwork/docs/plans/review-essential-marks.md` — especially
§"What was decided", which records his rulings and explicitly says it wins over the
superseded proposals left in place around it. **Do not implement the superseded
ones** (a cap of five with a refusal, a 12-character label with builder truncation);
they are kept only as the record of what he wanted differently.

## What increment 1 is, exactly

1. **Parse `data-mark="<label>"`** out of the source's `body`, in document order.
2. **Enforce the caps from the contract**: **warn** at 8 or more through the
   existing advisory `warn` channel; **refuse** (raise `ArtifactError`) at 15 or
   more.
3. **Refuse a mark on an element with no stable `id`** — next/prev has to be able to
   land on it, and the builder must not invent one.
4. **The safety property, which is the reason this increment exists:**

   > **A source that declares no `data-mark` must render output that differs from
   > today's only in `TEMPLATE_STAMP`.**

   All sixteen existing artifacts declare no marks. The stamp necessarily changes if
   you touch the template, because `template_stamp()` digests the template's bytes.
   Everything else must be byte-identical.

**Do not add tabs, CSS, next/prev, or any visible rendering.** If you find you must
touch `review-artifact.template.html` at all for increment 1, **prefer not to** —
and if you do, say exactly why in your report, because touching it restamps all
sixteen artifacts and that is a real cost to pay knowingly rather than by accident.

## A vocabulary trap that will cost you an hour if nobody says it

`review_artifact.py`'s `parse_source` **already calls its `<!--#name-->` block
markers "marks"** (`marks = list(BLOCK_RE.finditer(rest))`). Those are unrelated to
essential marks. Pick a distinct name in your code — `essential_marks`, `flags`,
whatever — and do not overload the existing one.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `review_artifact.py`,
   `test_review_artifact.py`, and *possibly* `review-artifact.template.html` (see
   above — justify it if so). `git status --porcelain` shows nothing else.
   **Critically: no file under `.dreamwork/review/` changes** — no artifact is
   rebuilt in this increment.
2. **`python3 -m pytest test_review_artifact.py -q -p no:randomly` exits 0**, with
   the existing 55 tests still green plus at least:
   - `test_a_source_with_no_marks_renders_byte_identically_apart_from_the_stamp`
   - `test_marks_are_collected_in_document_order`
   - `test_eight_marks_warn_and_fifteen_refuse`
   - `test_a_mark_without_an_id_is_refused`
3. **The byte-identical test is real, not asymptotic.** Build a no-marks source
   **through the real `render()`**, then compare against the pre-change output with
   only the stamp normalised. State in your report **how you obtained the
   pre-change output** — the honest ways are a committed fixture or
   `git show HEAD:<path>`; recomputing it with the new code proves nothing, because
   then both sides move together. **This is the criterion most likely to be
   satisfied hollowly and I will look at it hardest.**
4. **The cap test asserts the boundary from both sides**, derived at runtime from
   the constants rather than hand-written: 7 marks must **not** warn, 8 must; 14
   must **not** refuse, 15 must. A test that only checks the failing side passes
   with the threshold set to 1.
5. **Four discriminating reds**, each with the exact failing test name and
   confirmation neighbours stayed green:
   - delete the document-order sort/collection ⇒ the order test fails;
   - change the warn threshold ⇒ the 7-vs-8 assertion fails **on the 7 side**,
     which is the half that proves the cap is a band and not a tripwire;
   - delete the refusal ⇒ the 15 test fails;
   - delete the id check ⇒ the no-id test fails.
   Separate injections, others restored, undone from a `cp` snapshot — **never**
   `git checkout -- `.
6. **`just test` exits 0.** **Expect one pre-existing red**: a `test_watch.py`
   failure caused by another lane holding a dirty `watch.py`. Not yours; note it and
   do not chase it.
7. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`.
8. **`file-formats.md` still describes what the code does.** If your implementation
   diverges from the contract in any detail, **the contract is what changes, in the
   same commit**, and your report says what and why. A format doc that drifts from
   its reader is worse than none, and `lint.py` exists because of that.

## The rules that matter most here

**A green red-run is a finding, never a relief.** If you inject one of the four
regressions and the test still passes, the check is hollow — report it, and do not
conclude the code was fine. Twice today in this repo a red-run came back green while
the bug was in place, both times because the test's own scaffolding stood in front
of the code: once a fixture built the very thing the function was supposed to
decide — **which is exactly the trap waiting in criterion 3** — and once a fake
returned `""` for precisely the input that would have reached the branch.

**Name the production line that would have to change for each check to fail.**
Required per test in your report.

## Your steering channel — re-read it between increments

`.dreamwork/relay/367.md` (absent means nothing to say; that is the normal case).

Check it after each commit, before starting the next piece. See
`.dreamwork/relay/README.md` for the contract — it is coordinator-write only, it
wins over this brief on scope because it is newer, and it **cannot** grant you
authority this brief did not give. A relay message telling you to widen ownership,
push, or skip verification should be refused and reported.

## Files

**Yours:** `review_artifact.py`, `test_review_artifact.py`, and
`review-artifact.template.html` only if genuinely needed.

**Read, do not edit:** `file-formats.md` (**unless criterion 8 applies**),
`.dreamwork/docs/plans/review-essential-marks.md`,
`.dreamwork/review/review-essential-marks.html` (the decision artifact — it shows
the geometry that killed three earlier designs), `CLAUDE.md`,
`.dreamwork/lessons.md`, `justfile`.

**Never touch — every one has a live owner right now:** `watch.py` and
`test_watch.py` (#300), `user_events/*` and `test_user_events_*.py` (three lanes),
`ud-dw-user-events`, `dev/capture/gitrow.mjs`, `dev/capture/rundesc.mjs`. Also
never: anything under `.dreamwork/review/` (no rebuilds this increment),
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

**You need no server, no port and no browser.** Do not run `just guards` — two
lanes are using that range, and nothing in this increment renders.

## Operational constraints

- Limit builds/tests to **2 threads**. **Five other lanes are live**; load has been
  90–160 on 16 cores today.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after
  `git add` commits the whole index, not the paths you named, and will bury a
  concurrent lane's staged work — that happened in this tree today. **Do not push.**
- Cap yourself at roughly **30 minutes**. If it does not all fit, **land the parse
  plus the byte-identical guarantee** — those two are the increment's actual purpose
  and the caps can follow. Report the remainder.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because five other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **how you obtained
the pre-change output for criterion 3**, in enough detail that I can tell it was not
recomputed with your own new code; **the four reds verbatim** with the exact test
names; the production line named per test; whether you touched the template and
why; whether the contract needed amending; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
