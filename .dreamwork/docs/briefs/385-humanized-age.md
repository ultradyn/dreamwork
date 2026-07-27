# Brief — #385: his `XXa YYb` humanized age, and the ladder that stops too early

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first — and
because this touches the dashboard, **read `transitions.md` and `watch-design.md`
too**. The transitions rule on this repo has no exceptions and no size below which
it stops applying.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it;
  the dashboard is that surface, and the questions page is where he answers.
- **Session goal**: the dashboard tells him the truth about the loop's state.
- **This task**: #385, his own request, typed into the dashboard at 05:41 today.

**His words, verbatim — they are the spec:**

> *"questions have the date in their headline, next to that they should have
> humanized time in a standard XXa YYb format, where a and b are units like
> minutes and seconds. We always show both to 2 figures (prefix with gray 0 if
> single digit). Smallest units is seconds, then minutes, hours, days, weeks,
> years. This is structured so that neither XX nor YY are >99 for at least 100
> years."*

## What already exists — reuse it, do not author a second one

**This is the most important instruction in this brief.** `watch.py` already
implements his format. At **1617–1625**:

```js
const p2 = n => String(n).padStart(2, '0');
const AGE_PAIRS = [["d",86400,"h",3600], ["h",3600,"m",60], ["m",60,"s",1]];
const agePair = ct => { … returns `${p2(big)}${bu} ${p2(small)}${su}` … };
```

It is already wired to a `data-ct` attribute (see around **3092**). So the format,
the two-figure padding, and the pair selection are built and working. **Do not
write a second humanizer.** This repo's standing rule is to reuse the existing
idiom rather than authoring a parallel one, and a second time-formatter would drift
from the first within a week.

## The three gaps, and one is a live defect

**1 · The ladder stops at days, which breaks the exact invariant he designed the
format around.** `AGE_PAIRS` has no week and no year rung, so the largest unit is
`d` and **`XX` passes 99 at 100 days** — about 3.3 months, not 100 years. This is
a real defect in existing code, not merely a gap for a new caller. Adding the two
rungs restores his invariant, and you should verify the arithmetic rather than
trust mine: with years and weeks present, years ≤ 99 covers a century, weeks
within a year ≤ 52, days within a week ≤ 6, hours ≤ 23, minutes and seconds ≤ 59 —
so no field can reach 100 for ~100 years, which is what he asked for.

**Decide and state the year length.** 365 days and 52 weeks are not consistent
with each other, and the choice changes the remainder. Pick one, write down why in
a comment, and make the test assert the boundary rather than a magic number.

**2 · The gray leading zero cannot be done through `textContent`.** The current
call site assigns `el.textContent = agePair(...)`, and a text node cannot carry a
`<span>`. So graying one digit means `agePair` returns markup and its caller
switches to `innerHTML`. Every value involved is digits and unit letters the
function itself produced, so there is no injection surface — but **say so
explicitly in your report rather than leaving it implied**, because "we switched to
innerHTML" is exactly the change a reviewer should stop on. If you find a way to
do it without `innerHTML`, that is better; say what you chose and why.

**3 · The questions headline is a new caller.** The entries already show a date in
the headline. Check whether a parseable timestamp reaches the client for those
entries, or whether one has to be added; if it has to be added, that is a
`watch.py` server-side change and it is in scope.

## Acceptance criteria — binary, and I will check each one

1. **`AGE_PAIRS` covers seconds → minutes → hours → days → weeks → years**, and a
   test asserts that **no field can reach 100 within 100 years**. Derive the bound
   at runtime from the table itself — do not hand-write `99`. A literal tuned to
   today's table is a check that cannot see the table change.
2. **A discriminating red for the ladder:** remove the year rung, and a named test
   must fail *by showing a day count above 99*. State the exact test name and the
   value it printed. If removing the year rung does **not** fail a test, the test
   is not testing his invariant — report that.
3. **The gray zero is real and only on a single-digit pad.** `05h 09m` grays two
   zeros; `15h 42m` grays none. A test asserts both directions — the second one is
   the discriminating half, because a rule that grays unconditionally passes any
   test that only checks the first.
4. **The questions headline shows the age next to the date**, and one browser
   guard proves it against a fixture whose entries have **deliberately different
   ages** — assert at runtime that the fixture's two ages actually differ, or the
   check is vacuous. This repo has been bitten three times by fixtures whose two
   values happened to be equal.
5. **`transitions.md` is obeyed.** The age is text that updates; if it changes in
   place, the change is a transition and it obeys that file. Read it before
   deciding, and if the honest answer is "this text updates without a transition
   and that is correct because X", say X in your report. Do not invent a new
   motion idiom — reuse what is there.
6. **`just test` exits 0**, and **`python3 lint.py` exits 0 run as its own
   command** (never in the same shell command as a `git commit` — that has
   committed through a lint ERROR twice here).
7. **`just audit-styleguide` passes**, which means: if you changed how the page
   looks, `watch-design.md` is updated **in the same commit**. That is enforced,
   not advisory.

## The rule that matters most here

**A green red-run is a finding, never a relief.** Reinstate each bug, watch the
named check fail, then restore from a `cp` snapshot — **never** `git checkout --`.
If a check passes with the bug in place, the check is wrong; report it, and do not
conclude the code was fine. And for anything you fake or patch, **name the
production line that would have to change for your check to fail.** If you cannot
name one, there isn't one.

## Files

**Yours:** `watch.py` (you are its sole holder — confirmed free at 06:10, the
previous holder merged and stood down), `test_watch.py`, and **one** guard file
under `dev/capture/` for criterion 4 — extend an existing questions guard if one
fits rather than adding a new file, and say which you chose.

**Read, do not edit:** `transitions.md`, `watch-design.md`, `file-formats.md`,
`justfile`.

**Never touch:** `user_events/` and `test_user_events_*.py` (**two lanes are live
in those right now**), `dev/capture/gitrow.mjs` (another lane owns it),
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

## Operational constraints

- **Your guard port is `39891`.** Run guards as
  `DREAMWORK_GUARDS="<name>" DREAMWORK_HUB_GUARDS="" just guards 39891`.
  **Never** the full sweep and never the default port — other lanes use that range.
- The guards import playwright by absolute path; see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.
- Limit builds/tests to **2 threads**. Other lanes are live.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after
  `git add` commits the whole index, not the paths you named, and will bury a
  concurrent lane's staged work — that happened in this tree an hour ago. **Do not
  push.**
- Cap yourself at roughly **35 minutes**. The ladder fix (gaps 1) is a coherent,
  committable, independently valuable increment — **land it first**, then the gray
  zero, then the headline. If you run out of time after the first, that is a good
  outcome; report the remainder.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the reds verbatim
— what you broke, the exact check name that failed, what it printed**; the year
length you chose and why; whether you used `innerHTML` and what made that safe;
what you did not reach; and what you are not confident about. An honest "not
confident about X, and here is what would settle it" is worth more than a
confident guess.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
