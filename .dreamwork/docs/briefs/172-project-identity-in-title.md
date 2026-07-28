# Brief — #172: the project name is not in the title, and the ledger says it is

Repo: `ud-dreamwork`. Worktree: **`.worktrees/172`**, branch **`wt/172`**. Do not push, do not merge.
**Never use `attn`** — report through the inbox path at the bottom.

**This is urgent and he is right to be annoyed.** His words at 15:13, verbatim:

> *"we have several tasks about putting hte project name in the title line. This has been delayed
> too long. it's essential and basic. Dispatch a subagent to solve this problem ASAP. (I thought we
> already did last night but it is still unimplemented)"*

He is correct on both counts, measured before writing this: `#172` sits in the ledger's
`## Recently landed` section **with no closing marker at all**, and the served page contains the
string `ud-dreamwork` **nowhere**. The tab title is the literal `dreamwork watch`. So a P1 he asked
for was filed as done without being done. Read that as the reason for the tone, not as pressure to
cut corners — the fix for "it was claimed and not built" is not a faster claim.

## What is true right now, measured at 15:15

- The visible title is `<h1 class="htitle" id="htitle">` (`watch.py:1618`), **populated by JS** and
  currently carrying only the route word — empty string on the dashboard route.
- The tab title comes from `TITLE_ROUTE` (`watch.py:3646`) composed with `titleNeed` and the
  liveness word. **No project identity in either.**
- **`/data.json` already carries `target`** — the absolute path of the project
  (`/home/xertrov/.llm-general/skills/ud-dreamwork` here) — plus `tint`. **So the data is already
  in the client and nothing needs plumbing.** This really is a display change, which is why he
  calls it basic.
- **The idiom already exists in this same file and is the model to follow.** `popoutShell`
  (`watch.py:~5931`) gives every popped-out window `titleWord + ' · ' + base + ' · dreamwork'` and
  a hue-tinted band with *"the project basename + full path"*. **The popouts have project identity
  and the main window does not.** Reuse that vocabulary rather than inventing a second one.

## His design constraint, in his own words, and it is the interesting part

From `#172`: show the project name *"in a materially more prominent position within the visible
title section"*, and:

> **"anchor what is invariant to an edge, not to a variable-width neighbour"** — the route title
> varies while repo identity does not, so the identity must not be shoved about by unrelated route
> changes.

So the identity is pinned to an edge of the title bar and **does not move when the route word
changes length**. A layout where identity sits beside the route and slides as `questions` becomes
`review 367-option-previews.html` fails this even if it looks fine on one route. **Check it by
navigating between routes and measuring the identity's box, not by looking at one screenshot.**

One caution already recorded in `watch.py:6143`: **two checkouts can share a basename**, so
basename alone is ambiguous. The popout band's answer is basename *plus* full path. Decide what the
main title does about that and say why — the full path in an `h1` is almost certainly wrong, a
`title=`/tooltip or the existing meta line is likely right.

## Done means all of these

1. **The project name is visible in the title section on every route**, prominent, and pinned so a
   route change does not move it. Prove the pinning: capture the identity element's
   `getBoundingClientRect()` on at least three routes (`/`, `/questions`, a `/review?p=…` with a
   long param) and assert the box is **identical**, not merely present.
2. **The browser tab title contains the project name too**, composed with what is already there —
   `titleNeed`'s count, the route, and the liveness word. Do not drop or reorder those; `#136`'s
   `!` and the `stalled`/`dreaming` word are load-bearing and their reasoning is in the long
   comment above `TITLE_ROUTE`. Read it before you touch that function.
3. **Desktop and mobile captures**, deterministic, plus **your own visual verdict** — you were
   chosen partly because you can see. Does it read as identity, or as a breadcrumb? Is it prominent
   at his actual reading size, or merely present?
4. **A registered guard** in `dev/capture/` (added to `DEFAULT_GUARDS` in the `justfile`), red-first:
   write it, watch it FAIL against current `master` behaviour, then make it pass. **Include the
   route-invariance assertion from criterion 1** — that is the one that encodes his rule rather
   than the surface fact.
5. **`watch-design.md` updated in the same commit as the code** — `#172` asks for the rule
   documented, and `just audit-styleguide` measures whether that happened.
6. **`transitions.md` applies.** If the identity or the route word changes on navigation, that is a
   transition and it obeys the file. There is no size floor on this rule here. The route change is
   the reference implementation — reuse the existing idiom, do not author a second.
7. `python3 lint.py` clean, and **`just test`**. Do **not** pipe it — a pipeline returns the last
   command's status; write to a file, read the file, quote the tail and the real exit code. The
   suite was **fully green at 14:50** (51 guards, 0 failures), so **any** failure is yours and is
   worth your attention. There are no excused reds today.
8. **A red-proof of the guard, from a `cp` snapshot**: remove the identity from the title and watch
   your guard fail on the named assertion. **A green red-run is a finding, not a relief** — if the
   guard still passes with the identity gone, say so; the guard is wrong and that is the more
   valuable result.

## Files

Yours: `watch.py`, `watch-design.md`, `dev/capture/<your-guard>.mjs`, `justfile` (the
`DEFAULT_GUARDS` line only), and a `test_watch.py` addition if the title composition deserves a
unit test — it probably does, since it is a pure string function.

**Not yours:** `status_sync.py` and `test_status_sync.py` — another lane holds those right now.
Do not touch `.dreamwork/tasks.md` or `.dreamwork/questions.md`; the coordinator is their only
writer and is fixing `#172`'s ledger placement itself.

`#172` also says *"read his references first: `grok-build`, `codename-thin` at
`ssh://x-game:src/codename-thin`, on another machine"*. **Treat that as optional** — it is on a host
you may not reach. If you cannot, say so and proceed; do not block on it.

## Practical

- Guards bind ports **39890-39899**. Another lane may be running `just test`; **check who owns them
  before you run** (`ss -ltnp | grep 3989`) and say so if you had to wait. Two servers in one range
  is a mistake this repo has already paid for.
- 2 threads.
- Commit with `git commit --only <paths> -m 'feat(#172): …'`. **`--only`, never `git add -A`** — two
  other agents commit in this tree and a bare `git commit` sweeps up their staged work under your
  message. A **new** file needs `git add <file>` first.
- **Push back with reasons if any of this is wrong.** Seven lanes today have refuted something their
  brief asserted, and every one was right to. If my reading of the layout constraint is wrong, say
  so before building to it.
- Then append one line to `.dreamwork/handoffs.md` **inside your worktree** and commit it there:
  `- **#172** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`.
  Do **not** write the hand-off to the main checkout's copy — that lands the same line in two places
  and blocks the merge.

## Report

Append once, at the end, to the **absolute** path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`.

Say: the real `just test` exit code and how you got it; the guard's name and its red-proof with the
exact failing assertion; the three route rectangles proving the identity does not move; whether you
could reach his reference repos; and **your own visual verdict on whether it reads as prominent
identity** at normal reading size.
