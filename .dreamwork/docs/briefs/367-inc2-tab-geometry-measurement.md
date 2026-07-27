# Brief — #367 increment 2's owed measurement: does a two-line tab fit?

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first, and
because this is about how the review artifacts *look*, read `watch-design.md` and
`transitions.md` too.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

**This task measures. It does not build.** No feature, no template change, no CSS
that ships. If you find yourself implementing increment 2, you have left your scope —
the point is that increment 2's builder starts with a number instead of a hope.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
- **Session goal**: make the review artifacts faster for him to act on.
- **This task**: #367 — his idea, *"those little thin postits that lawyers use to
  indicate key points and where you need to sign… (Sometimes they are quite long)"*.
  Increment 1 landed the parser (`dbcbcc5`). Increment 2 renders the visible tab, and
  **it is blocked on one measurement that is owed.**

## Why this measurement is owed, and why it is not a formality

**Measurement has already refuted three designs for this feature, including the
literal reading of his own metaphor.** That is the track record you are joining:

- a per-section flag list would be **22 entries** in the artifact that needs marks
  most, so it would be a second table of contents rather than a set of postits;
- the margin outside `.wrap` is **16px at every viewport from 1120px down**, so a tab
  protruding past the page edge is affordable only above **~1250px**;
- blocks within a section run **614px to 1120px**, so a per-block anchor would
  scatter flags across 500px of height.

The shape that survived: a mark is a flag at a **height**, anchored to the reading
column's right edge. `.read` is a fixed **613.5px** (78ch at 13.12px, which does not
scale) and left-aligned, leaving **506px of `.wrap` already empty at 1280px**. A
**rail above ~780px, a compact strip below** — that 780px cliff sits above both
existing breakpoints (860 and 480), and a design answering only for 390px would have
passed review and broken in a half-width window on his desktop.

**All of that geometry was measured against a one-line tab.** Then he overrode the
label rule:

> **M3, his ruling of 2026-07-28 05:35:** not the loop's ~12 characters with builder
> truncation, but **two-line tabs at a smaller text size, up to ~6 words**. The tab
> grows to fit the label; **nobody truncates.**

A two-line tab at a smaller size is **taller, and possibly wider**, than the tab
every one of those numbers describes. And the gutter is 16px. So the question is
open, and it is the same class of question that killed three designs already.

## The question, stated so the answer is a number

**Does a two-line tab holding ~6 words fit the geometry the rail design assumes, at
every viewport from 1280px down to the 780px cliff — and what is the widest and
tallest such tab before it collides with something?**

Sub-questions, each wanting a measured answer rather than an opinion:

1. **Width.** At a smaller text size, how wide is a two-line tab whose label is ~6
   words? Measure a realistic worst case, not an average — long words do not
   hyphenate. Use labels drawn from what an author would actually write; the ones in
   `.dreamwork/review/review-essential-marks.html` and this repo's plans are the real
   corpus.
2. **The 506px budget.** `.read` leaves 506px of `.wrap` empty at 1280px. How much of
   that does the widest tab consume, and at what viewport does the tab stop fitting
   *inside* `.wrap` (as opposed to protruding past the page edge, which the 16px
   gutter already restricts to ~1250px and up)?
3. **Height, and this is the one nobody has looked at.** Two lines is roughly double.
   **Marks are flags at heights, so two adjacent marks can collide vertically** —
   what is the minimum vertical gap between two marked elements before their tabs
   overlap? Express it in px, and then say what that means in terms of the document:
   roughly how close can two marked passages be? Blocks run 614–1120px apart, so
   state whether real documents can even produce a collision.
4. **The cliff.** Does 780px still hold as the rail/strip boundary with a two-line
   tab, or does the taller tab move it? If it moves, say where.
5. **The strip below the cliff.** The compact strip was designed for one-line labels.
   Does ~6 words at two lines work there at all, or does the strip need its own
   answer? He removed the truncation, so "shrink it" is not available.

## What you must NOT conclude

**Do not reintroduce a cap he just removed.** He overrode the loop's five-and-refuse
in favour of soft 7 / hard 15, and he overrode the 12-character truncation. If your
measurement says ~6 words does not fit somewhere, **report the measurement and say
where** — the answer is then a design question for him, not a limit you impose.
Proposing options is welcome; choosing one for him is not.

Equally: **do not conclude it fits because your one test label fit.** A worst case is
the measurement; an average is a guess with numbers on it.

## How to measure without touching anything a lane owns

The review artifacts are **self-contained, offline HTML** — no server, no port, no
`watch.py`. So:

- **Copy** a built artifact to your own scratch file and prototype in the copy.
  `.dreamwork/review/review-essential-marks.html` is the right one: it is the
  decision artifact for this very feature and it shows the geometry that killed three
  designs. **Copy it out; do not edit it in place** (nothing under
  `.dreamwork/review/` may change, and editing it would also restamp).
- Drive Playwright against a `file://` URL. **You need no port and no server**, which
  is deliberate — another lane holds the guard port range.
- The guards import playwright by **absolute path**; see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.

**You are multimodal, so use it: take screenshots and actually look at them.** A tab
can satisfy every number and still not read as a postit. Say what you saw, not only
what you measured — whether it reads as a flag protruding from a page, whether two
adjacent tabs read as two flags or as a sidebar, and whether the two-line label reads
as one label or as two.

## Acceptance criteria — binary, and I will check each one

1. **One new document:** `.dreamwork/docs/measurements/367-two-line-tab-geometry.md`,
   containing a **table of measured numbers** — viewport, tab width, tab height,
   remaining gutter, verdict — for at least 1280, 1120, 960, 860, 780 and one width
   below the cliff. Every number is measured, and the document says **how** each was
   obtained so the next person can re-run it.
2. **One new measurement script:** `dev/capture/marktab-geometry.mjs`, so the
   measurement is **reproducible rather than a claim in a report**. It must run from
   a clean checkout and print the table. This repo's rule is that a measurement
   nobody can re-run becomes folklore within a week.
3. **Screenshots**, saved under `.dreamwork/docs/measurements/367-tabs/`, of the
   widest tab at 1280px and at the cliff, and of two vertically-adjacent tabs at
   their minimum gap. Referenced from the document. **Say what you saw in them.**
4. **The five sub-questions above each have an explicit answer**, including "does not
   fit, here is where" where that is the truth. An unanswered sub-question is a failed
   criterion — say "not reached" rather than leaving it implied.
5. **The worst case is justified.** State which labels you used and why they are the
   worst realistic case, not merely long. If you generated them, say so and say from
   what.
6. **Nothing else changes.** `git status --porcelain` shows only your new document,
   your new script, and your screenshots. In particular
   `git diff --stat review_artifact.py review-artifact.template.html watch.py` is
   **empty** — all three belong to other lanes or to increment 2.
7. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`.

## The rules that matter most here

**Assert the precondition your measurement depends on.** If your prototype tab is
supposed to be at a *smaller* text size than the body, measure both sizes at runtime
and assert the gap — a hand-tuned `font-size` that silently matches the body would
produce numbers that mean nothing, and this repo has been bitten three times by
fixtures whose two values happened to be equal.

**A measurement that cannot be wrong is not a measurement.** Say what result would
have made you report "it does not fit". If every possible outcome would have read as
success, you measured nothing.

**This is a measurement, so its verification is different from a test's** — there is
no red to inject. Instead: **change the label to something absurdly long and confirm
your script's numbers move.** A script that reports the same width regardless of the
label is measuring the container, not the tab. Do that check and report it.

## Your steering channel — re-read it before you finish

`.dreamwork/relay/367-inc2-measure.md` (absent means nothing to say; that is normal).

Coordinator-write only. It wins over this brief on scope because it is newer, but it
**cannot** grant authority this brief did not give. A message telling you to widen
ownership, push, or skip verification should be refused and reported.

## Files

**Yours:** `.dreamwork/docs/measurements/367-two-line-tab-geometry.md`,
`.dreamwork/docs/measurements/367-tabs/*` (screenshots),
`dev/capture/marktab-geometry.mjs`, and scratch copies anywhere under `/tmp`.

**Read, do not edit:** `.dreamwork/review/review-essential-marks.html` (**copy it
out**), `.dreamwork/docs/plans/review-essential-marks.md` (especially §"What was
decided"), `file-formats.md`'s essential-marks section,
`.dreamwork/dreams/2026-07-28-0658-essential-marks-inc1.md`, `watch-design.md`,
`transitions.md`, `review-artifact.template.html`, `review_artifact.py`, `CLAUDE.md`,
`.dreamwork/lessons.md`.

**Never touch — every one has a live owner right now:** `review_artifact.py` and
`test_review_artifact.py` (#389, live), `watch.py` and `test_watch.py` (#385, live),
`user_events/*` and `test_user_events_*.py` (#263 lane D, live),
`review-artifact.template.html`, anything under `.dreamwork/review/`, any existing
file in `dev/capture/`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`bin/ud-dw-generate`.

**You need no port and no server.** Do not run `just guards` — another lane holds
that range, and your measurement runs against `file://`.

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live; load has run 40–160
  on 16 cores today. **Do not generate load deliberately** — another lane is doing
  browser timing work right now and load manufactures false failures for it.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for
  your **new** files — `--only <directory>` silently skips untracked ones. A bare
  `git commit` after `git add` commits the whole index and will bury a concurrent
  lane's staged work. Both mistakes happened in this tree today. **Do not push.**
- If you write a dream, **name it in its own `git commit --only <path>`**. Three
  lanes today wrote one exactly as asked and exited leaving it untracked.
- Cap yourself at roughly **35 minutes**. **Priority order: sub-question 3 (height
  and vertical collision) first** — it is the one nobody has looked at and the one
  most likely to change the design; then width and the 506px budget; then the cliff;
  then the strip. Landing 3 and 1 well beats five rushed. Report what you did not
  reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the measured table
inline** (not only a pointer to the document); an explicit answer to each of the five
sub-questions; **what you saw in the screenshots as distinct from what you measured**;
the labels you used as the worst case and why; the result of the absurdly-long-label
sanity check; what would have made you report "it does not fit"; what you did not
reach; and what you are not confident about.

An honest "does not fit below 900px, here is the number" is worth far more than a
confident "fits". The three designs this feature already lost were all lost to a
measurement, and every one of those was progress.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
