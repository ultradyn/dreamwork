# Brief — #397: is the dashboard's client worth extracting from `watch.py`? Design only.

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

**This task writes ONE plan and changes no code.** Do not edit `watch.py`. The human has not
authorised this and the whole point of the document is to let him rule on it. A lane that
starts extracting has failed the brief regardless of how good the extraction is.

**When you land your commit**, also append **one line** to `.dreamwork/handoffs.md` under
`## Pending`: `- **#397** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by ccc @glm52 — <what>`.
Append only (`cat >>`), never rewrite — other sessions append concurrently. Do **not** touch
`## Folded` and do **not** write to `.dreamwork/tasks.md`.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it; `watch.py`
  *is* that surface, which is exactly why every lane needs it.
- **Session goal**: this session ran a coordinator directing subagents, and file contention
  became the binding constraint on how much could run at once.
- **This task**: `#397`, **P1**, filed from `#264`'s evidence half.

## Why this exists — two measurements, both done, both yours to inherit

**1. `#264` measured the fan-out and the answer surprised me.** Across the whole session there
were **zero concurrent-write instances** — no two lanes ever wrote the same record. So locks,
CAS, leases, SQLite and per-record spools *"would have prevented zero of the actual damage"*.
What did cause damage was shared CPU, a shared working tree, a shared **registry**, and **one
overloaded single-writer file**. The evidence points at **modularity, not a concurrency
mechanism**, and it names the file.

**2. I then measured the file, and it is not a module-split problem.** `watch.py` is
**9,479 lines**, of which **7,142 — 75% — sit inside triple-quoted blocks**: the dashboard's
HTML, CSS and JS embedded as Python string literals. One function, `server_class` (`:262`), is
**6,798 lines**, 72% of the file; the next largest is `make_handler` at 436. The actual Python
is roughly **2,300 lines across 82 top-level defs**.

So the question is **not** "how should `watch.py` be partitioned". It is:

> **75% of the dashboard's source is a web app living inside Python string literals. Is
> extracting it into real files worth what that costs?**

That is a question he can answer. The other one is not, and if your plan drifts back into
proposing a Python module split you have answered a question nobody asked.

## What the plan must answer, and question 3 is the one that decides it

Ground every claim in line numbers. Read the code first.

1. **What is actually in there.** Break the 7,142 down: how much is CSS, how much JS, how much
   HTML? Is it one blob or several? Are the strings **interpolated** (f-strings, `%`, `.format`,
   `.replace`) — and where, because an interpolated asset cannot become a static file without a
   templating decision. **Count the interpolation sites; that number is the real cost driver
   and nobody has it.**
2. **What the extraction would look like**, concretely enough to cost: which files, how the
   server loads them, whether they are read once at import or per request (`--autoreload`
   re-execs on source mtime — say whether asset mtime should also trigger it).
3. **What it breaks, and these two are load-bearing — I checked.**
   - **`just deploy` snapshots `watch.py` alone** into `~/.cache/dreamwork/deployed/` and runs
     it from there. A `watch.py` that no longer contains its own client **deploys broken**, and
     the failure mode is a live dashboard serving a blank page. Say exactly what `deploy` must
     become, and whether the deployed thing stays a single file (concatenated at deploy time?)
     or becomes a directory.
   - **`just guards` copies `dev/capture/fixture` to a temp target and imports `watch.py`
     directly.** Say what each guard needs.
   **If your answer to either is hand-waving, say so plainly** — that is a more useful result
   than a confident plan, because these are the reasons this has not already been done.
4. **The counter-argument, stated rather than buried.** Extraction multiplies the
   **registry-coupling** failure: a new file in a checked directory reddens *other* lanes'
   baselines until it is registered. That class **did** cause damage today (`markrail`
   unregistered; six artifacts reading stale). More files means more of it. Weigh it honestly.
5. **What it costs to do nothing.** Six tasks are queued behind `watch.py` in the ledger and
   this session serialised three dispatches on it. **"Leave it" is a legitimate answer he may
   prefer**, so make the do-nothing column real rather than a straw man.
6. **The smallest useful version.** If full extraction is too expensive, is there a partial one
   that removes most of the contention — e.g. only the CSS, which is what a design lane touches
   and a request-path lane never does? **Recommend the smallest thing that would have prevented
   this session's actual collisions**, and name which collisions those were.

## What NOT to do

- Do not propose a Python module split. See above.
- Do not touch `watch.py`, or any test, guard, or the `justfile`.
- Do not design a build step, a bundler, or a dependency. This repo is stdlib-Python and
  offline-clean by contract; a plan that needs `npm` is dead on arrival and you should say so
  if you think it is unavoidable.
- Do not re-derive the two measurements above. They are done.

## Deliverable

**`.dreamwork/docs/plans/watch-client-extraction.md`**. Follow the shape of the existing plans
in that directory — read one first, e.g. `filebytes-range.md`, which is the model for a plan
that **refutes its own ledger entry's recommendation** and is better for it. If your
conclusion is "do not do this", that is a fully acceptable result and you should say it in the
first paragraph rather than at the end.

End the document with, literally:

```
--- SUMMARY ---
```

followed by a concise dot-point summary covering the decisions, costs and open questions. He
reads the summary first.

**Where you are uncertain, say so and why.** An honest *"I could not determine what `deploy`
should become, and here is what would settle it"* is worth more than a confident guess; this
repo has a documented habit of paying for the latter.

## Acceptance criteria — binary

1. **Files touched, and only these:** `.dreamwork/docs/plans/watch-client-extraction.md` (new)
   and one line in `.dreamwork/handoffs.md`. **`git status --porcelain` shows nothing else** —
   no `watch.py`, no test, no guard, no `justfile`.
2. **Question 1's interpolation count is a number**, with the method you used to get it stated
   so I can re-derive it. "Several places" fails this criterion.
3. **Question 3 names what `just deploy` becomes**, in enough detail to implement, or says
   explicitly that it could not be resolved and what would settle it.
4. **Question 5's do-nothing column names the six queued tasks by id.** They are in
   `.dreamwork/tasks.md`; find them rather than trusting the count.
5. **Question 6 names actual collisions from this session**, not hypothetical ones. `#264`'s
   research doc and `dogfood-orchestration.md` have them with shas.
6. **The document ends with the literal `--- SUMMARY ---` line.**
7. **`python3 lint.py` exits 0** when you finish — proving you left the tree as you found it.

## The hollow outcome

**A plan that recommends extraction because modularity is good.** The interesting content is
entirely in questions 3, 4 and 5 — what breaks, what gets worse, and what doing nothing costs.
A plan that spends its length on the benefits has skipped the part only reading this code can
produce.

## Files

**Yours:** `.dreamwork/docs/plans/watch-client-extraction.md` (new), one appended line in
`.dreamwork/handoffs.md`.

**Read freely, do not edit:** `watch.py`, `justfile`, `test_watch.py`, `dev/capture/*.mjs`,
`.dreamwork/docs/research/2026-07-28-parallel-lanes-evidence.md` (`#264`'s evidence — read it,
it is the reason this task exists), `.dreamwork/docs/dogfood-orchestration.md`,
`.dreamwork/tasks.md`, `.dreamwork/lessons.md`, `watch-design.md`, `transitions.md`.

**Never touch — a live owner right now:** `review_artifact.py`, `test_review_artifact.py`,
`file-formats.md`, `dev/capture/fixture/**`, `dev/capture/markrail.mjs`, anything under
`.dreamwork/review/` (**#396**); `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`bin/ud-dw-generate`.

## Operational constraints

- Limit any builds/tests to **2 threads**. A lane is live and runs browser guards; **do not
  generate load deliberately** — load manufactures false reds for it.
- **You need no server and no port.** Do not run `just guards`; a port is held and nothing in a
  design task renders.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for your **new**
  plan — `--only <directory>` silently skips untracked files and does not say so. **Do not
  push.**
- Use **`design(#397): …`**, and commit the hand-off line separately or in the same
  `--only` list; either is fine as long as `tasks.md` is untouched.
- Cap yourself at roughly **35 minutes**. **Priority order: questions 1 and 3 first, then 5 and
  6, then 2 and 4.** Question 3 is what makes this a plan rather than an opinion. Report what
  you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

State: the path you wrote; **your one-sentence recommendation** (including "do not do this" if
that is where you land); **the interpolation count and how you got it**; what `just deploy`
becomes; the smallest useful version and which of this session's collisions it would have
prevented; whether you wrote the hand-off line; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
