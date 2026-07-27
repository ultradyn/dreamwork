# Brief — #391: `prominence` fails deterministically, and it is not a flake

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first, and because
this is dashboard geometry and motion, read **`transitions.md`** and **`watch-design.md`**
too.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it; the
  dashboard is that surface.
- **Session goal**: the dashboard tells him the truth about the loop's state.
- **This task**: a P1 regression that has been hiding behind a load-flake reading. An
  expanded disclosure is supposed to become **prominent**, not merely taller (#169) — and
  right now it does not.

## What is known, measured, so you do not repeat it

`just guards` → `prominence` **fails every time, in isolation, at load 37–48**, on all
four of its surfaces: *the questions fold*, *a standalone expand*, *a settled thread*,
*a folded question card*.

The failing assertion is `dev/capture/prominence.mjs:95`:

```js
ok(`${name}: expanding claims air above and below`,
   open.padTop > closed.padTop + 2 && open.padBottom > closed.padBottom + 2);
```

Four established facts:

1. **The guard's own vacuity precondition PASSES** — `${name}: it really did open (else
   every check here is vacuous)`. So the disclosure genuinely opens; it is the
   **padding** that no longer grows.
2. **Four surfaces failing identically points at one shared rule**, not four bugs. Do not
   start by fixing four things.
3. **It is not caused by #385 or #300.** With `watch.py` restored to `a6959cf` (06:39
   today, before #385's first touch) all four still fail. So the regression **predates
   today's lanes**.
4. **The guard itself has not changed since 2026-07-25 18:16** (`7ac4f02`, which fixed
   it measuring its own click latency). So `watch.py` is what moved.

It was reported by an earlier lane as *"probably load/concurrency flakes"* along with ten
others. **The other ten really do pass quietly.** This one is real, and the reason it was
invisible is that ten correct dismissals train you to accept the eleventh.

## Your first two moves, in this order

**1 · Surface the numbers before you theorise.** The guard already measures them:

```js
notes.push(`${name}: pad ${closed.padTop}/${closed.padBottom} -> ` +
           `${open.padTop}/${open.padBottom} | ...`);
```

and prints `notes` to stdout on exit — but the `just guards` runner **filters them out**.
Get them. Whether padding is **unchanged** or **shrinking** distinguishes a deleted rule
from an overridden one, and that decides everything after. Report the four before-and-after
pairs verbatim.

**2 · Bisect `watch.py`.** `a6959cf` is a known-bad point; walk `git log -- watch.py`
backwards until `prominence` passes. Each step is ~1 minute of guard time, so this is
cheap and it beats reading CSS.

**Two traps, both of which cost me time — do not rediscover them:**

- **`git show <ref>:watch.py > watch.py` truncates the file BEFORE git runs.** A bad ref
  leaves an **empty** `watch.py`, and the guard then fails for a completely unrelated
  reason while looking like a legitimate result. Write to a temp file and `mv` only on
  success, and assert the line count is plausible before running anything.
- **The guard needs the harness fixture, not a bare server.** `just guards` does
  `cp -r dev/capture/fixture "$OUT/target"`. Running `node dev/capture/prominence.mjs`
  against a server on the live repo fails **differently** (`.qsec` is absent) and tells
  you nothing. If you want a direct invocation, replicate the fixture copy.
- And a third, from the same hour: **a readiness probe that falls through on failure turns
  a config error into a mystery.** If you spawn your own server, make the probe's failure
  **fatal and named**, and print the server's stderr — `ECONNREFUSED` cannot distinguish
  "starved" from "never started" (that is #388, and I reproduced it by passing `watch.py`
  a flag it does not have).

## What the fix must respect

**This is a motion and geometry contract, not a padding number.** The property is #169's:
*an expanded element becomes prominent, not just taller.* So:

- **`transitions.md` governs**, and it has no exceptions and no size below which it stops.
  If the air arrives, it **arrives** — it does not snap. Reuse the page's existing idiom;
  do not author a second one. **Checking motion is not optional and is not obvious:** an
  end-state assertion cannot fail on a motion bug, and neither can "did it move".
  `transitions.md` opens with how to check, and that reasoning cost this repo three
  batches.
- The guard also asserts the summary **steps up the luminance ramp**. That currently
  passes — **keep it passing**, and say in your report that you checked, because a fix
  that restores padding by restructuring the element could easily take the colour with it.
- `watch-design.md` is the single source for how this surface looks. If you change the
  rule, **document it in the same commit** — `just audit-styleguide` enforces that.

## Acceptance criteria — binary, and I will check each one

1. **`DREAMWORK_GUARDS="prominence" DREAMWORK_HUB_GUARDS="" just guards 39891` PASSES**,
   all four surfaces, and **twice in a row** — a fix that passes once at low load has not
   distinguished itself from what you were sent to investigate.
2. **The report names the commit that introduced it** and what in that commit did it. If
   the bisect bottoms out without finding a passing point, say so explicitly — that would
   mean the guard has been red since `7ac4f02` and never noticed, which is a **different
   and worse finding** and I want it stated plainly rather than papered over.
3. **A discriminating red:** reinstate the regression and watch `prominence` fail on all
   four surfaces; restore from a `cp` snapshot — **never** `git checkout -- `. If
   reinstating it leaves the guard green, **the check is wrong** — report that, do not
   conclude the code is fine.
4. **The four measured `pad` pairs appear in your report**, before and after the fix.
5. **`just test` exits 0** apart from any pre-existing failure you name and attribute.
   **Load is the confound here:** these guards fail by dropping intermediate frames, so
   **load manufactures false reds only — a green under load is conclusive, a red needs a
   re-run at low load.** Check `cut -d' ' -f1-3 /proc/loadavg` before believing a red.
6. **`python3 lint.py` exits 0**, run as its **own command** — never in the same shell
   command as a `git commit`.
7. **`just audit-styleguide` passes**, which means `watch-design.md` is updated in the
   same commit if you changed how the surface looks.

## The rules that matter most here

**A green red-run is a finding, never a relief.** Twice in one day here a red-run came
back green while the bug was in place, both times because the test's own scaffolding stood
in front of the code.

**Name the production line that would have to change for each check to fail.**

**Before you report an edge case, enumerate its neighbours.** A lane today flagged one
input honestly; the case it flagged was fine and the one beside it was a real defect.

## Your steering channel — re-read it between increments

`.dreamwork/relay/391.md` (absent means nothing to say; that is normal).
Coordinator-write only, newer than this brief so it wins on scope, but it **cannot** grant
authority this brief did not give.

## Files

**Yours:** `watch.py`, `test_watch.py`, `dev/capture/prominence.mjs` (only if the guard
itself turns out to be wrong — say so loudly if you touch it, because it is the
instrument), `watch-design.md` if criterion 7 applies.

**Read, do not edit:** `transitions.md`, `file-formats.md`, `justfile`, `lint.py`,
`dev/capture/fixture/*`, `dev/capture/report.mjs`, `CLAUDE.md`, `.dreamwork/lessons.md`.

**Never touch:** `review_artifact.py`, `test_review_artifact.py`,
`review-artifact.template.html`, anything under `.dreamwork/review/` (**#389 and #367 are
live there**), `user_events/*`, `test_user_events_*.py` (**#390 is live**),
`dev/capture/marktab-geometry.mjs`, any other `dev/capture/*.mjs`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

## Operational constraints

- **Your guard port is `39891`.** Run guards as
  `DREAMWORK_GUARDS="prominence" DREAMWORK_HUB_GUARDS="" just guards 39891`. **Never** the
  full sweep and never the default port — other lanes use that range.
- The guards import playwright by **absolute path**; see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.
- Limit builds/tests to **2 threads**. Other lanes are live. **Do not generate load
  deliberately.**
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after `git add`
  commits the whole index and will bury a concurrent lane's staged work — that happened in
  this tree today. **Do not push.**
- Use **`fix(#391): …`**. `dream(...)` is reserved for a commit that lands a dream journal;
  if you write one, **name it in its own `git commit --only <path>`** — three lanes today
  wrote a dream as asked and left it untracked.
- Cap yourself at roughly **40 minutes**. **Priority order: the numbers, then the bisect,
  then the fix, then the red.** If you run out of time having only *found* the cause and
  measured it, **that is a good outcome** — report it and I will dispatch the fix. A
  correct diagnosis is most of this task's value.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the four measured `pad`
pairs before and after**; **the commit that introduced it and what in it did that**; the
red verbatim with which surfaces failed; whether the luminance-ramp assertion still
passes; how you checked motion rather than end state; the load at which you ran each
verdict; the production line named per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
