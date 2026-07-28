# Brief — #429: the `#263` artifact's ask is below the fold on mobile

Repo: `ud-dreamwork`. Worktree: **`.worktrees/fold`**, branch **`wt/fold`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

## The defect, measured

`.dreamwork/review/263-second-gate.html` is **live on the human's desk right now** — it is the artifact
attached to the open `#263` question asking him to open the second gate. Its content is correct. Its
decision block is not reachable on a phone:

```
  ok   desktop  1280x900 innerHeight=900 scrollHeight=7193  | #ask.top=594  h=870  above
  FAIL mobile   390x844  innerHeight=844 scrollHeight=11713 | #ask.top=1006 h=1354 BELOW
```

On mobile he scrolls **a full screen and a fifth of another** past the title block before the decision
begins. **The cause is one measured fact:** the `<header>`'s `.hero-grid` is two columns on desktop
(487px) and **stacks to two rows on mobile (899px)**. 899 > 844, so while the ask sits after the header
it **cannot** start above the fold on mobile at any content length. This is arithmetic, not taste.

## The fix already exists in the corpus, so copy it rather than inventing one

`.dreamwork/review/421-question-options.html` passes both viewports — `#ask.top` **218** desktop and
**266** mobile — and it does so with a **similar hero height (484/873)**. It passes because it puts the
ask **inside the hero**, near its top, instead of after it. **Read that file and follow its structure.**
That pattern is the deliverable; a novel solution is not wanted here and would be a second idiom for one
job.

Do not simply delete content to win the measurement. The material currently in the hero's second cell
(badges, task meta, date) belongs on the page — move it **below** the ask, not out of existence.

## Acceptance is one command and you cannot satisfy it by writing your own check

```
node dev/capture/above_fold.mjs .dreamwork/review/263-second-gate.html
```

It must **exit 0** and print `ok` for both viewports. Quote its full output in your report.

That script landed at `1dd973f` and is now the only check briefs cite. **Do not write your own
above-fold measurement** — the reason it exists is that the coordinator's ad-hoc one used
`newPage({viewportSize:…})`, which Playwright swallows silently, so both "viewports" were the default
1280×720 and one page was measured twice under two labels. It has three red-proved preconditions
(viewport actually applied, page actually scrolls, element actually present). If you think it measures
the wrong thing, **say so in your report with your reasoning** — do not route around it.

## Done means all of these

1. **`above_fold.mjs` exits 0** on the built artifact, `ok` at both viewports. Output quoted verbatim.
2. **`python3 review_artifact.py build .dreamwork/review/src/263-second-gate.html`** regenerates the
   built file and **`python3 review_artifact.py check`** reports **`current`** for it. Quote that too.
   Edit the **`src/`** file; the built file is generated. Do not rename either path — the questions
   entry links them.
3. **No content lost.** Diff your own change and confirm every badge, figure and sentence that was in
   the hero still exists somewhere on the page. State what moved and to where.
4. **The content claims are unchanged and still true**: lane status `A 2/2 · B 8/8 · C 5/5 · D 4/4 ·
   F 4/4`, `C4` `f85be1c`, `C5` `2cc3537`, Q1/Q2/Q3 live, and the **16:24 correction stays visible
   below the ask** — it is demoted, never deleted, because the record of having got it wrong is why the
   current claim is trustworthy. **Grep your built output for `3/5` and report each hit with its
   surrounding sentence**: there should be exactly the hits that sit inside that correction, and a bare
   count is not an answer because a substring cannot tell an assertion from its retraction.
5. **`transitions.md` applies with no size floor.** If moving the ask changes anything that appears,
   disappears, expands or collapses, read that file first and reuse the existing idiom. State whether
   you introduced any gesture and whether reduced-motion parity is inherited or authored.
6. **Offline-clean** — grep the built file for `http://` / `https://` outside link text, report the
   count (it is 0 now; keep it 0).
7. `python3 lint.py` clean. **Do NOT run `just test`** — guards bind 39890–39899 and another lane is
   live; the coordinator runs the suite at merge (`#424`). Do not bind any port in 39880–39899.
8. **The visual verdict is owed, not yours** — you are `@glm52` and cannot see. Say *"visual verdict
   owed"* and do not characterise how anything looks beyond the numbers you measured.

## Files

Yours to commit: `.dreamwork/review/src/263-second-gate.html` and
`.dreamwork/review/263-second-gate.html`. **Nothing else** — `git status --porcelain` proves it.

**Not yours:** `review-artifact.template.html` (a template change touches all 22 artifacts and is a
separate call — if you conclude the fix *belongs* in the template, say so and stop rather than doing
it), `.dreamwork/review/*417*` (a live lane holds those), `watch.py`, `lint.py`, `dev/capture/*`, and
`.dreamwork/tasks.md` / `questions.md` (coordinator is the only writer — report exact lines instead).

## Practical

- 2 threads. `git commit --only <paths> -m 'fix(#429): …'` — **`--only`, never `git add -A`**: another
  agent commits in this tree and a bare `git commit` sweeps its staged work into your commit.
- **Commit before you finish.** The immediately preceding lane on this same file did the work, ran 24
  turns and **exited without committing**; `git log` showed nothing and the edits were recovered from
  the dirty worktree by hand. Your work does not exist until it is a commit.
- **Push back with reasons if any of this is wrong.** Many lanes today have refuted something their
  brief asserted and every one was right to.

## Report

Say: `above_fold.mjs` output verbatim; `review_artifact.py check` output verbatim; what moved and to
where; your `3/5` hits with surrounding sentences; your offline-clean count; whether you introduced any
transition; and confirmation that `git status --porcelain` shows only your two paths.
