# Brief — the `plugcmd` guard fails, and the product is probably fine

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first — its
verification rules are not optional and they are the reason this brief is long.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report to the coordinator by the file route named at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer what
  it is doing. The browser guards are the only thing standing between his
  dashboard and a silent UI regression — there is no CI.
- **Session goal**: the guard suite is not green, and until it is, every "verified"
  claim this loop makes about the dashboard is weaker than it sounds.
- **This task**: `plugcmd` fails deterministically. Find out whether the fault is
  in the guard or in the product, and fix the one that is actually wrong.

## What is already established — do not re-derive this

Run at 04:40 and again focused; `plugcmd` failed **identically in three separate
runs**, so unlike the other three reds it is not load-flakiness.

The failing check is at `dev/capture/plugcmd.mjs:299`:

```js
ok('POST /command ACCEPTS a plugin kind (a menu entry that 400s is worse '
   + 'than no menu entry)', /sent to the dream/.test(said));
```

`said` is captured like this, a few lines above:

```js
document.getElementById('cmdform').requestSubmit();
await new Promise(r => setTimeout(r, 900));
return document.querySelector('.cmdmsg').textContent;
```

**Measured facts, by the coordinator, on a hand-built fixture server:**

1. `said` comes back as `""` — empty. **Not** `rejected (400)`. So the guard's own
   headline ("a menu entry that 400s") is describing something that is not
   happening.
2. **The command genuinely reaches the loop.** The fixture target's
   `.dreamwork/watch-events.log` contains
   `command via watch [/questions]: gh-sync: a plugin steer 1785179005153`.
   So the POST succeeded. The very next check in the guard — "…and it reaches the
   loop by the same transport as a core command" — would pass.
3. The two checks *before* it pass: the plugin kind gets a button, and its title
   names the plugin.
4. `confirmationFor` in `watch.py` (around line 5595) sets the text, **holds it for
   ~5s**, then adds `.depart` and clears on `transitionend`. So at 900ms the text
   should still be on screen *if it was ever set*. The empty string therefore means
   `show()` had not been called yet — the POST's response had not been handled.

**So the hypothesis to test is: the guard samples at a fixed 900ms, and on the
plugin path the round-trip has not completed by then.** It is a race, not a 400.

## What I want you to find out, in this order

1. **Is the plugin path actually slower than a core kind, and by how much?**
   Measure both. A core `add-idea` submit versus a `gh-sync` submit, wall-clock
   from `requestSubmit()` to `.cmdmsg` becoming non-empty, several samples each.
   This is the question that decides everything below, so do it first and put the
   numbers in your report.
2. **If the plugin path is materially slower** — that is a product finding, and the
   guard is only the messenger. Find out what it spends the time on. Plugin
   resolution on the POST path is the obvious suspect (`plugin_resolver`,
   `.dreamwork/plugin-commands.json`). Report it with numbers; do not go and
   optimise `watch.py` (see ownership).
3. **Either way the instrument is wrong.** A fixed `setTimeout` where the code
   waits on a network round-trip is exactly the class of check this repo keeps
   finding hollow — `CLAUDE.md` and `.dreamwork/lessons.md` both have entries on
   it. Replace it with one that waits for the condition, with a bounded timeout,
   and make the failure message say what it actually saw.

## The verification rules, which are the point

- **A new or changed check is not verification until it has been red.** Break the
  thing it checks, watch it fail, then fix it. Undo the injection from a `cp`
  snapshot, never `git checkout --`.
- **A green red-run is a finding, never a relief.** If you reinstate the bug and
  the check still passes, the check is wrong — do not conclude the code was fine.
  This has happened twice in this repo in one day.
- **Assert the precondition your check depends on.** If your new wait-for-condition
  instrument would pass just as well when the message never appears at all, say so
  and fix it. Name, in your report, the production line that would have to change
  for your check to fail.
- Do not make the guard pass by widening the assertion until it cannot fail. If the
  honest outcome is "the product is too slow and I am leaving the guard red", that
  is an acceptable and valuable result — say so.

## Files you own, and the ones you must not touch

**Yours:** `dev/capture/plugcmd.mjs`.

**Read freely, do not edit:**
- `watch.py` — another agent has uncommitted work in it right now. Editing it would
  collide. If your fix must live in `watch.py`, **stop and report that**; do not do
  it. This is the one hard boundary in this brief.
- `plugin_resolver.py`, `.dreamwork/plugin-commands.json`, `justfile`.

**Never touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`bin/ud-dw-generate`.

## Operational constraints

- **Your guard port is `39897`.** Another agent is working in the same port range
  concurrently. Run guards as:
  `DREAMWORK_GUARDS="plugcmd" DREAMWORK_HUB_GUARDS="" just guards 39897`
  Never run the full sweep, and never use the default port.
- Limit builds/tests to 2 threads.
- `just guards` deletes its temp target on exit, so if you need the fixture's
  `watch-events.log` afterwards, build the fixture yourself: copy
  `dev/capture/fixture` somewhere, run `python3 watch.py --target <copy> --port 39897`,
  then run the guard against it. That is how the facts above were measured.
- The guards import playwright by absolute path — see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.
- Commit your own work, **`git commit --only <paths> -m …`** (`git add <path>` alone does NOT isolate it —
  `git commit` commits the whole index and will bury other agents' staged work — several are live in this tree). Do not push.
- Cap yourself at roughly 20-30 minutes of work. If it grows past that, land a
  coherent point, commit, and report the remainder.

## How to report

Append **once**, at the end, using a single shell append (`cat >> …` or `>>`),
never by rewriting the file, because another agent appends to the same file
concurrently:

`.dreamwork/inbox.md`

Follow the shape of the existing entries there. It must state: the measured
numbers from step 1; what you changed and in which files; **the red-proof — what
you broke, what failed, and the exact check name that failed**; what you did not
do and why; and anything you found that is out of scope (I will file it). If you
have insights or warnings beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so in the report.
