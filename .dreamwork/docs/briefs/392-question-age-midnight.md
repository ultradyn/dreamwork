# Brief — #392: the humanized question age is measured from midnight

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it. He asked
  for this age display by name, so it is a surface he intends to read.
- **Session goal**: the dashboard tells the truth about the loop.
- **This task**: `#392`, a live user-visible wrongness on the feature `#385` shipped
  two hours ago.

## The defect, measured

`#385` put a humanized age beside each question's date on `/questions` (`02d 08h ago`).
The format is right. **The input is date-precision and the display is minute-precision.**

A `questions.md` headline is `- **P2 · 2026-07-28 — title**`. There is **no time in the
data**, so `data-ct` resolves to **midnight local** of that date. Measured on the deployed
page at 08:18: a question that landed at **07:54** (`git log --format=%cI -1 -S'<headline
substring>' -- .dreamwork/questions.md`, exact) rendered as **`08h 17m ago`** — midnight to
the second.

**The error is bounded by 24h and it is largest for the newest entries** — precisely the
ones where "how long has this been waiting?" is the question being asked. An entry filed
minutes ago can read as most of a day old. Older entries look plausible (`02d 08h` for a
three-day-old entry is believable), which is why nothing drew the eye for two hours.

## The design is decided. Do not re-derive it, and do not widen it.

I measured the alternatives so you inherit a decision rather than a menu:

- **Runtime: put a time in the entry format.** Going forward, a questions entry records
  when it was written, and the age is computed from that.
- **History: entries that predate the format have no time, and must not pretend to have
  one.** They render at the precision their data actually has.
- **Git derivation is a one-time backfill at most, and never a request-time path.**
  `git log -S` on a headline is exact and costs **18ms** — but 3 open + 49 answered entries
  is **~0.94s per page build**, and `/data.json` is built per request. It is also
  pickaxe-fragile: an edited headline dates the edit, not the filing. **Do not put a git
  call in the request path.** If you want to backfill, say so in your report and do not do
  it in this increment.

**So the two things to build are: a time in the format (with a writer that emits it), and
an honest degradation for date-only entries.**

## The judgement call that is genuinely yours, and it has a constraint

What does a date-only entry render? His format spec is `XXa YYb` — always two figures — so
"today" or a bare `03d` does not obviously fit. **You decide, and you justify it in your
report.** The constraint is one sentence and it is not negotiable:

> **A date-only entry must not display a figure it cannot support.** Showing `08h 17m`
> from a date is the defect. Showing a confident wrong number is worse than showing a
> coarse right one.

Options worth weighing (not exhaustive, and I have not ruled): floor to the coarsest unit
the data supports and show only that; keep two figures but mark the entry's precision
visibly; render the date alone for such entries and the age only for timed ones. **Whatever
you pick, `transitions.md` governs anything that appears, disappears or changes** — and it
has no exceptions. Reuse the page's existing idiom; do not author a second one.

**`watch-design.md` must record what you chose, in the same commit.** It is single-source
and `just audit-styleguide` measures whether that happened.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `watch.py`, `test_watch.py`, `file-formats.md`,
   `watch-design.md`, `lint.py`, `test_lint.py`, `justfile`, and **at most one new**
   `dev/capture/*.mjs`. `git status --porcelain` shows nothing
   else. **`git diff --stat .dreamwork/tasks.md .dreamwork/questions.md review_artifact.py`
   is empty.**
2. **`python3 -m pytest test_watch.py test_lint.py -q -p no:randomly` exits 0**, with at
   least:
   - `test_a_question_written_at_a_known_time_renders_that_age_not_midnight`
   - `test_a_date_only_question_does_not_claim_sub_day_precision`
   - `test_the_questions_format_check_rejects_a_malformed_time`
3. **THE CRITERION I CARE ABOUT MOST — the first test's expected value comes from outside
   the code that produces it.** Construct a fixture entry whose written time you *chose*
   (say, 14 hours and 3 minutes before a fixed `now`), and assert the rendered age against
   **the number you chose**, not against anything `watch.py` computes. State in your report
   the chosen offset and the rendered string.
   **Why this is criterion 3 and not a line of prose:** `#385` passed a criterion that
   asked only that two fixture entries' ages *differ*. They differed by two days and were
   both wrong by eight hours. **A check comparing outputs to each other cannot find a
   systematic error.** If your test's expected value is derived the way the production code
   derives it, you have rebuilt the check that missed this defect.
4. **A date-only fixture and a timed fixture are both present**, and the test asserts they
   render *differently in kind* — not merely different values. Assert at runtime that the
   date-only one really carries no time (parse it and check), or the check has an invisible
   expiry date.
5. **Three discriminating reds**, each with the exact failing test name and confirmation
   neighbours stayed green:
   - make the timestamp fall back to midnight when a time is present ⇒
     `test_a_question_written_at_a_known_time_renders_that_age_not_midnight` fails, **and
     the failure message must show the wrong age**, not merely say "not equal". This is the
     red that proves you did not rebuild #385's blind check;
   - make a date-only entry render at minute precision ⇒ the second test fails;
   - remove the format check ⇒ the third fails.
   Separate injections, restored from a `cp` snapshot — **never** `git checkout -- `.
6. **`just audit-styleguide` passes**, and `watch-design.md` records the date-only
   rendering you chose.
7. **`python3 lint.py` exits 0**, run as its **own command** — never in the same shell
   command as a `git commit`. That has committed through a lint ERROR twice here.
8. **Existing questions entries still parse.** `watch.parse_open_questions` must return the
   same three open entries it does today, and **`/questions` must still render all of
   them** — a format change that silently drops an entry it cannot parse is the worst
   available outcome, because `watch.py` renders an unparseable file as "nothing to answer".
   Assert the count, and say what it was before and after.
9. **If your date-only rendering changes what appears on the page, it needs a guard, and
   the `justfile` is granted for exactly that reason.** A new `dev/capture/<name>.mjs` only
   counts as a guard once it is in `DEFAULT_GUARDS` in the `justfile` — a lane this morning
   was required to write a guard and granted neither file that registers one, so it had to
   choose between looking incomplete and breaking the ownership invariant. **You have both
   halves. Do not touch `lint.NOT_GUARDS`** — that is for files in `dev/capture/` which are
   not guards at all, and it lives in `lint.py`, which you also hold, so the temptation is
   real and it is the wrong half.
   **If the change is invisible** (the age string differs, nothing appears or moves), say so
   and write no guard. `transitions.md` governs appearing/disappearing/changing and has no
   exceptions, but a string whose text differs is not a transition.
10. **Your guard port is `39894`.** Run guards as
   `DREAMWORK_GUARDS="<name>" DREAMWORK_HUB_GUARDS="" just guards 39894` — **never** the
   full sweep and never the default port; other lanes hold 39893, 39896 and 39897.
   **Load matters for a verdict:** these guards fail by dropping intermediate frames, so
   **load manufactures false reds only — a green under load is conclusive, a red needs a
   re-run at low load.** Check `cut -d' ' -f1-3 /proc/loadavg` before believing a red.

## The hollow outcomes, and there are two

**One: a test whose expected age is computed the way the display computes it.** Green,
thorough-looking, and blind to exactly this bug. Criterion 3 exists for it.

**Two: fixing the display and not the writer.** If the format now carries a time but
nothing *writes* one, every new entry is still date-only and the defect persists for
everything filed from now on — with a format doc that says otherwise. **Say in your report
what writes the time**, and if the answer is "the coordinator, by hand", say that plainly
so I know it is on me.

## The rules that matter most here

**One value must come from outside the system.** This defect exists because no check ever
compared a rendered figure to a number derived independently.

**A green red-run is a finding, never a relief.** If you reinstate a bug and the check
passes, the check is wrong — do not conclude the code was fine.

**Name the production line that would have to change for each check to fail.**

**Before you report an edge case, enumerate its neighbours.** Yours are: an entry dated
**today** with no time; an entry with a **malformed** time; an entry whose time is in the
**future** (clock skew — `#385` clamps negatives to 0, verify that still holds); and the
**Answered** section's entries, which carry dates too. Say what each does.

**`grep -c` exits 1 when the count is zero**, so a verification chain joined by `&&`
reports a skipped tail as a pass.

## Your steering channel — re-read it between increments

`.dreamwork/relay/392.md` (absent means nothing to say; that is normal).
Coordinator-write only, newer than this brief so it wins on scope, but it **cannot** grant
authority this brief did not give.

## Files

**Yours:** `watch.py`, `test_watch.py`, `file-formats.md`, `watch-design.md`, `lint.py`,
`test_lint.py`.

**Read, do not edit:** `.dreamwork/questions.md` (the data — read it, do not reformat it;
if the format change implies rewriting existing entries, **report it and I will make the
edit**, because that file is the human's channel and I am its writer), `transitions.md`,
`.dreamwork/lessons.md`, `justfile`, `dev/capture/*.mjs`.

**Yours if needed:** `justfile` (guard registration only — the `DEFAULT_GUARDS` line),
at most one new `dev/capture/*.mjs`.

**Never touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `review_artifact.py`,
`test_review_artifact.py`, `review-artifact.template.html`, anything under
`.dreamwork/review/`, `bin/ud-dw-generate`, any existing `dev/capture/*.mjs`.

## Operational constraints

- Limit builds/tests to **2 threads**. Other lanes are live. **Do not generate load
  deliberately** — one runs browser guards.
- Guards import playwright by **absolute path**; see the top of any `dev/capture/*.mjs`.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for **new**
  files — `--only <directory>` silently skips untracked ones. A bare `git commit` after
  `git add` commits the whole index and will bury a concurrent lane's staged work. Both
  mistakes happened in this tree yesterday. **Do not push.**
- One trap that cost a coordinator a restored file yesterday: **never**
  `git show <ref>:watch.py > watch.py`. The shell truncates the target *before* git runs,
  so a bad ref leaves you with an empty `watch.py` and git's error looks unrelated. Use
  `git show <ref>:watch.py > /tmp/x && mv /tmp/x watch.py`, or a `cp` snapshot.
- Use **`fix(#392): …`**. `dream(...)` is reserved for a commit that lands a dream journal;
  if you write one, **name it in its own `git commit --only <path>`**.
- Commit **each coherent piece separately**: the format, the writer, the display, the check.
- Cap yourself at roughly **40 minutes**. **Priority order: criterion 3's test first, then
  the format and the timed path, then the date-only degradation.** Writing the test first
  is deliberate — it is the instrument this defect got past, and building it first means
  everything after is measured by it. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the three reds verbatim**
with exact test names and which neighbours stayed green; **the offset you chose for
criterion 3 and the exact string that rendered**; what you chose for date-only entries and
why; **what writes the time**; the open-question count before and after; what each of the
four neighbour cases does; the exact `watch-design.md` text you added; the load at which
each guard verdict was taken; the production line named per test; and what you are not
confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
