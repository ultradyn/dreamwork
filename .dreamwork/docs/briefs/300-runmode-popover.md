# Brief — #300: one shared popover that explains each run mode on hover

You are a dreamer on the `ud-dreamwork` skill repo. **Read, in this order, before
you design anything:** `CLAUDE.md`, then **`transitions.md`**, then
**`watch-design.md`**.

**Then load these skills** — this repo's CLAUDE.md requires it for Web UI work and
generic frontend defaults do not meet its bar:

- **`web-artisan-core`** — before designing or implementing.
- **`visual-review-and-fix`** — for the review loops, which #300 names explicitly.
- **`headless-browser-screenshots`** — how to get pixels on this machine.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## Why you, specifically

This task needs **vision**. Its acceptance includes interleaved visual review
loops on rendered pixels, and a text-morph that can only be judged by looking at
intermediate frames. You are the multimodal runner; that is why this went to you
and not to the other lane.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  Run mode is *how he steers the loop's pace*, so a control he cannot understand
  without reading source is a hole in the primary goal.
- **Session goal**: the dashboard tells him the truth about the loop's state.
- **This task**: #300, his idea from 14:37, and **he re-raised it as `do-next` at
  06:07 today**: *"run mode button group needs a nice description that shows when
  any of the buttons are hovered. see the original task for a more."* The original
  task is #300 and it is fully specified — the ledger entry is your requirements
  document. `ca12a3c` only *captured* it; nothing is implemented.

## The specification

**`.dreamwork/tasks.md`, entry `#300`.** Read it in full — it is unusually
complete and every clause in it is an acceptance condition. The headline
requirements, restated so you cannot miss them, but **the entry is authoritative**:

- **One shared, geometrically stable surface.** Moving between buttons morphs the
  words in place. It does **not** spawn per-button tooltips — that is the failure
  mode the whole idea exists to avoid.
- **Copy comes from the actual behavioural contract** for each mode (what
  continues, what stops, what commits) — never marketing shorthand that could
  contradict runtime semantics. The contract lives in `.dreamwork/run-mode`'s
  documented meaning: see `file-formats.md` and `SKILL.md`'s Run-mode paragraph.
  **If the copy you write cannot be traced to a documented behaviour, it is
  wrong.**
- **Keyboard focus shows the same description**, with `aria-describedby` exposing
  it. Touch/focus parity must not introduce a surprise second tap.
- **Motion:** first arrival and final departure reuse the existing atmospheric
  blur/drift idiom. Button→button swaps hold the shell fixed while old text
  dissolves and new resolves, through **several causal intermediate opacity/blur
  states** — not a frame-zero replacement. **Reduced-motion swaps text instantly
  with identical meaning and function.**
- **Dismissal** (Escape, pointer-leave, blur) has **no mode side effect**, and
  the popover geometry clamps on desktop and mobile **without obscuring the
  countdown**.

## The hard constraint you must not break

**#290's arming semantics.** Writing a run mode is guarded by a 10-second arm,
with reset/cancel/cross-tab rules and an exactly-once POST. **A hover description
must not touch any of it.** Hovering, focusing, and dismissing are pure
presentation and must produce **zero** writes, zero events in
`.dreamwork/watch-events.log`, and no change to an in-flight arm.

**Prove that, do not assert it.** A check that counts events before and after a
full hover/focus/dismiss sweep and asserts the count is unchanged — with the
count derived at runtime, not a literal — is the single most valuable check in
this task. If hovering can cancel someone's arm, the feature is worse than absent.

## Acceptance criteria — binary, and I will check each one

1. **One surface, proven.** A guard asserts that after hovering all buttons in
   turn there is exactly **one** description element in the DOM, and that its box
   did not jump between buttons (position/size stable within a stated tolerance).
   Derive the button count at runtime; do not hardcode three.
2. **Zero side effects, proven as described above** — event-log line count and
   run-mode file content byte-identical across a full hover/focus/Escape/leave
   sweep. **Assert the precondition** that your sweep actually hovered something
   (e.g. the description became non-empty), or the check passes vacuously when the
   hover never landed. That vacuity has bitten this repo repeatedly.
3. **The morph is real, and this is where checks here go hollow.** `transitions.md`
   opens with how to check motion and why the obvious way does not work: **an
   end-state assertion cannot fail on a motion bug, and neither can "did it
   change".** Sample **per-frame** via `requestAnimationFrame` and assert on the
   collected sequence — at least one frame strictly between the endpoints. Reuse
   the `between(frames, first, last)` idiom already in `dev/capture/dreamfade.mjs`
   and used by the motion guards; **do not author a second sampling idiom**, and
   **do not count distinct values** — that specific mistake was the bug in three
   guards earlier today (#383).
4. **Reduced-motion parity.** Under `prefers-reduced-motion: reduce` the text
   swaps instantly, and a check asserts the meaning and function are *identical* —
   same text for the same button, same `aria-describedby` wiring. Parity means
   equal function, not a degraded variant.
5. **Accessibility is asserted, not claimed:** `aria-describedby` resolves to the
   description's live id, and keyboard focus alone (no pointer) shows the same text
   as hover for the same button. Assert the two strings are equal at runtime.
6. **Copy is traceable.** In your report, map each mode's sentence to the
   documented behaviour it came from. Any sentence you cannot trace, cut.
7. **`just test` exits 0**; your new guard is registered in `DEFAULT_GUARDS` in
   the `justfile` in the same commit that adds it; **`python3 lint.py` exits 0 run
   as its own command** (never in the same shell command as a `git commit`).
8. **`just audit-styleguide` passes** — you are changing how the page looks, so
   `watch-design.md` **and** `transitions.md` (if you add or reuse a motion) are
   updated in the **same commit**. This is enforced, not advisory.
9. **Visual review actually happened, on pixels.** Screenshots of: each mode
   hovered, a button→button swap mid-morph, the reduced-motion state, and the
   narrow viewport with the countdown visible. Say what you found and fixed. Two
   self-inflicted visual defects were found in this repo today *only* by looking at
   rendered output — a label overflowing into invisibility and an amber sliver
   reading as a grey block. Both passed every structural check.

## The rules that matter most here

**A green red-run is a finding, never a relief.** For every check: break the thing
it checks, watch it fail **by name**, then restore from a `cp` snapshot — **never**
`git checkout --`. If the check still passes with the bug in place, the check is
wrong; report it, and do not conclude the code was fine. Twice today in this repo a
red-run came back green while the bug was in place, both times because the test's
scaffolding stood in front of the code.

**Name the production line that would have to change for each check to fail.** If
you cannot name one, there isn't one. This is required in your report, per check.

**Do not widen a tolerance to get green.** If the honest outcome is "the morph
works and my check for it is not trustworthy", say that. One genuinely verified
behaviour beats four toothless checks.

## Files

**Yours:** `watch.py` (**you are its sole holder** — confirmed free at 06:10, the
previous holder merged and stood down; another watch.py task is queued **behind**
you, so commit and report promptly), `test_watch.py`, `justfile` (only to register
your guard), `watch-design.md`, `transitions.md` (only if you add or extend a
motion idiom), and **one new guard** under `dev/capture/`.

**Read, do not edit:** `file-formats.md`, `SKILL.md`,
`dev/capture/dreamfade.mjs` and the other motion guards (reference idioms —
read them, do not change them).

**Never touch:** `user_events/` and `test_user_events_*.py` (**two lanes are live
in there right now**), `dev/capture/gitrow.mjs` (another lane owns it),
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

## Operational constraints

- **Your guard port is `39891`.** Run guards as
  `DREAMWORK_GUARDS="<name>" DREAMWORK_HUB_GUARDS="" just guards 39891`.
  **Never** the full sweep, never the default port — other lanes use that range.
- The guards import playwright by **absolute path**; see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.
- Limit builds/tests to **2 threads**. Other lanes are live on this box, and load
  has been 40–125 on 16 cores today.
- **Load will make your motion checks fail spuriously, and the asymmetry is
  useful:** a dropped intermediate frame causes false **reds**, never false greens.
  So a green under load is conclusive; a red under load needs a re-run before you
  believe it. Do not "fix" a load-induced red by loosening the check.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after
  `git add` commits the whole index, not the paths you named, and will bury a
  concurrent lane's staged work — that happened in this tree an hour ago. **Do not
  push.**
- **This is bigger than one increment. Commit in stages** — copy + static surface
  first, then motion, then a11y/reduced-motion, then the visual-review fixes. Each
  stage committable and verifiable alone. Cap yourself at roughly **60 minutes**;
  if you run out, land the coherent stages and report what remains. A static
  correct description with traceable copy and zero side effects is already a real
  improvement over nothing.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the reds verbatim
— what you broke, the exact check name that failed**; the production line named
per check; the copy-to-contract mapping from criterion 6; what the visual review
found and what you changed because of it; commit shas; what you did not reach and
why; and what you are not confident about. An honest "not confident about X, and
here is what would settle it" is worth more than a confident guess, and this repo
has paid for the latter repeatedly.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
