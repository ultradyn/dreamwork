# Brief — #401-audit: which task-id forms does each reader actually accept?

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

**This task is READ-ONLY on code.** You write **one** research document and change no
parser, no check, and no test. Do not "fix" what you find — three of the findings this audit
generalises are already filed and one is blocked on a live owner. **A lane that starts fixing
has failed the brief regardless of how good the fix is.**

**When you land your commit**, also append **one line** to `.dreamwork/handoffs.md` under
`## Pending`:
`- **#401** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by ccc @grok — <one line, what landed>`
Append only (`cat >>`), never rewrite — other sessions append concurrently. Do **not** touch
`## Folded` and do **not** write to `.dreamwork/tasks.md`. **Note the irony:** the defect this
audit generalises is that a hand-off line with an unexpected id shape is silently dropped by
every reader. Write yours with the plain numeric `#401` above so it parses.

## The chain above this task

- **DREAMWORK.md goal**: the loop's durable state must tell the truth about the loop. A record
  whose readers silently drop entries is worse than no record, because it looks healthy.
- **Session goal**: find the next silent-drop before it costs an hour, rather than after.
- **This task**: the audit half of `#401`. Read `#401`, `#399` and `#395` in
  `.dreamwork/tasks.md` — they are three instances of the class you are measuring.

## Why this exists — three findings in one day, all the same shape

Every one of these was a parser whose idea of a task id was narrower than the ledger's:

1. **`#395`** — the `related:` marker regex captures **one** bold span, so
   `related: **#393**, **#394**` silently yields only `#393`.
2. **`#399`** — `watch._landed_ids` treats **any** bare bolded id in a landed section as landed,
   so **7 open tasks are reported landed**. Its docstring's exclusion only works when prose puts
   *words* inside the bold, and this ledger's natural voice does not.
3. **`#401`** (filed an hour ago) — all three hand-off patterns are `#(\d+)`, so
   `- **#392a** · landed …` yields `pending=[]` **and** `malformed=[]`. Invisible to the parser
   **and** to the fallback validator whose stated job is to catch an unrecognised head.

**The question nobody has asked: how many more are there?** That is a matrix, it is mechanical,
and it is exactly what a read-only sweep can settle in one pass.

## What to produce

A matrix, **rows = every id-matching pattern in the codebase, columns = every id form that
actually occurs in the repo**, each cell filled in by **running** the pattern against the form.

### Criterion-by-criterion, and criteria 1 and 3 are the ones I read first

1. **The id forms are DERIVED from the repo, not from my list.** Give the commands you used and
   the **occurrence count** of each form across `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
   `.dreamwork/answers.md`, `.dreamwork/handoffs.md`, `.dreamwork/docs/briefs/*.md`,
   `.dreamwork/dreams/**`, and **git commit subjects** (`git log --format=%s`). Forms I already
   know occur: plain `#392`; sub-id `#392a`; combined head `#367/#392`; prose-in-bold
   `**#96 stage 1**`. **Your list must contain at least one form I did not name** — if after real
   effort it does not, say so explicitly and show the derivation, because "I found no others" is
   a result and "I did not look" is not, and they read identically.
2. **The patterns are found by enumeration, not by memory.** Sweep `watch.py` and `lint.py` for
   every compiled regex or parse site that extracts or matches a task id. **State how many you
   found.** A count is the one thing a silent skip cannot fake.
3. **THE CRITERION I CARE ABOUT MOST — every cell is produced by EXECUTING the pattern, never by
   reading it.** Import the real module (`importlib` on `watch.py`; `lint.py` imports the parser
   from `watch`, so do not copy either) and apply each pattern to each form in a small harness.
   **State the harness in the document so I can re-run it.** A matrix derived by eye is the
   hollow outcome — reading a regex correctly is precisely the skill that failed three times
   today, and my own reading of `HANDOFF_BARE_RE` as a working fallback was wrong until I ran it.
4. **Every reject is classified SILENT or LOUD**, and only for readers that actually read a file
   where that form occurs. Silent means: no output, no WARN, no ERROR — indistinguishable from a
   clean parse. **The silent rejects are the findings; the loud ones are working as designed.**
   Give the silent count as a number.
5. **Rank the silent rejects by whether a human-visible surface loses information**, and say
   which surface. A dashboard panel that drops a row outranks an internal set that is never
   rendered.
6. **Independently re-derive `#401`'s measurement** and say whether it reproduces: does
   `- **#392a** · landed \`abc\` · 2026-07-28 09:40 · by ccc @glm52 — x` give `pending=[]` and
   `malformed=[]`? **If you get a different answer, say so plainly and show it** — I would rather
   be corrected than confirmed, and a lane refuted me twice today to the repo's benefit.
7. **Files touched, and only these:** `.dreamwork/docs/research/2026-07-28-task-id-grammar-audit.md`
   (new) and one line in `.dreamwork/handoffs.md`. `git status --porcelain` shows nothing else.
   **`git diff --stat watch.py lint.py test_watch.py test_lint.py .dreamwork/tasks.md` is
   empty** — the first three have live owners or are not yours, and the ledger has one writer.
8. **`python3 lint.py` exits 0** when you finish, run as its **own command** — never in the same
   shell command as a `git commit`. That has committed through a lint ERROR twice here.
9. **The document ends with the literal line `--- SUMMARY ---`** followed by a concise dot-point
   summary. He reads the summary first.

## The hollow outcome

**A table of what the regexes look like they do.** It will be mostly right, it will look
thorough, and it will miss the one cell that matters — because the two failures this audit
generalises were both "I read the pattern and it seemed fine". Criterion 3 exists for this and
it is the first thing I will check: if the document does not contain a runnable harness, the
matrix is an opinion.

## The rules that matter most here

**A count is the only thing a silent skip cannot fake.** If your sweep does not recognise a
parse site, that prints the same as a site with nothing wrong. Report *how many* patterns and
*how many* forms, so a later reader can tell coverage from cleanliness.

**A fallback validator shares the parser's blind axis.** `#401`'s whole point: the pattern that
exists to catch "a shape the grammar does not recognise" was `#(\d+)` like the grammar, so the
one class it was built for is the one class it cannot see. **When you meet a validator phrased
as "anything the parser rejected", vary the axis it shares with the parser** and check it still
fires. Expect more of these.

**Before you report an edge case, enumerate its neighbours.** Yours: an id inside a **code span**
(`` `#392` ``) rather than bold; an id with **no** `#`; a **four-digit** id (the ledger is at
#402 and will pass 1000); an id in a **link** (`[#392](...)`); and the **same** form appearing in
a file the reader does not read. Say what each does.

**`grep -c` exits 1 when the count is zero**, so an `&&` chain reports a skipped tail as a pass —
and you are counting things whose counts can legitimately be zero.

## Files

**Yours:** `.dreamwork/docs/research/2026-07-28-task-id-grammar-audit.md` (new — `git add` it
before `git commit --only`, because `--only <directory>` silently skips untracked files), one
appended line in `.dreamwork/handoffs.md`.

**Read freely, do not edit:** `watch.py`, `lint.py`, `test_watch.py`, `test_lint.py`,
`.dreamwork/tasks.md` (`#401`, `#399`, `#395`, `#381`), `file-formats.md`, `.dreamwork/handoffs.md`,
`.dreamwork/questions.md`, `.dreamwork/answers.md`, `.dreamwork/docs/briefs/*.md`,
`.dreamwork/dreams/**`, `justfile`.

**Never touch — live owners right now:** `watch.py`, `test_watch.py`, `watch-design.md`
(**#392a**); `.dreamwork/docs/plans/watch-client-extraction.md` (**#397**); `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single
append below), `bin/ud-dw-generate`, `SKILL.md`, `.dreamwork/lessons.md`.

**Explicit non-goal, already noted, do not fix:** `.dreamwork/docs/research/` has **no**
`doc-map.md` row (the existing row is for root-level `research-*.md`) and 11 files already sit
there unmapped. Adding your file needs no row. Mention it in your report if you like; the
coordinator is filing it.

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live. **Do not generate load
  deliberately** — one runs browser guards and load manufactures **false reds** for it. Check
  `cut -d' ' -f1-3 /proc/loadavg` before running anything heavy; it was ~17 at dispatch.
- **You need no server, no port, and no guards.** Do not run `just guards`; a port is held and
  nothing in an audit renders.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after `git add` commits
  the whole index and will bury a concurrent lane's staged work — that happened in this tree,
  at `12f47e3`. **Do not push.**
- Use **`docs(#401): …`**. `dream(...)` is reserved for a commit that lands a dream journal; if
  you write one, **name it in its own `git commit --only <path>`**.
- Cap yourself at roughly **30 minutes**. **Priority order: the form derivation (1) and the
  executed matrix (3) first, then the silent/loud classification (4), then the ranking (5), then
  the neighbours.** The matrix is what makes this evidence rather than an opinion, so build the
  harness before writing any prose. **Report what you did not reach** — an honest partial matrix
  with its coverage stated beats a complete-looking one.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the file,
because other agents append concurrently:

`.dreamwork/inbox.md`

State: the path you wrote; **the number of patterns found and the number of id forms derived**
(criteria 1 and 2); **the harness you used** (criterion 3 — I read this first); **the silent
reject count and the top three ranked findings**; whether `#401`'s measurement reproduced **and
loudly if it did not**; the form you found that I did not name, or that you found none; what each
of the five neighbour cases does; whether you wrote the hand-off line; and what you are not
confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
