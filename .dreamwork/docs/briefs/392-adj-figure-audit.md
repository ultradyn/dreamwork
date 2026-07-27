# Brief — audit every figure the deployed dashboard renders against a value from outside it

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

**This task writes a MEASUREMENT REPORT and changes no code.** You are not fixing
anything. Two other lanes hold `watch.py`, `review_artifact.py` and their tests right
now, so a fix from you would collide by construction. A finding is your deliverable.

## Why this exists — a defect found 20 minutes ago, and it is a class not an instance

`#385` added a humanized age (`02d 08h ago`) beside each question's date. It shipped
correctly: a guard proved the headline shows an age, a fixture proved two entries' ages
**differ**, and I re-ran its discriminating red myself and it was a good one.

Then I looked at the deployed page. A question I had filed **fourteen minutes** earlier
rendered as **`08h 17m ago`**, because a `questions.md` headline carries a date and no
time, so `data-ct` resolves to **midnight**. Filed as `#392`.

**The two fixture ages differed by two days and were both wrong by eight hours.** The
check could not see it, because every value it compared came from inside the system.

So the question you are answering is: **what else?** Every count, age, timestamp, sum and
percentage on that page is a candidate, and none of them has ever been compared against a
number derived independently.

## The one rule that makes this task worth anything

**You may not derive an expected value by calling, importing, or reading the logic in
`watch.py` that produces it.** That is circular and it would reproduce the #392 failure
exactly — the check and the code agreeing about the same wrong thing.

Every expected value must come from the **source of truth**, computed your own way:

- counts of tasks → `grep`/`python` over `.dreamwork/tasks.md`'s `## Open` section
- question and answer counts → over `.dreamwork/questions.md` / `answers.md`
- dream and review counts → `ls` the directories
- ages and timestamps → the clock, `git log`, or file mtimes, **and state which**
- commit shas and subjects → `git log`
- process ids, ports → `pgrep`, `ss`

If you find yourself writing `from watch import ...` to get an expected value, **stop —
that is the bug**. (Importing `watch` is fine for *nothing* in this task; you need no
Python from it at all.)

**State the command that produced each expected value.** A row without one is not a
measurement, it is an opinion.

## What to audit, and where the figures live

The page is **client-rendered**: `GET /` returns a shell and the browser fetches
**`/data.json`**, then JS builds every visible figure from it. So there are **two seams
and you must check both**, because #392 lived in the gap between them:

1. **Payload vs truth** — is the number `/data.json` carries correct? (`#392` was here:
   the payload's `ct` was midnight.)
2. **Render vs payload** — does the page display what the payload says? (A correct payload
   rendered with the wrong unit, a wrong rounding, or a stale cached value is a distinct
   defect, and only pixels can show it.)

`curl -s http://127.0.0.1:35110/data.json | python3 -m json.tool` is your starting point.
Numeric and date-ish fields I already know are there, as a floor and not a ceiling —
**enumerate them yourself, do not trust this list to be complete**:

`generated`, `open_questions`, `questions_open[]`, `answered_entries[]`, `answers_open[]`,
`answers_answered[]`, `dreams[]`, `dreams_archive[]`, `reviews[]`, `linkable_paths[]`,
`status.queue.in_progress`, `status.queue.pending`, `status.last_tick`,
`status.deployed.*`, `git[]`, `deployed.rev`, `deployed.missing[]`,
`burndown.buckets[]`, `burndown.step`, `burndown.open`, and every `data-ct` /
`ct` timestamp on any entry.

**`burndown` deserves particular attention** and I have not checked it at all: it claims
18 buckets at a 14400s step and an open count of 126. Does the bucket series actually
describe the queue's history, and does its final bucket agree with the live open count?
A burndown that disagrees with the queue it is drawn from is the same class as #392 with
a chart in front of it.

## The visual half — you have vision, so use it

Some of these are only findable in pixels. Screenshot the deployed page at **1280x900**
and at **420x900**, on `/`, `/questions` and `/answers`, and read the numbers *as he
would*:

- Does any figure render with an implausible magnitude, a missing unit, a doubled unit,
  or an obviously stale value?
- Does any age read as more precise than its input can support? (That *is* #392: `08h 17m`
  claims minute precision from a date-only source. **Look for its siblings** — anywhere a
  coarse input is rendered at a fine precision.)
- Is any count clipped, truncated, or overlapping at 420px?
- Does a figure that should be zero render as blank rather than `0`? A blank where a number
  belongs is the worst failure shape available because it looks like an absence of news.

**A screenshot is required evidence for every visual finding.** Save them beside your
report and reference them by path.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:**
   `.dreamwork/docs/measurements/2026-07-28-0830-dashboard-figure-audit.md` (new) and
   PNGs in that same directory. **`git status --porcelain` shows nothing else** — no
   `watch.py`, no test file, no styleguide, no ledger. Both are owned right now.
2. **At least 20 distinct figures audited**, each a row in a table with **four** columns:
   the figure (and where it appears), what the page/payload shows, the independently
   derived expected value, and **the exact command that derived it**. Fewer than 20 with a
   stated reason is acceptable; fewer than 20 silently is not.
3. **Both seams covered.** At least 15 rows for payload-vs-truth and at least 5 for
   render-vs-payload, and say which each row is.
4. **Every disagreement is reproduced twice** — once by your command, once by a second
   independent route (a different tool, a different derivation) — because a single
   derivation that disagrees is as likely to be your bug as theirs. Say both routes.
   **If your two routes disagree with each other, that is the finding**, and say so
   rather than picking the one you like.
5. **Screenshots exist and are referenced**: at minimum `/`, `/questions`, `/answers` at
   1280x900. Name the file for each.
6. **You state, explicitly, how many figures you checked and found CORRECT.** An audit
   that reports only problems is unfalsifiable — I cannot tell a clean page from a lazy
   pass. The correct ones are the evidence that you looked.
7. **No POST, no write, no restart.** You must not hit `/command`, `/ask`, `/answer`,
   `/comment`, or `/tint`; must not `pkill`; must not `just deploy`; must not start a
   second server on 35110. **`GET` only.** Two lanes are mid-flight and the running
   dashboard is the human's live window.
8. **`python3 lint.py` exits 0** when you finish — proving you left the tree as you found
   it. Run it as its own command.

## The hollow outcome, which I will check for first

**An audit that recomputes each figure the way `watch.py` computes it, and finds
everything correct.** It will be long, it will look thorough, and it will be worth
nothing — it is the #392 check again with more rows. The tell is an expected value whose
derivation mirrors the production code's derivation.

The second hollow outcome: **auditing only the fields that are easy to derive** (list
lengths) and skipping every timestamp. The timestamps are where the known defect was.
**Every `ct` value on the questions page must be a row**, and for each one say what its
source file actually carries — a date, a datetime, or nothing.

## Known-good anchors, so you can calibrate

I fixed two of these myself at 08:23 and they are now correct; if your audit says
otherwise, **your method is wrong and that is a useful finding about your method**:

- `status.queue` is `{in_progress: 2, pending: 124}` and the ledger's `## Open` section
  has **126** entries. `in_progress + pending == 126` must hold.
- `status.current_task_ids` is `[367, 381]` — the two live lanes. Both must appear under
  `## Open`.
- `status.deployed.pid` is `1264649` and it must be a **live** `python3 …watch.py`
  process. Check with `pgrep -af watch.py`.

And one known-stale thing that is **not** a defect, so do not file it: `deployed.rev`
(top level) tracks `HEAD`, which moves with ledger commits that do not touch `watch.py`.
Only a `git diff <deployed-rev>..HEAD -- watch.py` that is non-empty means the served page
is behind.

## The rules that matter most here

**One value must come from outside the system.** That is this entire task in one line.

**Before you report an edge case, enumerate its neighbours.** A lane flagged one input
honestly yesterday; the case it flagged was fine and the one beside it was a real defect.

**`grep -c` exits 1 when the count is zero**, so a verification chain joined by `&&`
reports a skipped tail as a pass. This will bite you in this task specifically, because
you are counting things and some counts are legitimately zero (`answers_open` is `0`).

**Say what you are not confident about.** An honest "I could not derive an independent
value for X, and here is why" is worth more than a fabricated row.

## Files

**Yours:** `.dreamwork/docs/measurements/2026-07-28-0830-dashboard-figure-audit.md` (new)
and PNGs in that directory. **Nothing else.** Do not create a new directory — that one
exists, and a new file in a registry-checked directory reddens the other live lanes'
`lint.py` baseline until it is registered.

**Read freely, do not edit:** `watch.py` (read it to know *what* is rendered and where —
just never to derive an expected value), `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/answers.md`, `.dreamwork/status.json`, `file-formats.md`, `watch-design.md`,
`.dreamwork/lessons.md`.

**Never touch — live owners right now:** `review_artifact.py`,
`test_review_artifact.py`, `review-artifact.template.html`, `watch-design.md`, anything
under `.dreamwork/review/` (**#367 increment 2a**); `watch.py`, `test_watch.py`,
`lint.py`, `test_lint.py`, `SKILL.md`, `file-formats.md` (**#381**);
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`, anything
under `dev/capture/`.

## Operational constraints

- Playwright must be imported by **absolute path**:
  `/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs`.
  A bare `import ... from 'playwright'` will not resolve. Look at the top of any
  `dev/capture/*.mjs` for the idiom — **read them, do not edit them.**
- **Do not run `just guards`.** Ports 39893 and 39896 are held by the two live lanes, and
  `just guards` copies a fixture target anyway, which is the opposite of what you want:
  you are auditing the **real** page with the **real** data.
- Limit builds/tests to **2 threads**. Two lanes are live. **Do not generate load
  deliberately** — one runs browser guards and load manufactures false reds for it.
- **Commit with `git commit --only <paths> -m …`**, and **`git add <file>` first** for your
  new files — `--only <directory>` silently skips untracked ones. A bare `git commit` after
  `git add` commits the whole index and will bury a concurrent lane's staged work. Both
  mistakes happened in this tree yesterday. **Do not push.**
- Use **`docs(#392): …`** for your commit.
- Cap yourself at roughly **30 minutes**. **Priority order: the timestamps first, then the
  burndown, then the counts.** The timestamps are where the known defect was and the
  burndown is entirely unexamined; list lengths are the least likely to be wrong. Report
  what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: the report path; **how many figures you checked and how many were correct**;
every disagreement with both derivation routes; which `ct` values are date-only versus
datetime; your burndown verdict; the screenshot paths; whether any of the three known-good
anchors failed your method; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
