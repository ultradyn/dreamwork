# Brief — #386: `gitrow` opens 0px under load, so the check is right and the gesture is not

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first, and
**`transitions.md`** — it opens with how to check motion and why the obvious way
does not work, which is the whole subject here.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
- **Session goal**: the guard suite is the only verification this repo has —
  there is no CI — so every "verified" claim about the dashboard is exactly as
  strong as the guards are.
- **This task**: #386, split deliberately out of #383 rather than papered over
  inside it.

## What is established — inherit it, do not re-derive it

#383 (landed `0d92862`) fixed a **real** shared bug in three motion guards: they
counted *distinct sampled values* and required `distinct >= 8`, so a genuinely
smooth travel that happened to be sampled seven times failed. The count was never
a property of the motion. They now use `between(frames, first, last)` — at least
one frame strictly between the endpoints, plus a vacuity span floor.

After that fix, measured by the #383 lane:

| guard | isolated | under moderate load (3 busyloops) |
|---|---|---|
| `revieworder` | 3/3 | 3/3 |
| `burndown` | 3/3 | 3/3 |
| **`gitrow`** | 3/3 | **2/3** |

**The residual failure is a different fault from the one #383 fixed, and this is
the key fact:** the failing run showed a **0px open** — a vacuous `displaced at
all` / 0px travel. The row never opened. So there was genuinely no motion, and the
check was **right** to fail. The instrument is not hollow; the **gesture did not
run**.

That distinction is the whole task. Do not treat this as a flaky assertion.

## What I want, in this order

1. **Reproduce it, and confirm the diagnosis rather than assuming it.** Run
   `gitrow` repeatedly under moderate load and record pass/fail per run. When it
   fails, capture **why**: was the row's height genuinely 0 at every sampled frame,
   or did the click throw, or did the element not exist yet? Numbers and the actual
   failure text, not impressions. **If it turns out the travel is real and the
   sampling is still wrong, that is a finding — say so loudly**, because it means
   #383's fix is incomplete and that changes what happens next.
2. **Find why the click does not land.** The likeliest candidate, which you should
   confirm or refute: the row's own **arrival** transition is still in flight when
   the click is dispatched, so the target is moving or not yet interactive.
   Another lane found a related thing today in `draft.mjs` — a `dreams (1)` label
   intercepting pointer events on `#cmdtext`. Pointer interception is a live
   pattern on this page, so check for it.
3. **Fix by waiting for the condition, not for time.** A fixed `setTimeout` where
   the code waits on a state change is the class of check this repo keeps finding
   hollow (`CLAUDE.md`, `.dreamwork/lessons.md`). Wait for the row to be ready —
   and make the failure message say what it actually saw, so the next person does
   not have to re-derive this.

**Do not widen the motion assertion.** Making the travel check tolerate 0px would
make the guard unable to see a real snap, which is precisely the regression it
exists to catch. If the honest outcome is "the gesture is now reliable but I could
not prove it under load", say that.

## Acceptance criteria — binary, and I will check each one

1. **A run-by-run table**: `gitrow` isolated (≥5 runs) and under moderate load
   (≥5 runs), pass/fail each, with the failure text for every failure. This is the
   deliverable even if the fix does not land.
2. **The cause is named**, with the evidence that distinguishes it from the
   alternatives you ruled out. "Probably a race" is not a cause.
3. **After your fix, ≥5/5 under the same moderate load** that previously produced
   2/3. State how you generated the load, so the number is reproducible.
4. **The motion assertions are unchanged in strictness.** Show me the diff of the
   assertion lines; if any tolerance moved, justify it explicitly or revert it.
5. **The red-proof still bites.** #383's red for this guard was a page-injected
   snapping `travelCard`, which must still produce
   `FAIL opening: ...and it travels there rather than teleporting`. Re-run that
   injection **after** your change and confirm it still fails by name. **If your
   fix makes the sabotage pass, you have hollowed the guard — report that
   immediately.** Restore from a `cp` snapshot, never `git checkout --`.
6. **Name the production line** that would have to change for your version of the
   check to fail. If you cannot name one, there isn't one.
7. **`python3 lint.py` exits 0**, run as its **own command**, never in the same
   shell command as a `git commit`.

## Files

**Yours:** `dev/capture/gitrow.mjs`.

**Read freely, do not edit:** `dev/capture/dreamfade.mjs`, `revieworder.mjs`,
`burndown.mjs`, `report.mjs` (reference idioms — read them, do not change them),
`transitions.md`, `justfile`.

**Never touch — every one of these has a live owner right now:** `watch.py` (a
lane holds it for #300; **if your fix must live in `watch.py`, STOP and report
that** — this is the one hard boundary), `user_events/` and
`test_user_events_*.py` (two lanes), `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/status.json`, `.dreamwork/inbox.md` (except
the single append below), `bin/ud-dw-generate`.

## Operational constraints

- **Your guard port is `39895`.** Run as
  `DREAMWORK_GUARDS="gitrow" DREAMWORK_HUB_GUARDS="" just guards 39895`.
  **Never** the full sweep and never the default port — three other lanes are live
  and one of them is using 39891.
- The guards import playwright by **absolute path**; see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.
- Limit builds/tests to **2 threads**.
- **The load asymmetry is useful and you should exploit it:** a dropped
  intermediate frame causes false **reds**, never false greens. So a green under
  load is conclusive evidence, and a red under load needs a re-run before you
  believe it. This is also why "under load" is the right condition to test in
  rather than something to avoid.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after
  `git add` commits the whole index, not the paths you named, and will bury a
  concurrent lane's staged work — that happened in this tree an hour ago. **Do not
  push.**
- Cap yourself at roughly **30 minutes**. **Characterisation alone (criterion 1 and
  2) is a perfectly good increment to land** if the fix does not fit — a named cause
  with numbers is worth more than a hurried fix.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: the run-by-run tables; the named cause and the evidence that ruled
out the alternatives; what you changed; **the re-run of #383's sabotage red and the
exact check name that failed**; the production line named; whether you are leaving
it flaky and why; and what you are not confident about. An honest "not confident
about X, and here is what would settle it" is worth more than a confident guess.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
