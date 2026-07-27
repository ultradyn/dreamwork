# Brief — #396: an inline `data-mark` clips past the page edge (P1)

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it — review
  artifacts are how he rules on designs, and a clipped flag is a broken one.
- **Session goal**: the surfaces he reads tell the truth.
- **This task**: `#396`, **P1**, a live geometry break on `#367` increment 2a, which landed
  forty minutes ago. Read `#367`'s ledger entry and `#396`'s for the full record.

## The defect, measured — inherit these numbers, do not re-derive them

`#367` increment 2a put a flag at the height of each essential passage, anchored to the
reading column's right edge. It anchors via `left:calc(var(--measure) + .4ch)` on an outer
`.marktab` that inherits the **body** font, so `78ch` resolves in the reading column's
metric. That mechanism is correct and subtle and **you must not break it.**

**But `file-formats.md:1118` says `data-mark` goes "on any element inside `body`."** For an
**inline** element the containing block is the inline box, so `left` resolves from *that
box's* horizontal offset instead of the column edge.

I built a probe artifact with two marks on one line and measured the worst flag's right edge
against the viewport:

| viewport | flag right | verdict |
|---|---|---|
| 1280px | 1076 | fits, 204px spare |
| 1000px | 1012 | **clipped by 12px** |
| 900px | 1012 | **clipped by 112px** |
| 861px | 1012 | **clipped by 151px** |

**The flag does not reflow** — `right` stays at 1012 from 1000px down to 861px while the
viewport shrinks, so the clipping grows monotonically. **861px is one pixel above the 860px
cliff**, which was chosen precisely to guarantee the worst case fits. Block marks anchor at
696.7 and behave correctly. This is inline-only.

**Why every check passed over it:** `markrail` asserts the flag anchors within 2px of
`.read`'s right edge, and that assertion is **true** — for the block marks its fixture
contains. The fixture has no inline mark. The hole is coverage, not logic.

## The decision is made. Implement it; do not re-open it.

**Refuse an inline `data-mark` at build time.** Not "support it", not "clamp it".

The reasoning, so you can implement it faithfully rather than guess:

- `review_artifact.py` **already refuses** two neighbouring mistakes — an `id` on an
  ancestor rather than on the marked element, and a blank or whitespace-only label. This is
  the same class and gets the same treatment. **Follow that existing refusal's idiom
  exactly**; do not author a second error path.
- A build-time refusal is **loud**. A clipped flag is silent, and this repo's standing
  preference is the loud failure — a silently mispositioned flag is the worse shape.
- Supporting inline marks properly means anchoring from the nearest **block** ancestor,
  which is probably the eventual right answer but is a product change to what a flag points
  at (a passage versus a phrase). **That is not yours** — `#367` increment 2b is already
  awaiting his ruling, and adding a second unruled change to the same feature is how
  something ships and then gets argued with. **File it in your report and I will file the
  task.**

**`file-formats.md` must change in the same commit**, because "any element inside `body`" is
now false. State the restriction and say why, in the voice of the surrounding text.

## What counts as "inline" is the one judgement call, and it has a trap

**Do not hardcode a tag list.** `<strong>`, `<em>`, `<a>`, `<code>`, `<span>` is the obvious
list and it is wrong twice over: it misses `<abbr>`, `<kbd>`, `<mark>`, `<sub>` and friends,
and it wrongly catches an element the artifact's own CSS has made `display:block`.

The builder parses HTML and cannot compute layout, so you cannot ask for a computed style.
**So decide on a rule you can defend and state it**: the defensible options are a
**block-element allowlist** (the marked element must be one of a named set of block
containers — `p`, `li`, `section`, `div`, `h1`-`h6`, `blockquote`, `td`, `figure`, …) or an
**inline denylist**. **Prefer the allowlist**, and say why in your report: an unknown tag
should refuse rather than silently clip, and an allowlist fails closed while a denylist fails
open on every element nobody thought of.

Whichever you pick, **the set lives in one named constant beside the other essential-marks
constants**, not scattered in a condition.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `review_artifact.py`, `test_review_artifact.py`,
   `file-formats.md`, and the guard fixture under `dev/capture/fixture/` (plus rebuilt
   `.dreamwork/review/*.html` **only if** your change restamps them — if it does not touch
   the template, they must be **unchanged**, and say which). `git status --porcelain` shows
   nothing else. **`git diff --stat watch.py test_watch.py` is empty** — a lane holds both.
2. **`python3 -m pytest test_review_artifact.py -q -p no:randomly` exits 0**, with at least:
   - `test_an_inline_data_mark_is_refused`
   - `test_a_block_data_mark_is_still_accepted`
   - `test_the_refusal_names_the_element_and_the_label`
3. **The refusal message names the offending element AND its label.** A build error that
   says only "inline mark refused" makes an author hunt. Match the existing refusals' level
   of detail — read them first.
4. **THE CRITERION I CARE ABOUT MOST — the guard fixture gains an inline mark, and you prove
   the guard sees it.** The fixture's blindness is *why* this shipped. So:
   - **First**, add an inline mark to the fixture and run `markrail` **before** any
     `review_artifact.py` change. It must **FAIL** (or the build must refuse, once your
     change lands). If it stays **green** with an inline mark present, the assertion is not
     watching the anchor and reporting that is worth more than the fix.
   - **Then** implement, and show the guard green after.
   State both results verbatim. **`markrail`'s port for you is `39893`.**
5. **Three discriminating reds**, each with the exact failing test name and confirmation
   neighbours stayed green:
   - remove the inline check ⇒ `test_an_inline_data_mark_is_refused` fails;
   - make the allowlist reject a block element too ⇒
     `test_a_block_data_mark_is_still_accepted` fails;
   - drop the label from the message ⇒ the third fails.
   Separate injections, restored from a `cp` snapshot — **never** `git checkout -- `.
   **One warning from experience an hour ago:** my own first injection for this feature
   targeted a CSS rule that did not exist, and the guard passed. **A green red-run is a
   finding, never a relief** — verify your injection actually reached the code by grepping
   for it before you believe the result.
6. **Assert the precondition your fixture depends on.** If a test needs the fixture to
   contain an inline mark for its meaning, assert at runtime that it does — derive it, do not
   trust a literal. A fixture that gains a third mark tomorrow must not quietly un-test this.
7. **`python3 lint.py` exits 0** and **`just audit-styleguide` passes**, each run as its
   **own command** — never in the same shell command as a `git commit`.
8. **The seventeen existing artifacts still build and still pass their staleness checks.**
   If your change restamps them, rebuild in the same commit; if it does not, prove it did
   not by showing `git status` clean for `.dreamwork/review/`.

## The hollow outcome

**A refusal that the fixture never exercises.** You will have added a check, a test, and a
doc line, and the guard will still be blind to the input class that shipped this bug — so the
*next* geometry change to the flag gets the same free pass. Criterion 4 is the whole task;
criteria 2 and 5 are the easy part.

## The rules that matter most here

**A green red-run is a finding, never a relief**, and verify the injection reached the code.

**Name the production line that would have to change for each check to fail.**

**Before you report an edge case, enumerate its neighbours.** This task exists *because* a
lane's caveat named one axis and held the element type constant. Yours to enumerate: a mark
on a `<td>`; a mark on an element the CSS floats or absolutely positions; a mark on the
**first** element in the body; two marks on the same block. Say what each does.

**`grep -c` exits 1 when the count is zero**, so an `&&` chain reports a skipped tail as a
pass.

## Files

**Yours:** `review_artifact.py`, `test_review_artifact.py`, `file-formats.md`,
`dev/capture/fixture/**`, `dev/capture/markrail.mjs` (only if the assertion itself needs
sharpening — say so if you touch it), rebuilt `.dreamwork/review/*.html` if restamped.

**Read, do not edit:** `review-artifact.template.html` (**read it to understand the anchor;
you should not need to change CSS for a refusal — if you believe you do, stop and report**),
`.dreamwork/tasks.md` (#396 and #367), `transitions.md`, `watch-design.md`, `justfile`,
`CLAUDE.md`, `.dreamwork/lessons.md`.

**Never touch — a live owner right now:** `watch.py`, `test_watch.py` (**#354 increment 1**);
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`,
`.dreamwork/docs/research/2026-07-28-parallel-lanes-evidence.md` (**#264**).

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live. **Do not generate load
  deliberately** — but note the asymmetry in your favour: these guards fail by dropping
  frames, so **load manufactures false reds only. A green under load is conclusive; a red
  needs a re-run at low load.** Check `cut -d' ' -f1-3 /proc/loadavg` before believing a red.
- Guards import playwright by **absolute path**; see the top of any `dev/capture/*.mjs`.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for **new**
  files — `--only <directory>` silently skips untracked ones. A bare `git commit` after
  `git add` commits the whole index and will bury a concurrent lane's staged work. Both
  happened in this tree. **Do not push.**
- Use **`fix(#396): …`**. `dream(...)` is reserved for a commit that lands a dream journal;
  if you write one, **name it in its own `git commit --only <path>`**.
- Cap yourself at roughly **35 minutes**. **Priority order: criterion 4's fixture red first,
  then the refusal, then the doc.** The fixture red is the finding; the refusal is
  mechanical once you have it. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the fixture result before
your change, verbatim** (criterion 4's first half — this is the one I will read first); the
three reds verbatim with exact test names and which neighbours stayed green; whether you
chose an allowlist or a denylist and why; the exact refusal message; what each of the four
neighbour cases does; whether the seventeen artifacts restamped; the exact `file-formats.md`
text you wrote; the load at which each guard verdict was taken; the production line named
per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
