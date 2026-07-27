# Brief — #392a: a date-only question must stop claiming a sub-day figure

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

**When you land a commit**, also append **one line** to `.dreamwork/handoffs.md` under
`## Pending`:
`- **#392a** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by ccc @glm52 — <one line, what landed>`
Append only (`cat >>`), never rewrite — other sessions append concurrently. Do **not** touch
`## Folded` and do **not** write to `.dreamwork/tasks.md`.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it. He asked for
  this age display **by name**, so it is a surface he intends to read and currently cannot trust.
- **Session goal**: the surfaces he reads tell the truth.
- **This task**: `#392a`, the unblocked half of a **live user-visible defect** on a feature that
  shipped this morning.

## The defect, measured — inherit these numbers

`#385` put a humanized age beside each question's date on `/questions` (`02d 08h ago`). The
format is right and the ladder is right. **The input is date-precision and the display is
minute-precision.**

A `questions.md` headline is `- **P2 · 2026-07-28 — title**`. **There is no time in the data**,
so the timestamp reaching the client resolves to **midnight local** of that date. Measured on
the deployed dashboard at 08:18: a question that landed at **07:54** rendered as
**`08h 17m ago`** — midnight to the second, an eight-hour lie about a 24-minute-old entry.

**Two things make it worse than a rounding error.** The error is **largest for the newest
entries** — exactly the ones where *"how long has this been waiting?"* is the question being
asked, so something filed minutes ago can read as most of a day old. And it is **invisible on
old entries**: `02d 08h` for a three-day-old question is believable, which is why it sat for
two hours. The tell, once you know it, is that **every multi-day age on the page ends in the
same hour figure** — an audit found all **38** age nodes doing it.

**Every entry in `questions.md` is date-only today.** So this half alone removes the whole
user-visible error. Putting a time *into* the format is `#392b` and it is **blocked on another
lane holding `file-formats.md`** — so **you must not change the file format** or add a time to
any entry. You are fixing what the display claims about the data it already has.

## The presentation decision is made. Implement it; do not re-open it.

> **The number of figures encodes the precision. Two figures means we know the time; one figure
> means we know only the day.**

So a date-only entry renders **`03d ago`**, not `03d 08h ago`. The **missing second figure is
the signal**, read against timed entries beside it. No tilde, no tooltip, no badge, no new
glyph — it reuses `#385`'s existing idiom (including its greyed pad digit) and it degrades to
exactly the information the data holds.

His original spec was `XXa YYb` — always two figures — so **this is a deliberate, documented
departure and `watch-design.md` must say so and say why.** That file is yours.

**One case is genuinely yours to decide, and it is the one he will see most: an entry dated
today.** `0d ago` reads wrong for something filed this morning. Decide it, implement it, and
**justify it in your report**. The constraint on your choice is the same single rule:

> **Never display a figure the data cannot support.** A confident wrong number is worse than a
> coarse right one.

Options worth weighing, not exhaustive and I have not ruled: a word (`today`) — which breaks the
figure grammar and may be the right break; `0d`; or the date alone with no age. Say what you
picked and what you rejected.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `watch.py`, `test_watch.py`, `watch-design.md`, and **at
   most one new** `dev/capture/*.mjs` plus the `justfile`'s `DEFAULT_GUARDS` line **only if** you
   write a guard (see criterion 6). `git status --porcelain` shows nothing else.
   **`git diff --stat file-formats.md review_artifact.py test_review_artifact.py
   .dreamwork/questions.md` is empty** — the first three have a live owner and the fourth is the
   human's channel, which I write.
2. **`python3 -m pytest test_watch.py -q -p no:randomly` exits 0**, with at least:
   - `test_a_date_only_question_shows_one_figure_not_two`
   - `test_a_timed_timestamp_still_shows_two_figures`
   - `test_an_entry_dated_today_does_not_read_as_stale`
3. **THE CRITERION I CARE ABOUT MOST — assert the *precision* of the input at runtime, not a
   literal.** The first test must derive, from the fixture it uses, that the entry genuinely
   carries **no time**, and assert that before asserting the rendering. A literal date string
   tuned to today's fixture is a check with an invisible expiry date, and **this whole defect
   exists because `#385`'s criterion asked only that two fixture ages *differ* — they differed
   by two days and were both wrong by eight hours.** A check that compares outputs to each other
   cannot find a systematic error.
4. **The second test's expected value comes from outside the code that produces it.** Feed a
   timestamp you *chose* (say, 14 hours and 3 minutes before a fixed `now`) and assert the
   rendered string against **the number you chose** — not against anything `watch.py` computes.
   State the offset and the exact rendered string in your report.
5. **Three discriminating reds**, each with the exact failing test name and confirmation
   neighbours stayed green:
   - render a date-only entry with two figures ⇒ the first test fails, **and its message must
     show the wrong string**, not merely "not equal";
   - collapse timed entries to one figure ⇒ the second fails;
   - restore whatever today's-entry behaviour you replaced ⇒ the third fails.
   Separate injections, restored from a `cp` snapshot — **never** `git checkout -- `.
   **A green red-run is a finding, never a relief**, and **grep for your injection to confirm it
   reached the code**: mine for another task this morning targeted a CSS rule that did not exist
   and the check passed.
6. **`transitions.md` governs anything that appears, disappears or changes, and it has no
   exceptions.** If your change only alters the *text* of an existing string, that is not a
   transition — **say so explicitly and write no guard.** If anything appears or moves, it needs
   one, and then the `justfile`'s `DEFAULT_GUARDS` is granted because a guard that is not
   registered gates nothing. **Your guard port is `39894`** if you need it; another lane holds
   39893. Load manufactures **false reds only** for these guards, so a green under load is
   conclusive and a red needs a re-run at low load — check `cut -d' ' -f1-3 /proc/loadavg`.
7. **`just audit-styleguide` passes** and `watch-design.md` documents the departure from the
   two-figure grammar **in the same commit**.
8. **All three open questions still render.** `watch.parse_open_questions` must return the same
   **3** entries it does today and `/questions` must show all of them — a display change that
   drops an entry it cannot classify is the worst outcome available, because `watch.py` renders
   an unreadable file as *"nothing to answer"*. Assert the count; say what it was before and
   after.
9. **`python3 lint.py` exits 0**, run as its **own command** — never in the same shell command
   as a `git commit`.

## The hollow outcome

**A test whose expected value is computed the way the display computes it.** Green,
thorough-looking, and blind to precisely this bug — it is `#385`'s check rebuilt. Criteria 3 and
4 exist for it and they are the two I will read first.

## The rules that matter most here

**One value must come from outside the system.**

**Before you report an edge case, enumerate its neighbours.** Yours: an entry dated **tomorrow**
(clock skew — `#385` clamps negatives to 0, verify that still holds); an entry whose date is
**malformed**; the **Answered** section's entries, which carry dates too and are on the same
page; and an entry exactly **24h** old. Say what each does.

**`grep -c` exits 1 when the count is zero**, so an `&&` chain reports a skipped tail as a pass.

**One trap that cost a coordinator a restored file this morning:** never
`git show <ref>:watch.py > watch.py`. The shell truncates the target *before* git runs, so a bad
ref leaves `watch.py` **empty** and git's error looks unrelated. Use a `cp` snapshot.

## Files

**Yours:** `watch.py`, `test_watch.py`, `watch-design.md`, and — only if criterion 6 applies —
one new `dev/capture/*.mjs` and the `justfile`'s `DEFAULT_GUARDS` line.

**Read, do not edit:** `.dreamwork/questions.md` (the data — **do not reformat it**; if your
change implies editing entries, report it and I will make the edit), `transitions.md`,
`file-formats.md`, `justfile`, `CLAUDE.md`, `.dreamwork/lessons.md`, `.dreamwork/tasks.md`
(`#392`, `#385`).

**Never touch — live owners right now:** `review_artifact.py`, `test_review_artifact.py`,
`file-formats.md`, `dev/capture/fixture/**`, `dev/capture/markrail.mjs` (**#396**);
`.dreamwork/docs/plans/watch-client-extraction.md` (**#397**); `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single
append below), `bin/ud-dw-generate`, `lint.py`, `test_lint.py`.

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live. **Do not generate load
  deliberately** — one runs browser guards.
- Guards import playwright by **absolute path**; see the top of any `dev/capture/*.mjs`.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for **new** files —
  `--only <directory>` silently skips untracked ones. A bare `git commit` after `git add` commits
  the whole index and will bury a concurrent lane's staged work. Both happened in this tree.
  **Do not push.**
- Use **`fix(#392a): …`**. `dream(...)` is reserved for a commit that lands a dream journal; if
  you write one, **name it in its own `git commit --only <path>`**.
- Cap yourself at roughly **35 minutes**. **Priority order: criteria 3 and 4's tests first, then
  the degradation, then the today case, then the styleguide.** Writing those two tests first is
  deliberate — they are the instrument this defect got past, so building them first means
  everything after is measured by them. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the file,
because other agents append concurrently:

`.dreamwork/inbox.md`

State: each acceptance criterion and whether it holds; **the runtime precondition your first test
asserts** and **the offset you chose for the second plus the exact string it rendered** (criteria
3 and 4 — I read these first); the three reds verbatim with exact test names and which neighbours
stayed green; **what you chose for an entry dated today and what you rejected**; whether the
change is a transition and so whether you wrote a guard; the open-question count before and
after; what each of the four neighbour cases does; the exact `watch-design.md` text you added;
the load at which any guard verdict was taken; whether you wrote the hand-off line; the
production line named per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
