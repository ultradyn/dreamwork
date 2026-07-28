# #254 — Threaded review notes: written design only

**Status: design only. Not authorised for implementation.**

Approved as **N1** (human via watch, 2026-07-27 23:03, `rec` = Accept N1) and
amended by **R1** (human via watch, 2026-07-27 23:38, `rec` = R1 — give the
loop a resolution tag). This document is the implementable rendering rule
those two rulings produce. It supersedes
`.dreamwork/docs/plans/note-reply-threading-254.md` for anyone who will
build it; that earlier plan is history and still true on the parts R1 did
not change.

**Scope limit is part of the approval.** His ask granted a design/spec
document and explicitly **not** parser, file-format, UI, migration,
deployment, or transition changes. Where this file says "the
implementation would", it describes work that needs a separate word.

**Goal.** When he reads a question thread he can tell instantly who said
what, in what order, and in reply to what. That is the whole acceptance
test.

---

## 1. What he reported, and what the evidence actually shows

Evidence: `.dreamwork/review/evidence/review-note-reply-unclear.png`.

His report: a human Note followed by a loop reply reads as sibling
bullets on the main question, so authorship and causality are obscure.

Reading the pixels against the file finds **two separate defects on one
card**, and only one of them is #254:

| what the screenshot shows | mechanism | does N1+R1 fix it? |
|---|---|---|
| a note and a reply as similar siblings | both are `.follow` rows in one `.threadin`; they differ by a dim `you`/`loop` label and one step of luminance | **yes** — this is the task: one flat branch under a resolution root |
| the 14:48 reply sitting *above* the 14:47 note it answers | its tag was `Answer (loop, …)`, in neither `NOTE_TAGS` nor `ANSWER_TAGS`, so it was never a contribution: it fell into the **body** and rendered as a `·` item with its raw tag as text | **no** — a tag-recognition bug, since repaired in the live file to `Follow-up (loop, …)` |

**N1 alone does not change that card.** It has no human `Answer` — only
`Note (human, 14:47)` and `Follow-up (loop, 14:48)` — so the no-root
tie-breaker keeps it flat. **R1 closes that gap** by giving the loop a
deliberate resolution tag that *is* a root. Without writing that tag on
the card, the render stays flat; with it, N1 runs.

---

## 2. The data it reads (describe only — do not change)

Authoritative grammar: `file-formats.md` § `.dreamwork/questions.md`.
Implementation today: `watch.py`'s `NOTE_TAGS`, `ANSWER_TAGS`,
`note_author`, `answer_author`, `sub_when`, `_parse_entries`,
`parse_open_questions`, `parse_answered`.

### Markers that exist and are recognised

| prefix (exact match) | who | where it goes |
|---|---|---|
| `- **Note (human,` | human | `follows[]` |
| `- **Follow-up (via watch,` | human (legacy) | `follows[]` |
| `- **Follow-up (loop,` | loop | `follows[]` |
| `- **Follow-up (in-session,` | loop (legacy) | `follows[]` |
| `- **Answer (via watch` | human | lifted to `q.answer` + `q.answer_at` **in Open only** |

Each contribution carries `author` (`human` / `loop` / `None`) and
`when` (from the tag's closing `)`, or `None`). File order is chronology
(#128). Continuation lines of a sub-bullet belong to that bullet, not the
body.

`answer_at` is the positional cut: how many recognised contributions
preceded the lifted Answer. It is the only signal step 1 of the rule
needs, and the parser already produces it.

### Markers that look right and match nothing

The renderer matches an **exact prefix**. Anything else is not a
contribution: it falls into the entry **body** and renders as a `·` item
with its raw tag visible and **no author label** (#340 / #343). Measured
live failures that have already occurred:

- `Answer (loop, …)` — the #254 screenshot's second defect
- `Note (loop, …)`
- `Reply (loop, …)` — **three** such bullets sat unrendered until
  `lint.check_author_tags` found them

### Ambiguities that force a guess at render time (and must not)

These are the places the rule is forbidden from inventing structure:

1. **No loop resolution tag exists today.** `Answer (via watch, …)` is
   *his* — written by `POST /answer` only. A loop contribution that
   settles a question has no recognised spelling. That is why "the loop
   Answer becomes the root" (N1) has no referent on cards he never
   answered. **R1 names the fix; the design-only grant forbids landing
   it.**
2. **Authorship is closed-set, never inferred.** `note_author` returns
   `None` rather than guessing. A wrong attribution is worse than an
   absent one (#109).
3. **Timestamps are rendered, never structural.** File order is
   chronology. A stamp comparison is a second mechanism able to disagree
   with the first — and it would disagree exactly on missing or
   hand-edited stamps.
4. **Two Answers on one Open entry.** `_parse_entries` overwrites
   `cur["answer"]` and resets `answer_at`, so the earlier answer's text is
   **gone from every surface** before any render rule runs. The rule
   inherits "last Answer wins"; it does not invent retention. (Out of
   scope; see §7.)
5. **`## Answered` does not lift answers.** `lift_answer=False` there, so
   a retained Answer bullet falls into the body. Threading that section
   would root every pre-fold note under a head that sits at the *start*
   of the body while temporally following several of them — a wrong
   attachment. This design keeps Answered flat (D3).
6. **Unrecognised tags are body prose.** The rule never promotes them.

### What R1 adds to the grammar (design obligation; not yet written)

A **new** recognised tag, distinct from `Answer (via watch, …)`:

```text
- **Reply (loop, <ts>):** <resolution text>
```

- **Who:** loop. Spelling is the one N1 already named and the one three
  live bullets already used (wrongly, as body).
- **What it means:** a loop **resolution**, not any loop reply. Writing
  it is a deliberate act by whatever produces the resolution.
- **What it is not:** a substitute for `Follow-up (loop, …)`. A
  non-resolution loop contribution keeps `Follow-up` and stays a branch
  member (or lead, if it precedes the root).
- **Where it must land, together:** `NOTE_TAGS` (or a dedicated table the
  parser and lint both import), `file-formats.md`, and parser tests, in
  **one** commit. Documenting a tag the renderer does not recognise is
  the #340/#343 defect written into the contract itself.

R2 (promote any loop contribution to root when he has not answered) and
R3 (ship N1 and accept the card stays flat) are **refused**. Reasons
kept: R2 inverts on the common shape where the loop asks *him* a
clarifying question and he answers it; R3 retires the honest-but-unsatisfying
fallback rather than leaving it for time pressure later.

---

## 3. The rendering rule (implement without re-deciding)

Stated as a pure function of one parsed Open entry. Inputs are already
produced by `_parse_entries` once R1's tag is recognised; nothing is
keyed by contribution text (hard-wrap makes text a non-identity).

```
qaBranch(q) -> [lead, root, branch]
```

- **`lead`** — contributions that precede the root. Today's treatment,
  including the settled-thread collapse at `QTHREAD_FOLD_AT = 2`.
- **`root`** — the one thing a branch hangs off, or none.
- **`branch`** — contributions that are responses to the root. **One
  flat list. One inset depth. Never a tree.**

### Procedure

1. **A human resolution exists** (`q.answer` is non-null *and*
   `q.answer_at` is non-null):
   - `root = the resolution` (the Answer block already drawn with
     awaiting rail + `✓`)
   - `lead = follows[0 : answer_at]`
   - `branch = follows[answer_at : ]`
   - Stop.

2. **Else a loop resolution exists** — the **last** contribution in
   `follows` whose tag is `Reply (loop, …)`, at index `i`:
   - `root = follows[i]` (the Reply itself is the root, not the row above
     it — R1 redefines the tag as a *resolution*, not "I reply to my
     neighbour")
   - `lead = follows[0 : i]`
   - `branch = follows[i+1 : ]`
   - Stop.

3. **Else → flat:** `lead = follows`, `root = none`, `branch = []`.

Step 1 outranks step 2 so the two mechanisms never both fire and
disagree. A `Reply` written above a later human Answer sits in `lead`.

### Governing principle for unlisted cases

**Prefer flat over wrongly-attached.** His tie-breaker — *if no root
exists, keep the note top-level rather than guessing* — generalises. A
flat render under-claims a relationship the reader can still recover
from order and stamps; a wrong branch makes a false claim about who
answered whom, on the channel whose entire job is telling him what was
said.

**Never derive attachment from timestamps.** File order is the
chronology. Stamps render; they never decide structure.

### Every case, named

| case | result | why |
|---|---|---|
| Note → Answer → Note | lead=[note], root=answer, branch=[note] | step 1; #128's cut |
| Note → Answer (answer after note) | same | `answer_at = 1`; earlier note must not hang *under* a later answer |
| Note → Follow-up(loop), no Answer, no Reply | **flat** | step 3; R2 refused |
| Note → **Reply(loop)** | lead=[note], root=Reply, branch=[] | step 2; **this is his screenshot, once the tag is written** |
| Note → Reply(loop) → Note → Follow-up(loop) | lead=[note], root=Reply, branch=[note, follow-up] | one branch, one depth |
| two Answers | root = the **last** | inherited: parser overwrites; see §7 |
| two Replies, no Answer | root = the **last** Reply | same supersession reading as two Answers |
| Reply as the only contribution (`i == 0`) | root=Reply, lead=[], branch=[] | a resolution with no prior discussion is still a root; empty lead and empty branch emit no extra chrome |
| interleaved notes after a root | all join **one** branch, file order, **one** depth | N1; no staircase |
| root with nothing after it | root as today, **no branch container** | empty rail claims content that is not there |
| unrecognised tag | not a contribution — body prose | today's behaviour; state it in the code |
| entry in `## Answered` | **flat** — no branch on this section | D3 |
| he edited an earlier entry | recomputed from scratch on next parse | pure function of file order + tags; no contribution identity |

### Before / after (the case he filed)

**Before (today, after the tag repair):**

```
[question body…]
  ↳ YOU  14:47  I added a task… has the HTML artifact been updated?
  ↳ LOOP 14:48  Yes for the two feature amendments…
[answer box]
```

Both rows are siblings inside one `.threadin`. Nothing says the second
answers the first.

**After (N1 + R1, with the loop's contribution written as `Reply`):**

```
[question body…]
  ↳ YOU  14:47  I added a task… has the HTML artifact been updated?   ← lead
✓ LOOP 14:48  Yes for the two feature amendments…                    ← root
  │  (branch empty → no rail emitted)
[answer box — outside the branch]
```

If a later human note arrives:

```
[question body…]
  ↳ YOU  14:47  I added a task…                                        ← lead
✓ LOOP 14:48  Yes for the two feature amendments…                     ← root
  │ ↳ YOU  15:10  Thanks — one more thing…                            ← branch, one depth
[answer box]
```

A second later note does **not** indent further. Same rail, same depth.

---

## 4. Visual structure (no new component)

Written in `watch-design.md`'s vocabulary.

**The branch container is `.thread` with a modifier**, `.thread.branch`.
`.thread` already means "these belong to the thing above": a 1px
`--line` left rail and `padding-left: 1ch`. That rail *is* the one inset
depth N1 asks for. Adding a second container would be a second answer to
a question the page has already answered.

- **The rail starts at the root's bottom edge** so the connection is
  *drawn*, not implied.
- **Branch rows are unchanged `.follow` rows:** the `↳` `::before`, the
  dim uppercase `.who` (`you` / `loop`), the quieter `.qts` stamp, and
  the luminance split (human at `--lit`, loop at `--muted`). **No
  accent** — accent is for live and actionable things.
- **The root says it is a root.** Human Answer already carries the
  awaiting rail and `✓`. A loop `Reply` root takes `.follow.root` as the
  rail's anchor only — no new colour, no badge.
- **`lead` keeps today's treatment**, including `.qthread` disclosure at
  `QTHREAD_FOLD_AT = 2`. One note is still not a thread.
- **The branch never collapses.** It is live, and it is where a note he
  just wrote lands. Only the segment a resolution has already answered
  may fold (#128).
- **A second rail inside a branch is impossible by construction**, not
  by CSS. The branch is a flat list; there is no path that nests one.

### Responsive at 390px

One depth costs `.thread`'s `1ch` + 1px rail, on top of `.follow`'s
existing hanging indent (`padding-left: 2.6ch; text-indent: -2.6ch`) —
roughly **one character of reading column, once**, no matter how long
the exchange runs. That is the entire reason N1 caps the depth.

At narrow widths (including ~390px):

- **Keep the rail** — it is the relationship signal.
- **Drop the branch's `padding-left` to 0** — adjacent to the rail the
  indent is redundant.
- Do **not** introduce a second depth, a horizontal scroll for the
  branch, or a "collapse branch" disclosure. Measure the resulting
  reading column against the page's existing minimum; the reflow work
  found the interesting widths are in the *middle* of a sweep, not only
  at the ends.

**Cost of this choice:** one character of column at every width that
keeps the rail. **Buy:** the relationship stays visible when the column
is tight, without a staircase that would cost N characters on a long
thread.

---

## 5. Authorship and accessibility

Authorship *is* the content of this fix. A visual hierarchy that
announces as a flat list is a failed design here.

- **The exchange is one real list.** `lead`, root, and `branch` render
  as a single `<ul>` of `<li>`; the branch is a **nested `<ul>` inside
  the root's own `<li>`**. A screen reader announces "list, N items …
  item k … list, M items" — exactly one level of nesting, matching the
  pixels. A **sibling** `<ul>` looks identical and announces flat; that
  is the failure the a11y check exists to catch.
- **Authorship and time lead the announcement.** `.who` and `.qts` stay
  the first text nodes in a `.follow` row, in that order: "you ·
  2026-07-26 14:47 · \<text\>". Do not move them into `::before` or hide
  them from the tree.
- **The `↳` glyph stays decorative** (CSS `content`, unannounced). The
  nested list already carries "reply to"; a spoken second statement is
  noise on every row.
- **The branch carries a group label** naming what it replies to:
  `aria-label` on the nested `<ul>`, derived from the root —
  `replies to the answer`, or `replies to your note of <ts>` / `replies
  to the loop's note of <ts>`. Derived, never invented: if the root has
  no stamp, omit the stamp rather than guessing.
- **Focus order is unchanged.** Card → settled thread's `<summary>` if
  present → composer → send → mode group.
  - **The composer stays outside the branch.** One input per card
    (#103). A box inside a branch would promise "reply to this turn",
    which `/comment` cannot keep (it appends to the end of the
    sequence).
  - If the branch ever gains a control, it sits after the root and
    before the composer: DOM order = reading order = tab order.
- **No live region.** The branch arrives inside a card the tick
  re-renders; announcing it would double up with the row itself.

**Cost of real nesting:** a slightly more careful `qaCard` template.
**Buy:** a screen reader and a sighted reader receive the same structure,
and the check that catches a sibling-`<ul>` mistake is structural rather
than geometric.

---

## 6. The transition (described only)

`transitions.md` binds with no size floor. **No new gesture is
authored** — every case already has a cell in the state matrix.

| what happens | existing idiom |
|---|---|
| a note lands in a branch | *"same card, a note lands"* — lifts from the box into the thread; card grows; same seam, same regroup. Where it lands is a layout fact, not a motion one |
| a branch appears for the first time | the unfold reveal: `.qreveal` + `.dreamin`. Start state must **snap** (`transition:none` on the start-state class, reflow, remove next frame) or the class animates *toward* the start and reads as a pop-in |
| a branch empties | `dreamAway` at the rect it occupied, clipped below the line the survivor still fills |
| a contribution moves from lead into branch (answer landed between) | *"same state, moved"* — it **slides**; it survived, so it travels rather than re-entering with `.dreamin` |
| **reduced motion** | **same DOM, same computed inset, no travel, no ghost.** Only the frames differ. A reduced-motion path that lays out differently is a second design |

---

## 7. What is NOT worth doing (with reasons)

| not doing | why |
|---|---|
| **Per-turn reply targets / true nesting** | Explicitly rejected by N1. A staircase on a long exchange is the defect this exists to prevent. Recorded so it is not re-proposed as an improvement |
| **Promoting `Follow-up (loop, …)` to root when there is no Answer** (R2) | Refused. Inverts on the common clarifying-question shape |
| **Shipping N1 without the loop resolution tag** (R3) | Refused. Closes #254 while leaving his evidence card unchanged |
| **Threading `## Answered`** | Resolution head sits at the *start* of the body there; rooting at it attaches pre-fold notes as replies to the resolution — wrong attachment; timestamp cut is forbidden |
| **Deriving structure from timestamps** | Second mechanism able to disagree with file order |
| **A second component or accent colour for the branch** | `.thread`'s rail already is the depth; accent is for live/actionable |
| **Composer inside the branch** | Promises per-turn reply; `/comment` cannot keep it |
| **Collapsing the live branch** | #128: never fold away what he just wrote |
| **Editing `file-formats.md` ahead of the parser** | Documents a tag the renderer cannot read — #340/#343 into the contract |
| **Fixing two-answer data loss in this grant** | Real bug (`_parse_entries` overwrites `cur["answer"]`); separate task, not a rendering rule |
| **Fixing Answered-section raw Answer rendering in this grant** | Real bug (`lift_answer=False`; measured 15/29 live entries lack a `you` label); separate task |
| **Any lint check for the branch shape itself** | The branch is a render-side rule over signals the format already defines. A lint check for it cannot fail for its stated reason. *If* R1's tag lands, *that* tag needs a format entry + lint import of the same tuple, in the same commit |

---

## 8. How an implementation would be proven

(Specified so the later increment does not invent hollow checks. Not run
in this grant.)

### Fixtures (frozen, under `dev/capture/fixture/.dreamwork/questions.md`)

- **F1 `rooted-human`** — Note → Answer → Note → Follow-up. One lead, one
  root, branch of two.
- **F2 `no root`** — Note → Follow-up, no Answer, no Reply. Must render
  flat. Precondition: assert ≥2 contributions or "no branch" is
  satisfied by "no contributions".
- **F3 `rooted-loop`** — Note → Reply(loop) → Note. The screenshot case
  once R1's tag is live.
- **F4 `two answers`** — Note → Answer(a) → Note → Answer(b) → Note.
  Records what it **cannot** prove: the first answer's text is gone
  before the rule runs.
- **F5 `root, no branch`** — Note → Answer, nothing after. No branch
  container.
- **F6 `unrecognised`** — a literal wrong tag still body prose (pin
  today's behaviour for tags that are *not* R1's).

### Checks (each names the production line that reddens it)

1. F1 partitions correctly — reddens on the cut expression using
   `answer_at`. Runtime precondition: `0 < answer_at < follows.length`.
2. F2 emits no `.thread.branch` — reddens on deleting the null test for
   resolution. Precondition: ≥2 contributions.
3. F3 roots at the Reply — reddens on treating Reply as a normal
   follow. Precondition: fixture contains exactly one `Reply (loop` and
   its index is derived at runtime, not a literal.
4. Depth is exactly one, measured — reddens on a recursive container.
   Precondition: branch has ≥2 rows **and** the card shows at least two
   distinct inset values.
5. Nesting is real (`<ul>` inside root's `<li>`) — reddens on moving the
   branch to a sibling (identical pixels, flat announcement).
6. A note posted into a branch travels — part-way frame via
   `between(vals, first, last)`, ≤1400ms window, node never replaced.
7. Reduced-motion parity — same DOM, same computed inset.
8. At least one guard drives the **dashboard**, not only `/questions`
   (#179). Closed `<details>`: use `checkVisibility()`.

**A green red-run is a finding, never a relief.**

---

## 9. Open decisions for him

**None that are genuinely his on this design.**

- **N1** settled the shape (one rooted exchange, single inset depth,
  no staircase, no-root stays flat).
- **R1** settled the loop resolution tag; **R2** and **R3** are closed
  with reasons.
- D1–D7 below are implementer defaults that follow from those two
  rulings. Overruling any one is a one-line correction, not a new
  design pass.

### Implementer defaults (overrule by naming the line)

- **D1** — A root is a **resolution** only: human `Answer (via watch, …)`
  or loop `Reply (loop, …)`. Never a bare `Follow-up`.
- **D2** — At most **one** branch per question card.
- **D3** — `## Answered` stays flat.
- **D4** — Human Answer (step 1) outranks loop Reply (step 2).
- **D5** — Real `<ul>`/`<li>` nesting, not ARIA-on-divs.
- **D6** — Narrow: keep the rail, drop the padding.
- **D7** — Empty branch emits no container.
- **D8** — When two loop `Reply` tags exist and no human Answer, the
  **last** is the root (same supersession reading as two Answers).

### The next ask (not this grant)

Implementation — recognising `Reply (loop, …)`, the render rule, the
fixtures and checks above — is a **separate** authorisation. This
document does not grant it. Exact `questions.md` text for that ask is in
the lane report; the coordinator is the only writer of that file.

### Artifact

**Skipped.** There is no decision genuinely his left on this design. A
decoy `#ask` is worse than none (repo rule; #436). Before/after lives in
§3 of this document. The earlier review page
`.dreamwork/review/note-reply-threading-254.html` remains as history of
the pre-R1 ask; it must not be treated as the current ask surface.

---

## 10. Cost / buy summary

| recommendation | buys | costs |
|---|---|---|
| one root + one flat branch at one inset | authorship and causality readable at a glance | careful `qaCard` partition; one character of column |
| R1's `Reply (loop, …)` as loop resolution | his screenshot card becomes fixable without R2's inversion | one new tag in `NOTE_TAGS` + `file-formats.md` + tests, **same commit**; writers must choose Reply vs Follow-up deliberately |
| prefer flat over wrong attach | never a false claim about who answered whom | under-claims on ambiguous entries until a resolution tag is written |
| reuse `.thread` rail | no new component, no new transition | implementer must not invent a second container |
| real nested `<ul>` | screen reader and pixels agree | template discipline; one dedicated a11y check |
| keep Answered flat | no wrong attachment from body-head position | Answered threads stay as today's sibling list until a later design |
| skip decoy artifact | honest empty desk | no HTML before/after pane (mock in §3 instead) |

---

## SUMMARY

- **What.** Post-R1 written design for #254. Resolution is the root;
  later notes and loop non-resolution follows render as **one flat
  branch at a single inset depth**. Prefer flat over wrongly-attached.
  Never a staircase. Never timestamp structure.
- **Data.** Existing `NOTE_TAGS` / `ANSWER_TAGS` / `answer_at` described
  as-is; ambiguities named. R1 obliges recognising `Reply (loop, …)` as
  a loop **resolution** tag — design obligation, implementation not
  authorised here.
- **Rule.** Three steps: human Answer → loop Reply → flat. Cases
  tabulated. Before/after for his card in §3.
- **A11y.** Nested list inside the root's `<li>`; `.who` + `.qts` lead
  the announcement; composer outside the branch.
- **390px.** Keep rail, drop branch padding; one character once.
- **Motion.** Reuse matrix cells only; reduced-motion = same DOM/inset.
- **Not doing.** True nesting, R2/R3, Answered threading, timestamp
  cuts, format edits ahead of parser, two-answer fix, decoy ask.
- **Open for him.** None on design. Implementation is a separate ask.
- **No parser, format, UI, or transition was changed by this document.**
