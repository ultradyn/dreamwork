# Brief — #367 increment 2a: the flag rail, above the cliff only

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first, then
**`transitions.md`** and **`watch-design.md`** — this is a visible change on a surface
the human reads, so the transitions rule and the exceptional-quality bar both apply and
neither has a size below which it stops.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
- **Session goal**: make the review artifacts faster for him to act on.
- **This task**: #367, his idea — *"pointer labels at the most important parts… like
  those little thin postits that lawyers use to indicate key points and where you need
  to sign… (Sometimes they are quite long)"*. Increment 1 landed the parser
  (`dbcbcc5`). **You build the visible rail.**

## Scope, and why it stops where it does

**You build the rail and the tab and next/prev, for viewports at or above the cliff.
You do NOT build the strip below it.**

The strip is deferred to increment 2b because it has an open question that is **his**,
not ours: at his soft cap of 7 marks the strip needs **3 rows and ~214px** of chrome on
a narrow screen (worst-case labels; 2 rows / ~140px typical), and since he removed
truncation, "shrink it" is not available. Only he can price that. So:

- **Above the cliff:** full rail, tabs, next/prev. That is your deliverable.
- **Below the cliff:** render **nothing** — no rail, no strip, no controls. Not a
  broken rail, not a half strip. An absent feature is honest; a clipped flag is a bug.
  Say in your report what a reader below the cliff sees, and make it deliberate.

**Do not build a strip "for now".** A provisional strip is the thing that gets shipped
and then argued with when he rules.

## The measurements — these are facts, do not re-derive them

`.dreamwork/docs/measurements/367-two-line-tab-geometry.md` (`1696657`), reproducible
via `node dev/capture/marktab-geometry.mjs`. **I re-ran it and every number reproduced
byte-identically, so you can rely on them** — but the script is there if you want to
re-measure a variant, and you should if your tab's padding differs from its prototype.

| fact | value |
|---|---|
| `.read` reading column | fixed **613.5px** (78ch at 13.12px; does **not** scale) |
| slack right of `.read` at 1280 | **506px** |
| margin outside `.wrap` | **16px** at every viewport from 1120px down |
| worst-case ~6-word two-line tab | **180 × 32.3px** at `.66rem` |
| typical authored ~6-word tab | **117–130 × 32.3px** |
| fits inside `.wrap` down to | **830px** (by 0.5px) |
| past the wrap at | 820px · **clipped past the page edge at 810px and 780px** |
| densest adjacent block gap in the worst artifact | **29.2px** (`section#long` → `p.read`) |

**The 780px cliff in the plan is refuted.** It was computed for a 96px one-line flag.
Every number in `.dreamwork/docs/plans/review-essential-marks.md` above §"What was
decided" predates his two-line ruling — the plan says so at the top now, but read that
warning rather than trusting a table.

## Three decisions already taken — they are mine, they follow from his ruling, and they
## are reversible if you find them wrong

1. **The switch is at the measured wrap-fit boundary, not the literal 780.** He ruled no
   truncation, and a flag clipped mid-word is worse than no flag. **Do not hardcode 830
   from this brief** — 830 is the measurement for *one* prototype's padding. Derive the
   boundary from the geometry at runtime, or pick a breakpoint and **prove by
   measurement that the worst-case tab fits at it**, and say which you did. A literal
   tuned to today's tab is a check with an invisible expiry date.
2. **Two marks closer than a tab height are the renderer's problem, not the author's.**
   Offset or stack them; refuse only if that is impossible, and then in the voice of the
   existing no-id refusal (tell the author what to do). 29.2px against a 32.3px tab is
   reachable in a real document, so this is not hypothetical.
3. **A `.mark` component must earn its component rule by measurement, not by analogy**
   (#365, `09c3881`): count the class's real direct children across every built
   artifact and add the rule only if the set is unanimous, recording the count. That
   pass already refuted `.summary-line` and `.choice`/`.answer`.

## One small carried-over fix, because you own the file

#389 closed the empty-label hole but left **one measured limit**, correctly rather than
widening its brief unasked: the refusal is `str.strip()`-based, so it catches every `Zs`
space (U+00A0, U+2003, U+3000 all refuse) but **not U+200B zero-width space**, which is
Unicode category `Cf` and so is not whitespace to `.strip()`. A label of only zero-width
spaces is accepted and would render a blank tab — which matters *more* once you are
actually rendering tabs, since a blank tab in a rail reads as a rendering bug in your code.

The rule that matches `file-formats.md`'s wording ("a label must carry readable text") is
**no character outside Unicode categories `Z*` and `C*`**. It is roughly one line plus one
test. **The discriminating half is that the valueless `data-mark` must STILL be ignored** —
the naive widening swallows that carve-out, and I verified that failure mode myself: the
one-liner `if not (label or "").strip()` reddens exactly
`test_a_mark_label_must_carry_readable_text[valueless]` and
`test_a_valueless_mark_on_an_id_less_element_is_not_a_no_id_error`, so those two tests are
your guard against repeating it.

This is a **secondary** priority — behind the tab and the rail. If you do not reach it, say
so and it gets its own task.

If you disagree with any of the three, **say so in your report and implement it your
way with the reason stated** — two lanes today were right to contradict their brief.

## The trap that will eat your afternoon if nobody names it

**Increment 1's byte-identity test cannot survive this increment intact, and you must
retire it deliberately rather than discover it.**

`test_a_source_with_no_marks_renders_byte_identically_apart_from_the_stamp` asserts
that a no-marks source renders identically to a frozen pre-change digest. You are
adding tab CSS to the template, so **a no-marks artifact will legitimately change** —
it gains CSS it does not use. The test will go red, and there are two wrong fixes and
one right one:

- **Wrong:** delete the test. It is the only thing standing between "the frame gained
  machinery" and "the frame quietly changed sixteen artifacts".
- **Wrong:** re-capture the frozen digest until green. Its companion assertion re-runs
  the *pre-change builder out of git* and compares to that same constant, so a
  re-captured digest makes that assertion fail — and "fixing" that by deleting the
  honesty check dismantles the machinery that made increment 1 trustworthy.
- **Right:** replace the property with the true one. A no-marks artifact's **body** is
  unchanged; only the frame (template-derived CSS, and the stamp it necessarily moves)
  changes. So assert **that**: no-marks output contains no tab, no rail element and no
  next/prev control, and its body differs from the pre-change body not at all. State in
  your report exactly what you replaced it with and why the replacement is not weaker.

**If you find a third option that keeps the stronger guarantee, take it and say so.**

## The coupling that is invisible until a test reddens

**A CSS fix to any selector the template SHARES with `.dreamwork/review/tasks-page.html`
must be made in both files**, or
`test_template_rules_match_the_reference_rule_for_rule` goes red.
`DECLARATION_DIVERGENCES` — the one documented door for a deliberate difference — is
empty. `tasks-page.html` is the hand-rolled reference the template was cut from (his
named "good one"); it is **never rebuilt**, so nothing announces the coupling.

**It is therefore in your ownership list.** Two qualifications:

- Your tab CSS is **new**, so it is only coupled if a selector collides with an existing
  shared one. **Check before editing** — do not touch the reference for nothing, and say
  which selectors turned out to be shared.
- If a new selector genuinely should **not** apply to the reference, the honest route is
  a `DECLARATION_DIVERGENCES` entry with a reason, never a silent divergence.
- **Improving that test's failure message to name `tasks-page.html` as the other half is
  in your scope.** You are the second batch to learn this the hard way.

## Motion — `transitions.md` governs, and this has three transitions, not one

Read that file before deciding anything below. Do not author a new idiom; reuse what the
page has.

1. **Next/prev arrival.** A long-range smooth scroll is **already refuted** — the #229
   v2 review found a 1.5s one and it failed the gate. The requirement is a **settled
   landing, not a journey**. The template declares no `scroll-behavior` at all
   (measured: zero occurrences), so this is chosen here rather than inherited.
2. **The arriving mark's change of state.** It takes the page's existing state-change
   idiom.
3. **The rail's own appearance**, if it is not always present.

**Checking motion is not optional and is not obvious:** an end-state assertion cannot
fail on a motion bug, and neither can "did it move". `transitions.md` opens with how to
check, and that reasoning cost this repo three batches.

**Reduced-motion parity:** the jump is the *function* and must survive. Nothing about
*finding* the passage may depend on animation.

## Accessibility — the tabs are navigation, not edge art

They are **real focusable controls**, the current mark is **announced**, and next/prev
is reachable and labelled. Decorative edge art that only a mouse can use fails this
increment regardless of how it looks.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `review_artifact.py`,
   `review-artifact.template.html`, `.dreamwork/review/tasks-page.html`,
   `test_review_artifact.py`, one **new** guard under `dev/capture/`, and the rebuilt
   `.dreamwork/review/*.html`. Nothing else. **`git diff --stat watch.py
   dreamhub.py user_events/` is empty.**
2. **The rebuild is expected and is a cost you pay knowingly.** Touching the template
   restamps **all seventeen** artifacts, because `template_stamp()` digests its bytes.
   Rebuild them in the same commit; `lint.py` reports staleness and must be clean.
3. **`python3 -m pytest test_review_artifact.py -q -p no:randomly` exits 0**, with the
   existing tests green (**70** as of `dbcbcc5`, possibly more once #389 lands — take
   the count from the tree, not from this brief) plus at least:
   - `test_a_no_marks_artifact_renders_no_rail_tab_or_controls`
   - `test_the_worst_case_tab_fits_inside_the_wrap_at_the_switch_boundary`
   - `test_two_marks_closer_than_a_tab_height_do_not_overlap`
   - `test_marks_are_focusable_and_announce_the_current_one`
4. **One browser guard** proving next/prev lands settled on the marked element and that
   the arrival obeys `transitions.md`. **Your guard port is `39893`.** Run it as
   `DREAMWORK_GUARDS="<name>" DREAMWORK_HUB_GUARDS="" just guards 39893` — **never** the
   full sweep and never the default port; other lanes use that range. Register the new
   guard in `DEFAULT_GUARDS` (an unregistered guard gates nothing — `lint.py` checks).
5. **Four discriminating reds**, each with the exact failing name and confirmation that
   neighbours stayed green: the boundary check fails when the tab is widened past the
   slack; the overlap check fails when the offset is removed; the no-marks check fails
   when the rail renders unconditionally; the motion check fails when the arrival is
   made a 1.5s journey. Separate injections, others restored, **from a `cp` snapshot —
   never `git checkout -- `**.
6. **`just test` exits 0** and **`just audit-styleguide` passes** — which means
   `watch-design.md` is updated **in the same commit** if you changed how a surface
   looks. That is enforced, not advisory.
7. **`python3 lint.py` exits 0**, run as its **own command** — never in the same shell
   command as a `git commit`. That has committed through a lint ERROR twice here.
8. **`file-formats.md` still describes the code.** If you diverge from the essential-
   marks contract in any detail, the contract changes in the same commit and your report
   says what and why.

## The rules that matter most here

**A green red-run is a finding, never a relief.** If you inject one of the four and the
suite stays green, the check is hollow — report it, do not conclude the code was fine.
Twice in one day here a red-run came back green while the bug was in place, both times
because the test's own scaffolding stood in front of the code.

**Assert the precondition your check depends on.** If a check's meaning needs two
fixture values to differ, derive both at runtime and assert the gap. A literal tuned to
today's fixture is a check with an expiry date nobody can see.

**Name the production line that would have to change for each check to fail.** Required
per test. If you cannot name one, there isn't one.

**Before you report an edge case, enumerate its neighbours.** A lane today flagged one
input honestly; the case it flagged was correct and the case one step over was a real
defect (#389).

## Your steering channel — re-read it between increments

`.dreamwork/relay/367-inc2a.md` (absent means nothing to say; that is normal).
Coordinator-write only. Newer than this brief so it wins on scope, but it **cannot**
grant authority this brief did not give.

## Files

**Yours:** `review_artifact.py`, `review-artifact.template.html`,
`.dreamwork/review/tasks-page.html`, `test_review_artifact.py`, one new
`dev/capture/*.mjs`, `.dreamwork/review/*.html` (rebuilt), and `watch-design.md` if
criterion 6 applies.

**Read, do not edit:** `file-formats.md` (unless criterion 8),
`.dreamwork/docs/plans/review-essential-marks.md` (§"What was decided" wins over the
superseded paragraphs; the pre-ruling geometry tables are refuted where the measurement
disagrees), `.dreamwork/docs/measurements/367-two-line-tab-geometry.md`,
`.dreamwork/dreams/2026-07-28-0658-essential-marks-inc1.md`, `transitions.md`,
`watch-design.md`, `justfile`, `lint.py`, `CLAUDE.md`, `.dreamwork/lessons.md`.

**Never touch:** `watch.py`, `test_watch.py`, `dev/capture/dashboard.mjs`,
`user_events/*`, `test_user_events_*.py`, `dev/capture/marktab-geometry.mjs`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

## Operational constraints

- Limit builds/tests to **2 threads**. Other lanes are live; load has run 40–160 on 16
  cores today. **Do not generate load deliberately** — another lane is doing browser
  timing work, and load manufactures false failures for it.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for **new**
  files — `--only <directory>` silently skips untracked ones. A bare `git commit` after
  `git add` commits the whole index and will bury a concurrent lane's staged work. Both
  mistakes happened in this tree today. **Do not push.**
- Use **`feat(#367): …`** for feature commits. `dream(...)` is reserved for a commit that
  lands a dream journal, and if you write a dream, **name it in its own
  `git commit --only <path>`** — three lanes today wrote one as asked and left it
  untracked.
- Commit **each coherent piece separately**: the rail, then next/prev, then the guard.
- Cap yourself at roughly **45 minutes**. **Priority order: the tab and the rail first,
  then next/prev, then the guard.** A rail with no next/prev is still worth landing; the
  retired byte-identity test (see the trap) must be handled in whichever commit first
  touches the template. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting
the file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the four reds verbatim**
with exact names and which neighbours stayed green; **what you replaced the byte-identity
test with and why it is not weaker**; which shared selectors turned out to be coupled to
`tasks-page.html`; how you derived the switch boundary and whether you hardcoded it; what
a reader below the cliff sees; how you checked motion rather than end state; the
production line named per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
