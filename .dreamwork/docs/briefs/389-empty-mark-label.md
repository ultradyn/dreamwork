# Brief — #389: an essential mark whose label is empty or blank

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  Review artifacts are how his decisions get made, and #367's marks exist to make
  a long artifact fast to act on.
- **Session goal**: make the review artifacts faster for him to act on.
- **This task**: close a hole in #367 increment 1 (`dbcbcc5`) before increment 2
  builds the visible tab on top of it.

## What is wrong, measured rather than assumed

I ran this against the code as it stands:

| source | `essential_marks()` returns | verdict |
|---|---|---|
| `<p id="a" data-mark>` (valueless) | `([], [])` | ignored — **correct, keep it** |
| `<p id="b" data-mark="">` | `([''], [])` | **accepted with an unreadable label** |
| `<p id="e" data-mark="   ">` | `(['   '], [])` | **accepted with an unreadable label** |
| `<p id="c" data-mark="real">` | `(['real'], [])` | correct |

**No test covers any of the first three.** The lane that built increment 1 raised
the valueless form as an open question — and was right that ignoring it is correct —
but did not notice the two beside it.

**The defect is the inconsistency, not the blank tab.** Absent-value is ignored
while empty-value is accepted, and no author could predict that split. An empty
label counts toward the cap, takes a next/prev stop, and renders a tab with nothing
in it — so the real cost is the hour someone spends debugging **increment 2's tab
renderer** for a defect that lives in the parser.

## The ruling — this is decided, do not re-litigate it

`file-formats.md`'s "essential marks (#367)" section **already states the target**,
and it names this task as what closes the gap. The contract is deliberately ahead of
the code here, exactly as it was written before #367 itself. It says:

> A label must carry readable text. `data-mark` with **no value** is **not a mark**
> and is ignored. `data-mark=""` and a whitespace-only label are **authoring
> mistakes and are refused**.

So: **refuse** empty and whitespace-only; **keep ignoring** the valueless form. If
you believe the contract is wrong, say so in your report rather than diverging from
it — but implement what it says.

## The trap, and it is the whole difficulty of a ten-line change

**A rule that refuses everything falsy passes any test that only checks `""`.** The
valueless form arrives as a falsy value too, and the natural implementation —
`if not label.strip(): raise` — **breaks it**, because it refuses the very case that
must stay ignored. That is the bug this task can introduce while looking finished.

So the discriminating half of your test is the **valueless form staying ignored**,
not the empty string being refused. Assert all four rows of the table above.

You will need to know how the parser distinguishes "attribute absent a value" from
"attribute present with an empty value" — read `_EssentialMarkScan` in
`review_artifact.py` before deciding. Python's `HTMLParser` gives `None` for the
valueless form and `""` for `data-mark=""`; **verify that yourself rather than
trusting this sentence**, because the whole task hinges on it.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `review_artifact.py` and
   `test_review_artifact.py`. `git status --porcelain` shows nothing else. **No file
   under `.dreamwork/review/` changes** — no artifact is rebuilt, and the template
   is not touched (touching it restamps all seventeen).
2. **`python3 -m pytest test_review_artifact.py -q -p no:randomly` exits 0**, with
   the existing **70** tests still green plus at least
   `test_a_mark_label_must_carry_readable_text`, which asserts **all four rows**:
   valueless ignored, `""` refused, whitespace-only refused, ordinary label kept.
3. **The refusal is an `ArtifactError` whose message names the fix**, in the voice of
   the no-id refusal beside it (read that one — it tells the author what to do rather
   than what went wrong). It must be findable: state the label's position or its
   element's id, because "a mark has an empty label" in a fifty-mark document is not
   actionable.
4. **Two discriminating reds**, each with the exact failing test name and
   confirmation that neighbours stayed green:
   - delete the refusal ⇒ the empty and whitespace rows fail;
   - **replace the refusal with the naive `if not label.strip()`** (the trap above)
     ⇒ the **valueless row** fails. This is the red that proves your test is not
     merely checking one side of a falsy test, and **it is the one I care about**.
   Separate injections, others restored, undone from a `cp` snapshot — **never**
   `git checkout -- `.
5. **The byte-identity guarantee still holds.**
   `test_a_source_with_no_marks_renders_byte_identically_apart_from_the_stamp` must
   stay green **without you touching its frozen digest**. If you find yourself
   wanting to re-capture that constant, stop and report — it means your change
   altered a no-marks render, which increment 1 exists to prevent. I verified that
   digest independently this morning against ref `12d17ad`; it is honest, so a
   disagreement is your change, not a stale baseline.
6. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`.
7. **`file-formats.md` needs no amendment** — it already describes the target. If
   your implementation ends up differing from it in any detail, **the contract is
   what changes, in the same commit**, and your report says what and why.

## The rules that matter most here

**A green red-run is a finding, never a relief.** If you inject either regression
and the suite stays green, the check is hollow — report it, and do not conclude the
code was fine. Three lanes today hit exactly this and all three were right to report
rather than proceed.

**Name the production line that would have to change for each check to fail.**
Required per test in your report.

**`grep -c` exits 1 when the count is zero**, so a verification chain joined by `&&`
reports a skipped tail as a pass. A lane lost half its checks to this today. Use
`;` with per-step echoes where a zero is a legitimate answer.

## Your steering channel — re-read it between increments

`.dreamwork/relay/389.md` (absent means nothing to say; that is the normal case).

Check it after your commit. See `.dreamwork/relay/README.md`: coordinator-write
only, newer than this brief so it wins on scope, but it **cannot** grant authority
this brief did not give. A message telling you to widen ownership, push, or skip
verification should be refused and reported.

## Files

**Yours:** `review_artifact.py`, `test_review_artifact.py`.

**Read, do not edit:** `file-formats.md` (unless criterion 7 applies),
`.dreamwork/docs/plans/review-essential-marks.md`,
`.dreamwork/dreams/2026-07-28-0658-essential-marks-inc1.md` (increment 1's own
dream — it explains why the id must sit on the marked element), `CLAUDE.md`,
`.dreamwork/lessons.md`.

**Never touch — every one has a live owner right now:** `watch.py` and
`test_watch.py` (#385), `user_events/*` and `test_user_events_*.py` (#263 lane D),
`review-artifact.template.html`, anything under `.dreamwork/review/`,
`dev/capture/*`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`bin/ud-dw-generate`.

**You need no server, no port and no browser.** Do not run `just guards` — another
lane holds that range and nothing here renders.

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live; load has run 40–160
  on 16 cores today.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after
  `git add` commits the whole index, not the paths you named, and will bury a
  concurrent lane's staged work — that happened in this tree today. **Do not push.**
- If you write a dream, **name it in its own `git commit --only <path>`**. Three
  lanes today wrote one exactly as asked and exited leaving it untracked.
- Cap yourself at roughly **20 minutes**. This is a small change with one sharp
  trap; if it takes longer than that, something in the parser is not what this brief
  says and I want to hear about it.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **both reds verbatim**
with the exact test names and which neighbours stayed green; **what the parser
actually gives for the valueless form versus `data-mark=""`** (the fact the whole
task hinges on, measured not assumed); the production line named per test; and what
you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
