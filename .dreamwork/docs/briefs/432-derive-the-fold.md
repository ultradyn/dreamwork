# Brief — #432 (fold half): derive the fold from the live route, because three separate inputs move it

Repo: `ud-dreamwork`. Worktree: **`.worktrees/fold`**, branch **`wt/fold`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

This is the *fold* half of `#432` only. The `#ask`-as-a-contract retrofit is `#436` and is **not yours**.

## The problem, and it is already proven rather than suspected

`dev/capture/above_fold.mjs` decides whether a decision he must rule on is visible. He reads artifacts
inside an iframe on the dashboard's `/review` route, so the visible height is **not** `innerHeight` — and
the checker compares against two hard-coded constants:

```js
{ label: 'desktop', width: 1280, height: 900, fold: 738 },
{ label: 'mobile',  width: 390,  height: 844, fold: 670 },
```

**That mobile number was wrong three times today, always in the same direction — optimistic, calling
clipped content visible.** The history is the argument for this task:

| value | why it was wrong |
|---|---|
| **706** | the **top** of a measured 693..708 range; a fold must take the floor |
| **691** | the floor measured **inside a worktree** |
| **670** | the floor on the real target — correct today, and still a dated constant |

Three separate inputs move it, and none of them is the viewport:

1. **The artifact's filename length.** `SPAN.revname` wraps the title bar once the name is long enough;
   the chrome grows and the frame shrinks. The iframe's *bottom* is pinned (828 at 390x844); its top is not.
2. **The target directory's basename**, because that is the project name in `#hproj` and it shares the
   title bar line. `.worktrees/frame` renders `frame` (5 chars, floor 693); the real repo renders
   `ud-dreamwork` (12 chars, floor 672). **A fold verified in a worktree is not verified for his surface.**
3. **How the name breaks.** A padded `xxxx…` run of the right character count has no hyphen to break on
   where real names do, so it wraps further. A derived *length* is not a derived *layout*.

So the constant cannot be right for all inputs, and nothing notices when it stops being right.

## What to build

**`above_fold.mjs` measures the fold itself, on the live route, for the artifact under test.** Concretely:
start a `watch.py` on an ephemeral port with `--target` the real repo, load `/review?p=<the artifact>`,
measure `#reviewframe`'s height, and use that as the fold for that artifact at that viewport. Then the
number is derived per artifact from the surface it will actually be read on, and all three dependencies
above stop mattering because none of them is being modelled any more — they are being measured.

Design decisions are yours, but state your reasoning for each:

- **Keep it usable on a bare file.** The tool takes `<file-or-url>` today and lanes call it that way. If
  you cannot derive a fold (no server, artifact not in `.dreamwork/review/`), say what you do — a stated,
  conservative fallback is acceptable; a *silent* fallback to a constant is not, because that is exactly
  today's failure with a new hiding place. Print which mode each viewport line used.
- **Cost matters a little.** Spawning a server per invocation adds seconds and lanes call this repeatedly.
  If you cache or reuse, say how, and make sure a stale cache cannot outlive a chrome change.
- **`#reviewframe` strictly.** Do **not** fall back to `querySelector('iframe')` — my own first probe did
  and it silently measures a different box. Wait for the real element and fail loudly if absent.

## Done means all of these

1. **The fold is measured, not declared**, for both viewports, and the tool prints the derived number and
   how it was obtained on every run.
2. **It reproduces the three known measurements** — run against the real target and show: the shortest-named
   artifact gives ~708 at 390x844, the longest-named gives ~672, and desktop gives ~740. Those are my
   numbers; if yours differ, **say so with your measurement rather than adjusting to match mine** — I may
   be the one who is wrong, and one of the four wrong numbers today was mine.
3. **`263-second-gate`, `421-question-options` and `417-burndown-commits` still pass** (their asks sit at
   `top=266`, `266`, `315`, so they have room), and the printed fold for each is the derived one.
4. **The `devoverlay.mjs` fold guard is updated or retired with a reason.** It exists to hold the
   *constant* honest by re-measuring the real corpus; if the constant is gone, that check's job changes.
   Do not simply delete it — either repoint it at the derivation (e.g. that the derived fold equals an
   independent measurement) or state why it no longer earns its runtime. **Its anti-vacuity assertion —
   that the shortest and longest names give different heights — is the part worth keeping in some form.**
5. **Red-first, and name the production line.** Break the derivation (e.g. make it report `innerHeight`)
   and show an artifact that should fail now failing. **A green red-run is a finding, never a relief** — if
   it stays green your check is wrong, and that is the more valuable result. If you cannot name a line
   whose change fails it, there isn't one.
6. **Every viewport probe asserts the viewport was applied** — `innerWidth === requested` **and**
   `innerHeight === requested`. Both: chromium's default is 1280x720 and desktop asks for 1280x900, so on
   a wrong `newPage({viewportSize:…})` (the key is `viewport`; the wrong one is swallowed in silence) **the
   width matches anyway** and only the height reveals it. The file already has this idiom — keep it.
7. **`python3 lint.py` clean** and **`python3 -m pytest -q -p no:randomly` passes.** You may run
   `DREAMWORK_GUARDS=devoverlay DREAMWORK_HUB_GUARDS= just guards 39897` for your own guard. **Do not run
   the full `just test`.**
8. **Do not restart, `pkill` or redeploy the live dashboard on :35110.** Start your own server on an
   ephemeral port outside 39880–39899 and stop it. Note `just deploy`'s `pkill -f` matches any process
   whose command line merely *mentions* the snapshot (`#431`) — and today the same self-match bit twice
   more, once from a **comment** that contained the pattern. Build process patterns from parts.
9. **`transitions.md` binds with no size floor** — read it if anything you touch appears, disappears,
   grows, moves or changes state, and state whether you introduced a gesture. Most likely you introduce
   none; say so rather than leaving it unaddressed.

## Files

Yours: `dev/capture/above_fold.mjs`, `dev/capture/devoverlay.mjs`, and any new file under `dev/capture/`
plus its `justfile` `DEFAULT_GUARDS` entry (a `.mjs` in that directory registered in neither
`DEFAULT_GUARDS` nor `lint.NOT_GUARDS` gates nothing, and `lint` will say so).

**Not yours:** `watch.py` and `test_watch.py` (**a live lane holds both**), `review-artifact.template.html`,
`.dreamwork/review/*`, `lint.py`, `dev/deploy_state.py`, and `.dreamwork/tasks.md` / `questions.md` — the
coordinator is their only writer, so report exact lines instead of editing them.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'fix(#432): …'` — **`--only`, never
  `git add -A`**: another agent commits in this tree and a bare `git commit` sweeps its staged work into
  yours. `--only <directory>` silently skips untracked files inside it.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without committing.
- **Push back with reasons if any of this is wrong.** Every lane today that refuted something its brief
  asserted was right to: one proved my acceptance criterion was blind to the bug it targeted, one proved
  a premise about lint warnings false, one improved on a brief by reordering a guard before a `pkill`.
  If per-artifact derivation is the wrong shape — say, if the fold should be derived once per *viewport
  and project name* rather than per artifact — argue it with the measurement.

## Report

Say: the shape you chose and why; the derived folds with the three reproduction numbers; what happens when
derivation is impossible and how a run says so; what became of the `devoverlay` fold guard; the exact
production line whose change fails your red-first; any transition introduced; and confirmation you neither
ran the full `just test` nor touched :35110.
