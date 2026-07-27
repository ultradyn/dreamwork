# #254 — one rooted exchange per question

**Status: design only.** Approved by the human at 2026-07-27 23:03 as
option N1, and the approval is for this document. Not a parser change,
not a file-format change, not UI code, not a migration, not a deploy, not
a transition. Where this file says "the implementation would", it is
describing work that is not authorised yet.

**Goal it serves.** When he reads a question thread he can tell instantly
who said what, in what order, and in reply to what. That is the whole
acceptance test; everything below is in service of it.

## 1. What he reported, and what the evidence actually shows

His report: a human `Note` followed by a loop answer renders as visually
similar sibling bullets, so his own later note reads as an unrelated
continuation rather than a reply. Evidence:
`.dreamwork/review/evidence/review-note-reply-unclear.png`.

Reading the pixels against the file finds **two separate defects on one
card**, and only one of them is #254:

1. **The one N1 addresses.** A recognised human `Note` and a recognised
   loop `Follow-up` render as adjacent `.follow` rows inside the same
   `.threadin`. They differ only by a dim `you` / `loop` label and one
   step of luminance. Nothing on screen says the second is a response to
   the first, or that a third is a response to the second.
2. **The one N1 does not address, and which produced this particular
   screenshot.** The loop's contribution was tagged
   `- **Answer (loop, <ts>):**`. That prefix is in neither `NOTE_TAGS`
   nor `ANSWER_TAGS`, so it is not a contribution at all — it fell into
   the entry's **body** and `mdB` rendered it as a `·` list item with its
   raw tag visible as text, above the thread. That is why the 14:48 reply
   sits above the 14:47 note it answers: it was never in the sequence.
   The tag has since been repaired to `Follow-up (loop, …)` in the live
   file.

Both readings are worth stating because they cost different things. The
consequence is recorded in §8 as an objection: **N1, shipped alone, does
not change how the entry in the screenshot renders.** See D1.

## 2. The relationship rule, as a decision procedure

Stated as a function so an implementer decides nothing. Its inputs are a
single parsed question entry; it returns three things.

```
qaBranch(q) -> [lead, root, branch]
```

- `lead` — contributions that precede the root. Rendered exactly as
  today, including the settled-thread collapse.
- `root` — the one thing a branch hangs off, or none.
- `branch` — contributions that are responses to the root. **One flat
  list. One inset depth. Never a tree.**

Inputs, all of them already produced by `_parse_entries`:

- `q.follows[]` — recognised contributions in **file order**, each with
  `author` (`human` / `loop` / `None`) and `when` (or `None`).
- `q.answer`, `q.answer_at` — the lifted resolution and **how many
  contributions preceded it**. `answer_at` is the positional cut #128
  added, and it is the only signal step 1 needs.
- `reply_at` — the index of the first contribution carrying an explicit
  reply tag. **This does not exist today.** See §3.

### The procedure

1. **A resolution exists** (`q.answer` is non-null *and* `q.answer_at`
   is non-null):
   `root = the resolution`;
   `lead = follows[0 : answer_at]`;
   `branch = follows[answer_at : ]`. Stop.
2. **Else an explicit reply tag exists** at index `i = reply_at`:
   - if `i == 0` there is nothing above it to reply to →
     **flat**: `lead = follows`, `root = none`, `branch = []`. Stop.
   - else `root = follows[i-1]`; `lead = follows[0 : i-1]`;
     `branch = follows[i : ]`. Stop.
3. **Else** → **flat**: `lead = follows`, `root = none`, `branch = []`.

Step 1 outranks step 2 deliberately, so the two mechanisms can never both
fire on one entry and disagree about the root. A `Reply` written *above* a
resolution therefore sits in `lead`.

### The governing principle, for cases this document did not list

**Prefer flat over wrongly-attached.** His tie-breaker — *if no root
exists, keep the note top-level rather than guessing* — generalises: a
flat render under-claims a relationship the reader can still recover from
order and timestamps, while a wrong branch makes a false claim about who
answered whom, on the channel whose entire job is telling him what was
said. When a case is genuinely ambiguous, return `branch = []`.

Its corollary, and it is not optional: **never derive attachment from
timestamps.** File order is the chronology. A stamp comparison would be a
second mechanism able to disagree with the first, and it would disagree
precisely on the entries whose stamps are missing or hand-edited — the
same argument that keeps `parse_open_questions` sorting on priority alone.
Stamps are rendered; they are never read for structure.

### Every case, named

| case | result | why |
|---|---|---|
| Note, then Answer, then Note | `lead=[note]`, root=answer, `branch=[note]` | step 1. The pre-answer note is discussion that led to the resolution — #128's existing cut, unchanged. |
| Answer that comes **after** a Note | as above | `answer_at = 1`, so the note is in `lead`. This is the case that must not put an earlier note *under* a later answer. |
| Note with **no Answer anywhere** | **flat** | step 3. His tie-breaker. Also the case in his own screenshot (D1). |
| **Two Answers** | root = the **last**, `branch` = what follows it | Inherited, not chosen: `_parse_entries` overwrites `cur["answer"]` and resets `answer_at` on the second answer bullet, so by the time the rule runs the first answer's text **no longer exists**. See §8 — that discard is a pre-existing bug, reported not fixed. |
| explicit `Reply` with **no preceding** contribution | **flat** | step 2's `i == 0` branch. Do not invent a root out of the entry body. |
| interleaved Notes and Replies after a root | all join **one** branch, in file order, at **one** depth | N1's explicit constraint. A reply to a reply is a branch member, not a second level. |
| a root with **nothing after it** | root rendered as today, **no branch container emitted** | An empty branch is a rail with nothing on it — a visual claim about content that is not there. |
| the human **edited** an earlier entry | recomputed from scratch on the next parse | The rule is a pure function of file order and tags. It keeps no state and gives a contribution no identity, so an edit cannot leave a stale attachment behind. If the edit changes a tag, the branch changes shape, and it does so through the existing regroup like any other layout change. **Never key a contribution by its text** — a rendering is not a record, and `append_*` hard-wraps his words on disk. |
| a contribution with an **unrecognised** tag | not a contribution at all — body prose | Today's behaviour, and it is what the screenshot shows. State it in the implementation's comments so nobody assumes the rule saw it. Same reason `note_author` returns `None` rather than guessing: a wrong attribution is worse than an absent one. |
| the entry is in `## Answered` | **flat** — no branch on this section at all | D3. |

## 3. What is read from the file, and what is inferred

**Present in the text today** (`file-formats.md`, "`.dreamwork/questions.md`";
`watch.py`'s `NOTE_TAGS` / `ANSWER_TAGS`):

- literal `## Open` / `## Answered` headings, matched exactly;
- `- **Note (human, via <channel>, <ts>):**` → human;
- `- **Follow-up (loop, <ts>):**` → loop;
- legacy `Follow-up (via watch, …)` → human, `Follow-up (in-session, …)` → loop;
- `- **Answer (via watch, <ts>):**` → human, lifted **in the Open section only**;
- `answer_at`, the positional cut;
- `when` per contribution, from the tag's closing `)`.

**Inferred by this rule:** only *adjacency to the root*, which is
positional and already in the parse. Nothing else. Authorship is read,
never inferred. Order is read, never reconstructed. Step 1 needs **no new
signal whatsoever** — that is why it is the part of N1 that is
implementable.

**Absent today, said loudly:**

- **`Reply (loop, <ts>)` is not a recognised tag.** It is in neither
  table, so today it renders as body prose with its tag visible and no
  attribution. **Step 2 of the procedure is therefore unimplementable
  without a `file-formats.md` + `NOTE_TAGS` change, which this grant
  excludes.** Scope it as a follow-up (§8). Do not quietly add the tag.
- **There is no loop-authored resolution tag at all.** `Answer (via
  watch, …)` is *his* — it is written by `POST /answer` and by nothing
  else. So "the loop Answer becomes the root" has **no referent in the
  file** for a question the loop replied to and he never answered. That
  is the gap behind D1 and the objection in §8.

## 4. Visual and structural spec

Written in `watch-design.md`'s existing vocabulary. **No new component.**

**The branch container is `.thread` with a modifier**, `.thread.branch`.
`.thread` already means "these belong to the thing above": a 1px
`--line` left rail and `padding-left:1ch`. That rail *is* the one inset
depth N1 asks for, and it is already the page's idiom for it. Adding a
second container would be authoring a second answer to a question the
page has answered.

- **The rail must start at the root's bottom edge** so the connection is
  *drawn* rather than implied. A branch that floats a row below its root
  is the current bug with extra indentation.
- **Contributions inside are unchanged `.follow` rows**: the `↳`
  `::before`, the dim uppercase `.who` label (`you` / `loop`), the
  quieter `.qts` stamp, and the luminance split — human at `--lit`
  against the loop's `--muted`. Emphasis on this page is luminance.
  **No accent**: the accent is for live and actionable things.
- **The root says it is a root.** When the root is the resolution
  (step 1) it already carries the awaiting state's accent rail and `✓`;
  nothing is added. When the root is a contribution (step 2) it takes
  `.follow.root`, whose only job is to be the rail's anchor — no new
  colour, no badge.
- **`lead` keeps today's treatment exactly**, including the `.qthread`
  disclosure at `QTHREAD_FOLD_AT = 2`. One note is still not a thread.
- **The branch never collapses.** It is live, and it is where a note he
  just wrote lands. #128's lesson stands: never let the page fold away
  what the human just wrote. Only the segment a resolution has already
  answered may collapse.
- **A second rail inside a branch must be impossible by construction,
  not prevented by CSS.** The branch is a flat list; there is no code
  path that nests one. That is the difference between N1 and a staircase,
  and it should not depend on a selector.

**Narrow widths.** The cost of one depth is `.thread`'s `1ch` plus a 1px
rail, on top of `.follow`'s existing `padding-left:2.6ch;
text-indent:-2.6ch` hanging indent — so roughly one character of reading
column, once, no matter how long the exchange runs. That is the entire
reason N1 caps the depth. Below the page's narrow breakpoint, **keep the
rail and drop the branch's `padding-left` to 0**: adjacent to the rail the
indent is redundant, and the rail is the part that carries the
relationship. An implementer measures the resulting reading column against
the page's existing minimum rather than assuming one character is free —
the reflow work found that the interesting widths are in the *middle* of a
sweep, not at the ends.

## 5. Accessibility — structure, not decoration

A visual hierarchy that announces as a flat list is a failed design here,
so the semantics are part of the spec and not a follow-up.

- **The exchange becomes one real list.** `lead`, root and `branch`
  render as a single `<ul>` of `<li>`; the branch is a **nested `<ul>`
  inside the root's own `<li>`**. A screen reader then announces "list, N
  items … item k … list, M items", which is exactly one level of
  nesting — matching the pixels. When the root is the resolution block,
  that block is the `<li>`; it is already one block.
  **A sibling `<ul>` renders identically and announces flat**, which is
  the failure this check exists to catch (§7, check 5).
- **Authorship and time lead the announcement.** `.who` and `.qts` are
  already the first text nodes in a `.follow` row, in that order, so a row
  reads "you · 2026-07-26 14:47 · <text>". Keep them in DOM order; do not
  move them into `::before` or hide them from the tree.
- **The `↳` glyph stays decorative** — it is CSS `content` and correctly
  unannounced. The instinct to add a spoken "reply to" is the wrong fix:
  the nested list already carries that, and a second statement of it is
  noise on every row.
- **The branch carries a group label naming what it replies to**, for a
  reader who lands inside it: `aria-label` on the nested `<ul>`, derived
  from the root — `replies to the answer`, or
  `replies to your note of <ts>` / `replies to the loop's note of <ts>`.
  Derived, never invented: if the root has no stamp, omit the stamp
  rather than guessing, the same rule as `note_author` and `answered_at`.
- **Focus order is unchanged**, because the branch contains no focusable
  element. Card → the settled thread's `<summary>` if present → the
  composer field → send → mode group. Two rules follow:
  - **The composer stays outside the branch.** One input per card (#103).
    A box inside a branch would read as "reply to this turn" — a promise
    `/comment` cannot keep, since it appends to the end of the sequence.
  - If the branch ever gains a control, it sits after the root and before
    the composer: DOM order is reading order is tab order.
- **No live region.** The branch arrives inside a card the tick
  re-renders; announcing it would double up with the row itself.
  And `focus()` into a closed `<details>` silently does nothing — so if a
  restore ever has to place the caret near a branch, folds are restored
  before state, and the refocus checks that it landed.

## 6. Motion and reduced-motion parity

Described, not implemented. **No new gesture is authored — every case
already has a cell in `transitions.md`'s state matrix.**

- **A note landing in a branch** is the matrix's *"same card, a note
  lands"* cell: the note lifts from the box into the thread and the card
  grows, same seam, same regroup. Where it lands is a layout fact, not a
  motion one.
- **A branch appearing for the first time** (a root gains its first
  reply) reuses the unfold reveal: `.qreveal` + `.dreamin`. The start
  state must **snap** — `transition:none` on the start-state class,
  reflow, then remove it next frame — or the class animates *toward* the
  start value and reads as a pop-in.
- **A branch emptying** departs on the page's one departure idiom:
  `dreamAway` ghosts it at the rect it occupied, clipped below the line
  the survivor still fills.
- **A contribution moving from `lead` into `branch`** because an answer
  landed between them is the *"same state, moved"* cell: it **slides**,
  and if the card resized the height travels. It must not teleport, and
  it must not re-enter with `.dreamin` — it survived, so it travels.
- **Reduced motion is a hard contract.** With `prefers-reduced-motion`,
  the branch is at its end state immediately: no travel, no ghost. The
  parity obligation is that **the DOM and the computed inset are
  identical** to the animated end state; only the frames differ. A
  reduced-motion path that lays out differently is a second design.

## 7. How an implementation would be proven

This repo's standard, and it is the reason this section is long: a check
is not verification until it has been red; the strongest evidence is a
*discriminating* red; **a green red-run is a finding, never a relief**;
and a check must assert at runtime the precondition its meaning depends
on.

### Fixtures

Five entries added to the **frozen** fixture at
`dev/capture/fixture/.dreamwork/questions.md` (a guard that reads mutable
content is testing the content, and its false reds train you to ignore
it):

- **F1 `rooted`** — Note(human) → Answer(via watch) → Note(human) →
  Follow-up(loop). One lead, one root, a branch of two.
- **F2 `no root`** — Note(human) → Follow-up(loop), **no answer
  anywhere**. Must render flat.
- **F3 `two answers`** — Note → Answer(a) → Note → Answer(b) → Note.
- **F4 `root, no branch`** — Note → Answer, nothing after.
- **F5 `unrecognised tag`** — a literal `- **Reply (loop, <ts>):**`
  bullet, pinning that today it is body prose and **not** silently
  treated as a contribution.

### The checks, each with the line that reddens it

1. **F1 partitions correctly.** `lead` length 1, root is the resolution,
   `branch` length 2 in file order.
   *Reddens on:* the cut expression in `qaBranch` — replace `q.answer_at`
   with `0` and the lead empties.
   *Runtime precondition:* derive `answer_at` and `follows.length` from
   the fixture and assert `0 < answer_at < follows.length`. A literal `1`
   tuned to today's fixture is a check with an invisible expiry date, and
   this exact shape has already gone vacuous here once.
2. **F2 emits no branch.** `querySelectorAll('.thread.branch').length === 0`.
   *Reddens on:* the null test `(q.answer && q.answer_at != null)` —
   delete it, the fallback becomes `0`, and every contribution lands in
   the branch. That is the obvious-looking arithmetic #128's guard
   already caught once.
   *Runtime precondition:* assert the F2 entry has **≥2 contributions**,
   or "no branch" is satisfied by "no contributions".
3. **F3 roots at the last answer.** Assert `answer_at` equals the count
   of contributions before the **second** answer bullet, derived at
   runtime by locating both bullets in the fixture text.
   **What this check does not prove, stated in the check:** because
   `_parse_entries` overwrites `cur["answer"]`, the first answer's text is
   gone before the rule runs, so this cannot distinguish "rooted at the
   last answer" from "the first answer never existed". The discriminating
   version needs the parser to keep both, which is out of scope. Recording
   the limit is the point — an unstated one is how a check gets believed
   as the thing it proxies.
4. **The depth is exactly one, measured.** The left content edge of a
   branch row minus that of the root row equals one `.thread` inset, and
   **no row in the card sits at two insets**.
   *Reddens on:* whatever emits the branch container — make it recurse and
   a staircase appears.
   *Runtime precondition:* assert the branch has ≥2 rows **and** that the
   card contains at least two distinct inset values, or "no row at two
   insets" passes on a card with one row.
5. **The nesting is real.** The branch is a `<ul>` and its ancestor is the
   root's `<li>`, not its sibling; an accessibility-tree read reports one
   level of nesting.
   *Reddens on:* the branch container's tag, and separately on its parent
   — moving the `<ul>` to be a sibling changes **nothing** visually and
   flattens the announcement. Invisible to every geometry check, which is
   why it is its own check.
6. **A note posted into a branch travels.** Assert some captured frame is
   *part-way* between the two ends using `between(vals, first, last)`
   copied verbatim, with a literal span floor and the **measured** span
   printed. An end-state assertion cannot fail on a motion bug and
   neither can "did it move".
   *Window:* ≤1400ms, and additionally assert the row node was never
   replaced — a guard that watches long enough will see a later tick's
   regroup produce the result it wanted, which is how `regroup.mjs` stayed
   green over a teleport for a day.
7. **Reduced-motion parity.** With the query forced, the same card yields
   the same branch DOM and the same computed inset; only the frame count
   differs.
   *Reddens on:* implementing the enter as a layout change rather than an
   opacity/transform one.
8. **`lint.py` gains nothing here, and that is stated rather than
   papered over.** The branch is a render-side rule over signals the
   format already defines, so it adds no file obligation. Inventing a
   lint check for it would be a check that cannot fail for its stated
   reason. *If* the `Reply (loop, …)` follow-up lands, that one **does**
   need a format entry and a lint check, in the same commit.

### Two obligations on whoever runs this

- **Run every injection above, and treat a green one as a finding.** If
  reinstating the bug leaves the check green, the check is wrong — do not
  conclude the code was fine.
- **Which of his routes and gestures does this not reach?** The branch
  renders on four surfaces through `qaCard`: the dashboard, `/questions`,
  the review dock, and the card the submit morph restates in place. A
  guard that only visits `/questions` is the #179 failure verbatim — the
  dashboard is the harder page to drive and the one he actually uses. **At
  least one guard must drive the dashboard**, where cards nest inside a
  fold; and a closed `<details>` does not `display:none` its children in
  current Chromium, so ask `checkVisibility()`.

## 8. What this does not do

**The objection, stated plainly, with N1 implemented as approved.**
N1 does not change the card he reported. That entry has no `Answer` — only
a `Note (human, …)` at 14:47 and a `Follow-up (loop, …)` at 14:48 — so
step 3 applies, his own tie-breaker holds, and it renders exactly as it
does today. What actually changed that screenshot was repairing an
unrecognised `Answer (loop, …)` tag. So **shipping N1 alone would close
#254 and leave the evidence unchanged.** His ruling stands and this
document implements it; the recommendation is that the loop-resolution-tag
follow-up below be treated as part of the same outcome rather than as a
nice-to-have.

Also out of scope by design:

- **Per-turn reply targets / true nesting.** Explicitly rejected by N1.
  Recorded here so it is not re-proposed later as an improvement.
- **`## Answered`.** D3 keeps it flat.
- **Anything touching `watch.py`, `lint.py`, `file-formats.md` or a
  guard.** This grant is a document.

### Follow-ups this design implies (named, not filed)

1. **A loop-authored resolution tag** — `Reply (loop, <ts>)` in
   `NOTE_TAGS`, or a loop-attributed answer form — without which step 2
   cannot run and his reported entry stays flat. The one that makes #254
   visible where he saw it.
2. **Two-answer data loss.** `_parse_entries` overwrites `cur["answer"]`,
   so on an entry with two `Answer (via watch, …)` bullets the earlier
   answer's words are **gone from every surface**. The live
   `.dreamwork/questions.md` has such an entry.
3. **`## Answered` shows his answer as raw body prose.** `lift_answer` is
   `False` for that section, so a retained `- **Answer (via watch, …):**`
   bullet falls into the body and renders as a `·` item with its tag
   visible and **no `you` label** — measured: **15 of 29** live answered
   entries. That is the screenshot's defect on the more-travelled path,
   and #109 makes it a correctness bug rather than a cosmetic one.
4. **Threading in `## Answered`**, if he wants it — needs the resolution's
   position inside the sub-bullet sequence, which is a format change.
5. **Doc drift:** `_parse_entries`'s docstring says an Answer sub-bullet is
   never an entry "even un-indented". That holds only when
   `lift_answer=True`; in `## Answered` it is indentation that saves it.

## 9. Decisions N1 left open — mine, so one line can overrule each

- **D1 — A root is a RESOLUTION, not merely the first loop contribution.**
  Only two things are roots: an `Answer (via watch, …)` bullet (state
  `awaiting`) and, were `## Answered` in scope, the `→ <verdict> (<ts>):`
  head. A loop `Follow-up` is **not** promoted to root. *Reasoning:*
  promoting it is inference from adjacency, which is exactly what N2 was
  rejected for, and it inverts on the common shape where the loop asks a
  clarifying question and he answers it — the loop's question would become
  the root and his answer a reply to it. Unfalsifiable and wrong. *Cost:*
  §8's objection. **Overrule this one line and his screenshot is fixed at
  the price of that inversion.**
- **D2 — A question block has at most ONE branch.** Not "a branch per
  root". *Reasoning:* it is what keeps the rule a decision procedure
  rather than a tree walk, and it is the only reading of "a single inset
  depth" that survives a long exchange.
- **D3 — `## Answered` renders flat; the branch is an Open-section
  structure.** *Reasoning:* the resolution head sits at the *start of the
  body* there, positionally before every sub-bullet, while temporally it
  may follow several of them. Rooting at it would attach every pre-fold
  note as a reply to the resolution — a wrong attachment, and the
  prefer-flat principle forbids it. The alternative is a timestamp cut,
  which §2 rules out.
- **D4 — Step 1 outranks step 2**, so the resolution always wins over an
  explicit reply tag. *Reasoning:* two mechanisms that can both fire will
  eventually disagree, on the one channel where a disagreement is a false
  claim about what he said.
- **D5 — The nesting is a `<ul>` inside the root's `<li>`**, not ARIA
  attributes on divs. *Reasoning:* native list nesting is what a screen
  reader announces as depth without anyone maintaining a role.
- **D6 — At narrow widths the rail stays and the padding goes**, rather
  than dropping the inset entirely. *Reasoning:* the rail is the part that
  carries the relationship; the indent is redundant once the rail is
  adjacent.
- **D7 — An empty branch emits no container.** *Reasoning:* a rail with
  nothing on it is a visual claim about content that is not there.

--- SUMMARY ---

- **What it is.** A design-only spec for #254, option N1 as he approved it
  at 23:03: the resolution becomes the root of a question's exchange, and
  later notes and replies render as **one flat branch at a single inset
  depth** beneath it. Two files only — this spec and
  `.dreamwork/review/note-reply-threading-254.html`.
- **The rule** is a three-step decision procedure over one parsed entry,
  returning `[lead, root, branch]`. Step 1 cuts at `answer_at` (a signal
  the parser already produces). Step 2 handles an explicit reply tag.
  Step 3 is flat. Every ambiguous case is tabulated, and the governing
  principle for unlisted ones is **prefer flat over wrongly-attached**,
  with a hard prohibition on deriving attachment from timestamps.
- **Signals.** Step 1 needs nothing new. **Step 2 does:**
  `Reply (loop, …)` is not a recognised tag today, and there is **no
  loop-authored resolution tag at all** — flagged loudly, scoped as a
  follow-up, not assumed.
- **The objection.** N1 shipped alone **does not change the card he
  reported**, because that card has no `Answer` — only a loop
  `Follow-up` — so his own tie-breaker keeps it flat. The screenshot's
  actual defect was an unrecognised `Answer (loop, …)` tag falling into
  the body. His ruling is implemented as approved; the recommendation is
  that follow-up 1 ride along with it.
- **Visual/a11y/motion** reuse what exists: `.thread`'s rail *is* the one
  inset depth; `.follow` rows keep the `you`/`loop` label, stamp and
  luminance split; the branch is a nested `<ul>` inside the root's `<li>`
  so the nesting is announced, not just drawn; the composer stays outside
  the branch; every motion case already has a cell in `transitions.md`
  and no new gesture is authored.
- **Proof** is specified as five fixtures (including "no root" and "two
  answers") and eight checks, each naming the production line that
  reddens it — plus the two checks that would otherwise be hollow: F2
  needs its "≥2 contributions" precondition or "no branch" passes on
  nothing, and the two-answer check **records what it cannot prove**
  because the parser discards the first answer before the rule runs.
- **Three out-of-scope bugs found while reading** and reported not fixed:
  the two-answer text discard; `## Answered` rendering his answer as raw
  body prose with no `you` label (**15 of 29** live entries); and a
  `_parse_entries` docstring claim true only for `lift_answer=True`.
